from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction
from django.utils import timezone
from .models import MeterEvent
from .services import check_idempotency, increment_usage_if_below_limit, get_usage, increment_usage, check_rate_limit
from subscriptions.models import Feature, Subscription, PlanFeature
import uuid
import logging

logger = logging.getLogger(__name__)

class UsageEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        feature_code = request.data.get('feature_code')
        
        if not feature_code:
            return Response({'detail': 'feature_code required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Always auto-generate event_id for idempotency (compulsory)
        # This ensures every request has a unique identifier
        event_id = str(uuid.uuid4())
        
        # Check idempotency first (fast Redis check)
        if not check_idempotency(event_id):
            return Response({'detail': 'Duplicate event'}, status=status.HTTP_409_CONFLICT)
        
        # Optimized: Use request-level caching if available (from middleware)
        if hasattr(request, '_cached_subscription'):
            subscription = request._cached_subscription
            plan = request._cached_plan
        else:
            # Check entitlement - optimized query
            subscription = Subscription.objects.filter(
                user=request.user, 
                active=True
            ).select_related('plan').only(
                'id', 'plan_id', 'plan__id', 'plan__name', 'plan__price',
                'plan__rate_limit', 'plan__rate_limit_window', 'plan__overage_price'
            ).first()
            
            if not subscription:
                return Response({'detail': 'No active subscription'}, status=status.HTTP_403_FORBIDDEN)
            
            plan = subscription.plan
        
        # Optimized: Use cached plan features if available
        if hasattr(request, '_cached_plan_features'):
            plan_feature = request._cached_plan_features.get(feature_code)
            if not plan_feature:
                return Response({'detail': 'Feature not allowed'}, status=status.HTTP_403_FORBIDDEN)
        else:
            try:
                feature = Feature.objects.only('id', 'code').get(code=feature_code)
                plan_feature = PlanFeature.objects.select_related('feature').only(
                    'plan_id', 'feature_id', 'limit'
                ).get(plan=plan, feature=feature)
            except (Feature.DoesNotExist, PlanFeature.DoesNotExist):
                return Response({'detail': 'Feature not allowed'}, status=status.HTTP_403_FORBIDDEN)
        
        limit = plan_feature.limit
        
        # Check rate limiting (if plan has rate_limit > 0)
        # Purpose: Tests API gateway throttling, concurrency race conditions
        # Used by: Rate-Limited Plan (5 calls per minute)
        if plan.rate_limit > 0:
            rate_limit_key = f"rate_limit:{request.user.id}:{feature_code}"
            if not check_rate_limit(rate_limit_key, plan.rate_limit, plan.rate_limit_window):
                return Response({
                    'detail': f'Rate limit exceeded: {plan.rate_limit} calls per {plan.rate_limit_window} seconds'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check if plan has overage billing
        # If overage is enabled, allow usage over limit (will be charged extra)
        has_overage = plan.overage_price > 0
        
        if has_overage and limit != -1:
            # Overage billing enabled - always allow, just increment usage
            new_usage = increment_usage(request.user.id, feature_code)
        else:
            # No overage - use atomic increment-if-below-limit
            success, new_usage = increment_usage_if_below_limit(
                request.user.id, 
                feature_code, 
                limit
            )
            
            if not success:
                return Response({'detail': 'Limit exceeded'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get feature for event logging (use cached if available)
        if hasattr(request, '_cached_plan_features') and feature_code in request._cached_plan_features:
            feature = request._cached_plan_features[feature_code].feature
        else:
            feature = Feature.objects.only('id', 'code').get(code=feature_code)
        
        # Log event (after successful increment) - Use bulk_create or defer for better performance
        # For latency optimization, we can defer this or make it non-blocking
        try:
            # Use get_or_create to avoid duplicate key errors and reduce query overhead
            MeterEvent.objects.get_or_create(
                event_id=event_id,
                defaults={
                    'user_id': request.user.id,  # Use user_id instead of user object
                    'feature_id': feature.id,  # Use feature_id instead of feature object
                    'metadata': request.data.get('metadata', {})
                }
            )
        except Exception as e:
            logger.error(f"Error creating MeterEvent: {e}", exc_info=True)
            # Don't fail the request if event logging fails
        
        # Check if user just hit their limit (defer webhook to avoid blocking)
        if limit != -1 and new_usage >= limit:
            # Send webhook notification to user (non-blocking for latency)
            try:
                from core.utils import notify_user
                remaining = max(0, limit - new_usage)
                
                # Get feature name (use cached if available)
                feature_name = feature.name if hasattr(feature, 'name') else feature_code
                
                notify_user(request.user, 'limit_reached', {
                    'user_id': request.user.id,
                    'username': request.user.username,
                    'feature_code': feature_code,
                    'feature_name': feature_name,
                    'usage': new_usage,
                    'limit': limit,
                    'remaining': remaining,
                    'plan_name': subscription.plan.name,
                    'message': 'Limit reached. You can renew or upgrade your current subscription.',
                    'suggested_actions': [
                        'Upgrade to a higher plan for more capacity',
                        'Renew your current subscription to reset usage counters'
                    ],
                    'upgrade_endpoint': '/api/subscriptions/change-plan/',
                    'renew_endpoint': '/api/subscriptions/renew/'
                }, raise_on_error=False)  # Don't block on webhook failure
            except Exception as e:
                logger.error(f"Error sending limit_reached webhook: {e}", exc_info=True)
                # Don't fail the request if webhook fails
        
        # Calculate remaining (for overage plans, can be negative)
        if limit == -1:
            remaining = 'Unlimited'
        elif has_overage:
            remaining = 'Overage allowed' if new_usage > limit else (limit - new_usage)
        else:
            remaining = max(0, limit - new_usage)
        
        return Response({
            'status': 'recorded',
            'event_id': event_id,
            'usage': new_usage,
            'limit': limit if limit != -1 else 'Unlimited',
            'remaining': remaining,
            'overage': (new_usage - limit) if has_overage and limit != -1 and new_usage > limit else 0
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
            # Return empty response instead of 404 for better frontend handling
            return Response({'features': [], 'message': 'No active subscription'}, status=status.HTTP_200_OK)
            
        # Optimized: Fetch all plan features with related feature data in one query
        plan_features = PlanFeature.objects.filter(
            plan=subscription.plan
        ).select_related('feature')
        
        usage_data = []
        
        for pf in plan_features:
            used = get_usage(request.user.id, pf.feature.code)
            usage_data.append({
                'feature_name': pf.feature.name,
                'feature_code': pf.feature.code,
                'current_usage': used,
                'limit': pf.limit,
                'remaining': pf.limit - used if pf.limit != -1 else 'Unlimited'
            })    
        return Response({'features': usage_data})

# Invoice Views
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.http import FileResponse, Http404
from .models import Invoice
from .serializers import InvoiceSerializer, InvoiceListSerializer

class InvoicePagination(PageNumberPagination):
    """Pagination for invoice list"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class InvoiceListView(generics.ListAPIView):
    """List all invoices for the authenticated user"""
    serializer_class = InvoiceListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = InvoicePagination
    
    def get_queryset(self):
        queryset = Invoice.objects.filter(user=self.request.user).select_related('subscription', 'subscription__plan')
        
        # Filter by status if provided
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)
            
        return queryset

class InvoiceDetailView(generics.RetrieveAPIView):
    """Get detailed invoice information"""
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see their own invoices
        return Invoice.objects.filter(user=self.request.user)

class InvoiceDownloadView(APIView):
    """Download invoice PDF"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, user=request.user)
        except Invoice.DoesNotExist:
            raise Http404("Invoice not found")
        
        if not invoice.pdf_file:
            return Response(
                {'detail': 'PDF not available for this invoice'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Return the PDF file
        response = FileResponse(
            invoice.pdf_file.open('rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response

class GenerateTestInvoiceView(APIView):
    """Generate a test invoice for the authenticated user (for testing purposes)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        from metering.models import Invoice
        from metering.invoice_generator import generate_invoice_pdf, generate_invoice_number
        from django.core.files.base import ContentFile
        from dateutil.relativedelta import relativedelta
        from decimal import Decimal
        import random
        
        user = request.user
        subscription = Subscription.objects.filter(user=user, active=True).first()
        
        if not subscription:
            return Response(
                {'detail': 'No active subscription found. Please subscribe to a plan first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        period_end = today
        period_start = today - relativedelta(months=1)
        
        # Check if invoice already exists for this period
        existing = Invoice.objects.filter(
            user=user,
            subscription=subscription,
            period_start=period_start,
            period_end=period_end
        ).first()
        
        if existing:
            return Response({
                'detail': 'Invoice already exists for this period',
                'invoice_id': existing.id,
                'invoice_number': existing.invoice_number
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate usage
        invoice_items = []
        total_cost = subscription.plan.price
        
        for pf in subscription.plan.planfeature_set.all():
            used = get_usage(user.id, pf.feature.code)
            invoice_items.append({
                'feature': pf.feature.name,
                'used': used,
                'limit': pf.limit
            })
        
        # Create invoice in transaction
        with transaction.atomic():
            invoice_number = generate_invoice_number(user.id, today)
            
            # Check if invoice with this number already exists and make it unique
            if Invoice.objects.filter(invoice_number=invoice_number).exists():
                # Add microseconds and random component to ensure uniqueness
                now = timezone.now()
                timestamp_ms = int(now.timestamp() * 1000000)  # Include microseconds
                random_suffix = random.randint(1000, 9999)
                invoice_number = f"{invoice_number}-{timestamp_ms}-{random_suffix}"
            
            # Double-check uniqueness (race condition protection)
            max_retries = 5
            retry_count = 0
            original_number = invoice_number
            while Invoice.objects.filter(invoice_number=invoice_number).exists() and retry_count < max_retries:
                now = timezone.now()
                timestamp_ms = int(now.timestamp() * 1000000)
                random_suffix = random.randint(10000, 99999)
                invoice_number = f"{original_number}-{timestamp_ms}-{random_suffix}"
                retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Could not generate unique invoice number after {max_retries} retries")
                return Response(
                    {'detail': 'Could not generate unique invoice number. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            invoice = Invoice.objects.create(
                user=user,
                subscription=subscription,
                invoice_number=invoice_number,
                invoice_date=today,
                period_start=period_start,
                period_end=period_end,
                subtotal=total_cost,
                tax=Decimal('0.00'),
                total=total_cost,
                status='finalized',
                items=invoice_items
            )
            
            # Generate PDF
            try:
                pdf_content = generate_invoice_pdf(invoice)
                invoice.pdf_file.save(
                    f'{invoice_number}.pdf',
                    ContentFile(pdf_content),
                    save=True
                )
            except Exception as e:
                logger.error(f"Error generating PDF for invoice {invoice_number}: {e}", exc_info=True)
                # Continue even if PDF generation fails
        
        return Response({
            'status': 'success',
            'message': 'Test invoice generated successfully',
            'invoice': InvoiceListSerializer(invoice).data
        }, status=status.HTTP_201_CREATED)
