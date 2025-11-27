from django.http import JsonResponse
from subscriptions.models import Subscription, PlanFeature
from .services import increment_usage, get_usage
from core.utils import notify_user

class EntitlementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        feature_code = request.headers.get('X-Feature-Code')
        
        if feature_code and request.user.is_authenticated:
            # 1. Check Subscription
            subscription = Subscription.objects.filter(user=request.user, active=True).first()
            if not subscription:
                return JsonResponse({'detail': 'No active subscription'}, status=403)
            
            # 2. Check Feature in Plan
            try:
                plan_feature = PlanFeature.objects.get(plan=subscription.plan, feature__code=feature_code)
            except PlanFeature.DoesNotExist:
                return JsonResponse({'detail': 'Feature not included in plan'}, status=403)
            
            # 3. Check Limit
            limit = plan_feature.limit
            if limit != -1:
                current_usage = get_usage(request.user.id, feature_code)
                if current_usage >= limit:
                    notify_user(request.user, 'limit_exceeded', {'feature': feature_code, 'limit': limit})
                    return JsonResponse({'detail': 'Usage limit exceeded'}, status=403)
            
            # 4. Increment Usage (Optimistic)
            # We increment here. If the view fails, we might want to decrement?
            # For now, we count the attempt as usage if it passes the gate.
            increment_usage(request.user.id, feature_code)
            
            # Also log MeterEvent asynchronously? 
            # For now, we'll just rely on Redis for real-time and maybe a background task for persistence.
            # Or we can create MeterEvent here but it might slow down response.
            # Let's keep it simple: Redis is the source of truth for limits.
            
        response = self.get_response(request)
        return response
