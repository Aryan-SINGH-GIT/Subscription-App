import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from subscriptions.models import Subscription
from metering.services import reset_usage, get_usage
from core.utils import notify_user

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_monthly_invoices(self):
    """Generate monthly invoices with PDF documents"""
    from metering.models import Invoice
    from metering.invoice_generator import generate_invoice_pdf, generate_invoice_number
    from django.core.files.base import ContentFile
    from dateutil.relativedelta import relativedelta
    
    logger.info("Starting monthly invoice generation")
    
    # This should run on the 1st of every month
    subscriptions = Subscription.objects.filter(active=True).select_related('user', 'plan')
    
    today = timezone.now().date()
    period_end = today
    period_start = today - relativedelta(months=1)
    
    success_count = 0
    error_count = 0
    
    for sub in subscriptions:
        try:
            # Check if invoice already exists for this period (idempotency)
            existing_invoice = Invoice.objects.filter(
                user=sub.user,
                subscription=sub,
                period_start=period_start,
                period_end=period_end
            ).first()
            
            if existing_invoice:
                logger.info(f"Invoice already exists for user {sub.user.id} for period {period_start} to {period_end}")
                continue
            
            # Calculate usage for the past month
            invoice_items = []
            total_cost = sub.plan.price
            
            for pf in sub.plan.planfeature_set.all():
                used = get_usage(sub.user.id, pf.feature.code)
                invoice_items.append({
                    'feature': pf.feature.name,
                    'used': used,
                    'limit': pf.limit
                })
            
            # Create Invoice record in transaction
            with transaction.atomic():
                invoice_number = generate_invoice_number(sub.user.id, today)
                
                # Double-check invoice doesn't exist (race condition protection)
                if Invoice.objects.filter(invoice_number=invoice_number).exists():
                    logger.warning(f"Invoice {invoice_number} already exists, skipping")
                    continue
                
                invoice = Invoice.objects.create(
                    user=sub.user,
                    subscription=sub,
                    invoice_number=invoice_number,
                    invoice_date=today,
                    period_start=period_start,
                    period_end=period_end,
                    subtotal=total_cost,
                    tax=0,  # Can be calculated based on location
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
                    logger.info(f"Generated PDF for invoice {invoice_number}")
                except Exception as e:
                    logger.error(f"Error generating PDF for invoice {invoice_number}: {e}", exc_info=True)
                    # Continue even if PDF generation fails
                
                # Reset usage AFTER invoice is successfully created
                for pf in sub.plan.planfeature_set.all():
                    reset_usage(sub.user.id, pf.feature.code)
                
                # Send invoice webhook with download link
                try:
                    notify_user(sub.user, 'invoice_generated', {
                        'invoice_id': invoice.id,
                        'invoice_number': invoice_number,
                        'amount': str(total_cost),
                        'items': invoice_items,
                        'date': str(today),
                        'period_start': str(period_start),
                        'period_end': str(period_end),
                        'download_url': f'/api/metering/invoices/{invoice.id}/download/'
                    })
                except Exception as e:
                    logger.error(f"Error sending webhook for invoice {invoice_number}: {e}", exc_info=True)
                    # Don't fail the task if webhook fails
                
                success_count += 1
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error generating invoice for user {sub.user.id}: {e}", exc_info=True)
            # Continue with next subscription even if one fails
    
    logger.info(f"Invoice generation completed: {success_count} successful, {error_count} errors")
    return {'success': success_count, 'errors': error_count}

@shared_task(bind=True, max_retries=3)
def generate_daily_usage_reports(self):
    """Send daily usage summary to all active subscribers"""
    logger.info("Starting daily usage report generation")
    
    subscriptions = Subscription.objects.filter(active=True).select_related('user', 'plan')
    
    success_count = 0
    error_count = 0
    
    for sub in subscriptions:
        try:
            usage_data = []
            for pf in sub.plan.planfeature_set.all():
                used = get_usage(sub.user.id, pf.feature.code)
                usage_data.append({
                    'feature': pf.feature.name,
                    'used': used,
                    'limit': pf.limit
                })
                
            notify_user(sub.user, 'daily_usage_report', {
                'date': str(timezone.now().date()),
                'usage': usage_data
            })
            success_count += 1
            
        except Exception as e:
            error_count += 1
            logger.error(f"Error sending usage report for user {sub.user.id}: {e}", exc_info=True)
            # Continue with next subscription even if one fails
    
    logger.info(f"Usage report generation completed: {success_count} successful, {error_count} errors")
    return {'success': success_count, 'errors': error_count}
