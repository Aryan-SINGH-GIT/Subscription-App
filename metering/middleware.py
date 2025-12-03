import time
import logging
from django.http import JsonResponse
from subscriptions.models import Subscription, PlanFeature
from .services import increment_usage, get_usage, check_rate_limit
from core.utils import notify_user

logger = logging.getLogger(__name__)

class EntitlementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        feature_code = request.headers.get('X-Feature-Code')
        should_increment = False
        
        if feature_code and request.user.is_authenticated:
            # 1. Check Subscription
            subscription = Subscription.objects.filter(user=request.user, active=True).select_related('plan').first()
            if not subscription:
                return JsonResponse({'detail': 'No active subscription'}, status=403)
            
            plan = subscription.plan
            
            # 2. Check Rate Limiting (if plan has rate_limit > 0)
            # Purpose: Tests API gateway throttling, concurrency race conditions
            # Used by: Rate-Limited Plan (5 calls per minute)
            if plan.rate_limit > 0:
                rate_limit_key = f"rate_limit:{request.user.id}:{feature_code}"
                if not check_rate_limit(rate_limit_key, plan.rate_limit, plan.rate_limit_window):
                    return JsonResponse({
                        'detail': f'Rate limit exceeded: {plan.rate_limit} calls per {plan.rate_limit_window} seconds'
                    }, status=429)  # 429 Too Many Requests
            
            # 3. Check Feature in Plan
            try:
                plan_feature = PlanFeature.objects.get(plan=plan, feature__code=feature_code)
            except PlanFeature.DoesNotExist:
                return JsonResponse({'detail': 'Feature not included in plan'}, status=403)
            
            # 4. Check Usage Limit
            limit = plan_feature.limit
            current_usage = get_usage(request.user.id, feature_code)
            
            # If plan has overage billing, allow usage over limit but track it
            # Purpose: Tests metered billing, overage invoice line items
            # Used by: Overage Plan (₹1 per extra call over 1000)
            has_overage = plan.overage_price > 0
            
            if limit != -1 and current_usage >= limit:
                if not has_overage:
                    # Hard limit - no overage billing, block the request
                    notify_user(request.user, 'limit_exceeded', {
                        'feature': feature_code,
                        'limit': limit,
                        'current_usage': current_usage
                    })
                    return JsonResponse({'detail': 'Usage limit exceeded'}, status=403)
                else:
                    # Overage billing enabled - allow but will be charged extra
                    # Log overage usage for invoice generation
                    logger.info(f"Overage usage: User {request.user.id}, Feature {feature_code}, "
                              f"Limit {limit}, Current {current_usage}, Overage {current_usage - limit}")
            
            # Mark that we should increment usage if request succeeds
            should_increment = True
            
        # Process the request
        response = self.get_response(request)
        
        # Only increment usage if:
        # 1. Request was successful (status < 400)
        # 2. This is NOT the /api/metering/event/ endpoint (view handles its own incrementing)
        # This prevents double counting when using the event endpoint
        is_event_endpoint = request.path == '/api/metering/event/'
        
        if should_increment and feature_code and response.status_code < 400 and not is_event_endpoint:
            increment_usage(request.user.id, feature_code)
        
        return response
