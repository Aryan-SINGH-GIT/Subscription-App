from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer

class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]

class SubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not subscription:
            return Response({"detail": "No active subscription"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    def post(self, request):
        # Subscribe
        serializer = SubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            # Check if user already has active subscription
            if Subscription.objects.filter(user=request.user, active=True).exists():
                return Response({"detail": "User already has an active subscription"}, status=status.HTTP_400_BAD_REQUEST)
            
            subscription = serializer.save(user=request.user)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        # Upgrade/Downgrade
        subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not subscription:
            return Response({"detail": "No active subscription"}, status=status.HTTP_404_NOT_FOUND)
        
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"detail": "plan_id required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"detail": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)

        from .utils import calculate_proration
        
        prorated_amount = calculate_proration(subscription, new_plan)
        
        # In a real app, we would charge the user here.
        # For now, we just record the change.
        
        old_plan_name = subscription.plan.name
        subscription.plan = new_plan
        subscription.save()
        
        # Notify the user
        from core.utils import notify_user
        notify_user(request.user, 'subscription_updated', {
            'previous_plan': old_plan_name,
            'new_plan': new_plan.name,
            'prorated_amount': str(prorated_amount)
        })
        
        serializer = SubscriptionSerializer(subscription)
        data = serializer.data
        data['prorated_amount'] = prorated_amount
        return Response(data)


class ChangePlanView(APIView):
    """Change subscription plan (upgrade or downgrade)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Get current subscription
        current_subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not current_subscription:
            return Response({
                "detail": "No active subscription. Please subscribe to a plan first."
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get target plan
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"detail": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"detail": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if trying to switch to the same plan
        if new_plan.id == current_subscription.plan.id:
            return Response({
                "detail": "You are already subscribed to this plan"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate proration
        from .utils import calculate_proration
        prorated_amount = calculate_proration(current_subscription, new_plan)
        
        # Deactivate old subscription
        old_plan_name = current_subscription.plan.name
        current_subscription.active = False
        current_subscription.save()
        
        # Create new subscription
        new_subscription = Subscription.objects.create(
            user=request.user,
            plan=new_plan,
            active=True,
            start_date=timezone.now()
        )
        
        # Determine if upgrade or downgrade
        is_upgrade = new_plan.price > current_subscription.plan.price
        event_type = 'subscription_upgraded' if is_upgrade else 'subscription_downgraded'
        action = 'upgraded' if is_upgrade else 'downgraded'
        
        # Notify user
        from core.utils import notify_user
        notify_user(request.user, event_type, {
            'user_id': request.user.id,
            'username': request.user.username,
            'old_plan': old_plan_name,
            'new_plan': new_plan.name,
            'new_plan_price': str(new_plan.price),
            'billing_period': new_plan.billing_period,
            'prorated_amount': str(prorated_amount),
            'message': f'Successfully {action} from {old_plan_name} to {new_plan.name}!'
        })
        
        serializer = SubscriptionSerializer(new_subscription)
        return Response({
            **serializer.data,
            'message': f'Successfully {action} from {old_plan_name} to {new_plan.name}',
            'prorated_amount': str(prorated_amount)
        }, status=status.HTTP_200_OK)


class RenewSubscriptionView(APIView):
    """Renew current subscription and reset usage counters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Get current subscription
        subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not subscription:
            return Response({
                "detail": "No active subscription to renew"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Reset usage counters for all features
        from metering.services import reset_usage
        from subscriptions.models import PlanFeature
        
        plan_features = PlanFeature.objects.filter(plan=subscription.plan)
        reset_count = 0
        for pf in plan_features:
            reset_usage(request.user.id, pf.feature.code)
            reset_count += 1
        
        # Update subscription start date
        subscription.start_date = timezone.now()
        subscription.save()
        
        # Notify user
        from core.utils import notify_user
        notify_user(request.user, 'subscription_renewed', {
            'user_id': request.user.id,
            'username': request.user.username,
            'plan_name': subscription.plan.name,
            'plan_price': str(subscription.plan.price),
            'billing_period': subscription.plan.billing_period,
            'start_date': subscription.start_date.isoformat(),
            'features_reset': reset_count,
            'message': f'Successfully renewed {subscription.plan.name}. All usage counters have been reset!'
        })
        
        serializer = SubscriptionSerializer(subscription)
        return Response({
            **serializer.data,
            'message': f'Successfully renewed {subscription.plan.name}. All usage counters have been reset!',
            'features_reset': reset_count
        }, status=status.HTTP_200_OK)
