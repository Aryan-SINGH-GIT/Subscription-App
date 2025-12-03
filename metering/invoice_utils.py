"""
Utility functions for invoice generation
"""
import logging
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import Invoice
from .invoice_generator import generate_invoice_pdf, generate_invoice_number
from .services import get_usage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

def create_subscription_invoice(subscription, invoice_type='subscription'):
    """
    Create an invoice for a subscription (new purchase or renewal)
    
    Args:
        subscription: Subscription instance
        invoice_type: Type of invoice ('subscription', 'renewal', 'upgrade')
    
    Returns:
        Invoice instance or None if creation failed
    """
    try:
        user = subscription.user
        plan = subscription.plan
        today = timezone.now().date()
        
        # For new subscriptions/renewals, invoice period is from start_date to end_date
        # Handle both datetime and date objects
        if hasattr(subscription.start_date, 'date'):
            period_start = subscription.start_date.date()
        else:
            period_start = subscription.start_date
        
        if subscription.end_date:
            if hasattr(subscription.end_date, 'date'):
                period_end = subscription.end_date.date()
            else:
                period_end = subscription.end_date
        else:
            # If end_date is not set, calculate it
            from subscriptions.utils import calculate_subscription_end_date
            end_date = calculate_subscription_end_date(subscription)
            if hasattr(end_date, 'date'):
                period_end = end_date.date()
            else:
                period_end = end_date
        
        # Calculate invoice items (current usage for features)
        invoice_items = []
        total_cost = plan.price
        overage_total = Decimal('0.00')
        
        for pf in plan.planfeature_set.all():
            used = get_usage(user.id, pf.feature.code)
            
            # Calculate overage if plan has overage billing
            # Purpose: Tests metered billing, overage invoice line items
            # Used by: Overage Plan (₹1 per extra call over 1000)
            overage_amount = Decimal('0.00')
            if plan.overage_price > 0 and pf.limit != -1 and used > pf.limit:
                overage_units = used - pf.limit
                overage_amount = Decimal(str(plan.overage_price)) * Decimal(str(overage_units))
                overage_total += overage_amount
                
                # Add overage as separate line item
                invoice_items.append({
                    'feature': f'{pf.feature.name} (Overage)',
                    'used': overage_units,
                    'limit': 0,
                    'description': f'Overage charges: {overage_units} units × ₹{plan.overage_price}',
                    'price': str(overage_amount),
                    'is_overage': True
                })
            
            # Add regular usage item
            invoice_items.append({
                'feature': pf.feature.name,
                'used': used,
                'limit': pf.limit,
                'description': f'{pf.feature.name} usage (included: {min(used, pf.limit) if pf.limit != -1 else used})',
                'is_overage': False
            })
        
        # Add subscription item
        invoice_items.insert(0, {
            'feature': f'{plan.name} Subscription',
            'used': 1,
            'limit': 1,
            'description': f'{plan.billing_period.capitalize()} subscription for {plan.name}',
            'price': str(plan.price),
            'is_overage': False
        })
        
        # Add overage to total
        total_cost = plan.price + overage_total
        
        # Create invoice in transaction
        with transaction.atomic():
            invoice_number = generate_invoice_number(user.id, today)
            
            # Check if invoice with this number already exists
            if Invoice.objects.filter(invoice_number=invoice_number).exists():
                # Add timestamp to make it unique
                invoice_number = f"{invoice_number}-{int(timezone.now().timestamp())}"
            
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
                logger.info(f"Generated PDF for invoice {invoice_number} ({invoice_type})")
            except Exception as e:
                logger.error(f"Error generating PDF for invoice {invoice_number}: {e}", exc_info=True)
                # Continue even if PDF generation fails
            
            # Send webhook notification
            try:
                from core.utils import notify_user
                notify_user(user, 'invoice_generated', {
                    'invoice_id': invoice.id,
                    'invoice_number': invoice_number,
                    'invoice_type': invoice_type,
                    'amount': str(total_cost),
                    'plan_name': plan.name,
                    'items': invoice_items,
                    'date': str(today),
                    'period_start': str(period_start),
                    'period_end': str(period_end),
                    'download_url': f'/api/metering/invoices/{invoice.id}/download/'
                })
            except Exception as e:
                logger.error(f"Error sending webhook for invoice {invoice_number}: {e}", exc_info=True)
            
            return invoice
            
    except Exception as e:
        logger.error(f"Error creating invoice for subscription {subscription.id}: {e}", exc_info=True)
        return None

