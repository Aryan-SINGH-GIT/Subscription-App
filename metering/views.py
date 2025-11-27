from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import MeterEvent
from .services import check_idempotency, increment_usage, get_usage
from subscriptions.models import Feature, Subscription, PlanFeature

class UsageEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        feature_code = request.data.get('feature_code')
        event_id = request.data.get('event_id')
        
        if not feature_code or not event_id:
            return Response({'detail': 'feature_code and event_id required'}, status=status.HTTP_400_BAD_REQUEST)
            
        if not check_idempotency(event_id):
            return Response({'detail': 'Duplicate event'}, status=status.HTTP_409_CONFLICT)
            
        # Check entitlement
        subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not subscription:
             return Response({'detail': 'No active subscription'}, status=status.HTTP_403_FORBIDDEN)
             
        try:
            feature = Feature.objects.get(code=feature_code)
            plan_feature = PlanFeature.objects.get(plan=subscription.plan, feature=feature)
        except (Feature.DoesNotExist, PlanFeature.DoesNotExist):
            return Response({'detail': 'Feature not allowed'}, status=status.HTTP_403_FORBIDDEN)
            
        limit = plan_feature.limit
        if limit != -1:
            current = get_usage(request.user.id, feature_code)
            if current >= limit:
                return Response({'detail': 'Limit exceeded'}, status=status.HTTP_403_FORBIDDEN)
        
        # Log event
        MeterEvent.objects.create(
            user=request.user,
            feature=feature,
            event_id=event_id,
            metadata=request.data.get('metadata', {})
        )
        
        # Increment counter
        new_usage = increment_usage(request.user.id, feature_code)
        
        # Check if user just hit their limit
        if limit != -1 and new_usage >= limit:
            # Send webhook notification to user
            from core.utils import notify_user
            remaining = limit - new_usage
            
            notify_user(request.user, 'limit_reached', {
                'user_id': request.user.id,
                'username': request.user.username,
                'feature_code': feature_code,
                'feature_name': feature.name,
                'usage': new_usage,
                'limit': limit,
                'remaining': remaining,
                'plan_name': subscription.plan.name,
                'message': 'limit is exceed user can renew or upgrade the current subscription',
                'suggested_actions': [
                    'Upgrade to a higher plan for more capacity',
                    'Renew your current subscription to reset usage counters'
                ],
                'upgrade_endpoint': '/api/subscriptions/upgrade/',
                'renew_endpoint': '/api/subscriptions/renew/'
            })
        
        return Response({
            'status': 'recorded',
            'usage': new_usage,
            'limit': limit if limit != -1 else 'Unlimited',
            'remaining': limit - new_usage if limit != -1 else 'Unlimited'
        }, status=status.HTTP_201_CREATED)

class UsageSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Optimized: Use select_related to reduce queries
        subscription = Subscription.objects.filter(
            user=request.user, 
            active=True
        ).select_related('plan').first()
        
        if not subscription:
            return Response({'detail': 'No active subscription'}, status=status.HTTP_404_NOT_FOUND)
            
        # Optimized: Fetch all plan features with related feature data in one query
        plan_features = PlanFeature.objects.filter(
            plan=subscription.plan
        ).select_related('feature')
        
        usage_data = []
        
        for pf in plan_features:
            used = get_usage(request.user.id, pf.feature.code)
            usage_data.append({
                'feature': pf.feature.name,
                'code': pf.feature.code,
                'limit': pf.limit,
                'used': used,
                'remaining': pf.limit - used if pf.limit != -1 else 'Unlimited'
            })    
        return Response(usage_data)
