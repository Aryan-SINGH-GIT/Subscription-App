from celery import shared_task
from django.utils import timezone
from subscriptions.models import Subscription
from metering.services import reset_usage, get_usage
from core.utils import notify_user

@shared_task
def generate_monthly_invoices():
    # This should run on the 1st of every month
    subscriptions = Subscription.objects.filter(active=True)
    
    for sub in subscriptions:
        # Calculate usage for the past month
        # For simplicity, we just read current counters and reset them
        
        invoice_items = []
        total_cost = sub.plan.price
        
        for pf in sub.plan.planfeature_set.all():
            used = get_usage(sub.user.id, pf.feature.code)
            invoice_items.append({
                'feature': pf.feature.name,
                'used': used,
                'limit': pf.limit
            })
            
            # Reset usage for next month
            reset_usage(sub.user.id, pf.feature.code)
            
        # Send invoice webhook
        notify_user(sub.user, 'invoice_generated', {
            'amount': str(total_cost),
            'items': invoice_items,
            'date': str(timezone.now().date())
        })

@shared_task
def generate_daily_usage_reports():
    """Send daily usage summary to all active subscribers"""
    subscriptions = Subscription.objects.filter(active=True)
    
    for sub in subscriptions:
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
