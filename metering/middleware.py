import time
import logging
from django.http import JsonResponse
from django.core.cache import cache
from subscriptions.models import Subscription, PlanFeature
from .services import increment_usage, get_usage, check_rate_limit
from core.utils import notify_user

logger = logging.getLogger(__name__)

class EntitlementMiddleware:
    """
    Optimized middleware for API entitlement checking.
    Target: P95 latency < 10ms for api_calls feature.
    
    Optimizations:
    - Request-level caching to avoid duplicate queries
    - Batch Redis operations where possible
    - Optimized database queries with select_related/prefetch_related
    - Early returns for common failure cases
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        feature_code = request.headers.get('X-Feature-Code')
        should_increment = False
        
        # Early exit if no feature code or not authenticated
        if not feature_code or not request.user.is_authenticated:
            response = self.get_response(request)
            return response
        
        # Request-level cache key for subscription
        cache_key = f"sub_{request.user.id}"
        
        # Try to get subscription from request cache first (per-request caching)
        if not hasattr(request, '_cached_subscription'):
            subscription = Subscription.objects.filter(
                user=request.user, 
                active=True
            ).select_related('plan').only(
                'id', 'plan_id', 'plan__id', 'plan__name', 'plan__price', 
                'plan__rate_limit', 'plan__rate_limit_window', 'plan__overage_price'
            ).first()
            
            if not subscription:
                return JsonResponse({'detail': 'No active subscription'}, status=403)
            
            # Cache in request object for this request
            request._cached_subscription = subscription
            request._cached_plan = subscription.plan
        
        subscription = request._cached_subscription
        plan = request._cached_plan
        
        # 2. Check Rate Limiting (if plan has rate_limit > 0) - Fast Redis check
        if plan.rate_limit > 0:
            rate_limit_key = f"rate_limit:{request.user.id}:{feature_code}"
            if not check_rate_limit(rate_limit_key, plan.rate_limit, plan.rate_limit_window):
                return JsonResponse({
                    'detail': f'Rate limit exceeded: {plan.rate_limit} calls per {plan.rate_limit_window} seconds'
                }, status=429)
        
        # 3. Check Feature in Plan - Use cached plan features if available
        if not hasattr(request, '_cached_plan_features'):
            # Prefetch all plan features for this plan
            plan_features = PlanFeature.objects.filter(
                plan=plan
            ).select_related('feature').only('plan_id', 'feature_id', 'feature__code', 'limit')
            
            # Create a dict for O(1) lookup
            request._cached_plan_features = {
                pf.feature.code: pf for pf in plan_features
            }
        
        plan_feature = request._cached_plan_features.get(feature_code)
        if not plan_feature:
            return JsonResponse({'detail': 'Feature not included in plan'}, status=403)
        
        # 4. Check Usage Limit - Fast Redis call
        limit = plan_feature.limit
        current_usage = get_usage(request.user.id, feature_code)
        
        # If plan has overage billing, allow usage over limit but track it
        has_overage = plan.overage_price > 0
        
        if limit != -1 and current_usage >= limit:
            if not has_overage:
                # Hard limit - no overage billing, block the request
                # Defer webhook notification to avoid blocking (async would be better)
                try:
                    notify_user(request.user, 'limit_exceeded', {
                        'feature': feature_code,
                        'limit': limit,
                        'current_usage': current_usage
                    }, raise_on_error=False)
                except:
                    pass  # Don't block on webhook failure
                return JsonResponse({'detail': 'Usage limit exceeded'}, status=403)
            else:
                # Overage billing enabled - allow but will be charged extra
                logger.debug(f"Overage usage: User {request.user.id}, Feature {feature_code}, "
                          f"Limit {limit}, Current {current_usage}, Overage {current_usage - limit}")
        
        # Mark that we should increment usage if request succeeds
        should_increment = True
        
        # Process the request
        response = self.get_response(request)
        
        # Only increment usage if:
        # 1. Request was successful (status < 400)
        # 2. This is NOT the /api/metering/event/ endpoint (view handles its own incrementing)
        is_event_endpoint = request.path == '/api/metering/event/'
        
        if should_increment and feature_code and response.status_code < 400 and not is_event_endpoint:
            increment_usage(request.user.id, feature_code)
        
        # Log latency for monitoring (only for api_calls to avoid spam)
        if feature_code == 'api_calls':
            latency_ms = (time.time() - start_time) * 1000
            if latency_ms > 10:  # Log if over target
                logger.warning(f"Middleware latency: {latency_ms:.2f}ms for user {request.user.id}")
        
        return response
