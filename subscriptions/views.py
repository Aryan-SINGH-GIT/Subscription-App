from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction
import logging
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer
from .utils import calculate_subscription_end_date

logger = logging.getLogger(__name__)

class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, *args, **kwargs):
        # Auto-run migrations if tables don't exist (for free tier without Shell)
        try:
            # Try to query plans - this will fail if table doesn't exist
            Plan.objects.count()
        except Exception:
            # Table doesn't exist, run migrations
            try:
                from django.core.management import call_command
                from django.db import connection
                from django.conf import settings
                
                # Check if database is configured
                if settings.DATABASES['default'].get('NAME'):
                    connection.ensure_connection()
                    logger.info("Running migrations automatically...")
                    call_command('migrate', verbosity=1, interactive=False)
                    
                    # Setup demo data if no plans exist
                    try:
                        if Plan.objects.count() == 0:
                            logger.info("Setting up demo data...")
                            call_command('setup_demo_data', verbosity=0)
                    except:
                        pass
            except Exception as e:
                logger.error(f"Auto-migration failed: {e}", exc_info=True)
                # Return error response instead of crashing
                from rest_framework.response import Response
                from rest_framework import status
                return Response({
                    "detail": "Database migrations required. Please ensure DATABASE_URL is set and database is accessible.",
                    "error": str(e)
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return super().get(request, *args, **kwargs)

class SubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subscription = Subscription.objects.filter(user=request.user, active=True).first()
        if not subscription:
            return Response({"detail": "No active subscription"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        # Subscribe
        serializer = SubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            # Use select_for_update to prevent race conditions
            # Check if user already has active subscription atomically
            existing = Subscription.objects.filter(
                user=request.user, 
                active=True
            ).select_for_update().first()
            
            if existing:
                return Response(
                    {"detail": "User already has an active subscription"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            subscription = serializer.save(user=request.user)
            
            # Calculate and set end_date if not provided
            if not subscription.end_date:
                subscription.end_date = calculate_subscription_end_date(subscription)
                subscription.save()
            
            # Create invoice for new subscription
            invoice = None
            try:
                from metering.invoice_utils import create_subscription_invoice
                invoice = create_subscription_invoice(subscription, invoice_type='subscription')
                if invoice:
                    logger.info(f"Created invoice {invoice.invoice_number} for new subscription")
            except Exception as e:
                logger.error(f"Failed to create invoice for new subscription: {e}", exc_info=True)
                # Don't fail subscription creation if invoice generation fails
            
            response_data = serializer.data
            # Include invoice information in response
            if invoice:
                from metering.serializers import InvoiceListSerializer
                response_data['invoice'] = InvoiceListSerializer(invoice).data
                response_data['message'] = f'Successfully subscribed to {subscription.plan.name}! Invoice has been generated.'
            else:
                response_data['message'] = f'Successfully subscribed to {subscription.plan.name}!'
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def put(self, request):
        # Upgrade/Downgrade - This method is deprecated in favor of ChangePlanView
        # Keeping for backward compatibility but redirecting to ChangePlanView logic
        subscription = Subscription.objects.filter(
            user=request.user, 
            active=True
        ).select_for_update().first()
        
        if not subscription:
            return Response({"detail": "No active subscription"}, status=status.HTTP_404_NOT_FOUND)
        
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"detail": "plan_id required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"detail": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if trying to switch to the same plan
        if new_plan.id == subscription.plan.id:
            return Response({
                "detail": "You are already subscribed to this plan"
            }, status=status.HTTP_400_BAD_REQUEST)

        from .utils import calculate_proration
        
        prorated_amount = calculate_proration(subscription, new_plan)
        
        # Update subscription
        old_plan_name = subscription.plan.name
        subscription.plan = new_plan
        # Recalculate end_date for new plan
        subscription.end_date = calculate_subscription_end_date(subscription)
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
    
    @transaction.atomic
    def post(self, request):
        # Get current subscription with lock to prevent race conditions
        current_subscription = Subscription.objects.filter(
            user=request.user, 
            active=True
        ).select_for_update().first()
        
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
        
        # Create new subscription with calculated end_date
        new_subscription = Subscription.objects.create(
            user=request.user,
            plan=new_plan,
            active=True,
            start_date=timezone.now(),
            end_date=calculate_subscription_end_date(
                Subscription(plan=new_plan, start_date=timezone.now())
            )
        )
        
        # Create invoice for plan change (if prorated amount is positive)
        if prorated_amount > 0:
            try:
                from metering.invoice_utils import create_subscription_invoice
                invoice = create_subscription_invoice(new_subscription, invoice_type='upgrade')
                if invoice:
                    logger.info(f"Created upgrade invoice {invoice.invoice_number}")
            except Exception as e:
                logger.error(f"Failed to create invoice for plan change: {e}", exc_info=True)
                # Don't fail plan change if invoice generation fails
        
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
    
    @transaction.atomic
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
        
        # Update subscription dates for renewal
        old_start_date = subscription.start_date
        subscription.start_date = timezone.now()
        # Recalculate end_date for renewed period
        subscription.end_date = calculate_subscription_end_date(subscription)
        subscription.save()
        
        # Create invoice for renewal
        invoice = None
        try:
            from metering.invoice_utils import create_subscription_invoice
            invoice = create_subscription_invoice(subscription, invoice_type='renewal')
            if invoice:
                logger.info(f"Created renewal invoice {invoice.invoice_number}")
        except Exception as e:
            logger.error(f"Failed to create invoice for renewal: {e}", exc_info=True)
            # Don't fail renewal if invoice generation fails
        
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
            'invoice_id': invoice.id if invoice else None,
            'invoice_number': invoice.invoice_number if invoice else None,
            'message': f'Successfully renewed {subscription.plan.name}. All usage counters have been reset!'
        })
        
        serializer = SubscriptionSerializer(subscription)
        response_data = {
            **serializer.data,
            'message': f'Successfully renewed {subscription.plan.name}. All usage counters have been reset!',
            'features_reset': reset_count
        }
        
        # Include invoice information in response
        if invoice:
            from metering.serializers import InvoiceListSerializer
            response_data['invoice'] = InvoiceListSerializer(invoice).data
        
        return Response(response_data, status=status.HTTP_200_OK)
