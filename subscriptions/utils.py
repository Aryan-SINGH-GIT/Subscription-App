from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

def calculate_proration(subscription, new_plan):
    now = timezone.now()
    if not subscription.end_date:
        # Should not happen for active subscription with billing period, but handle gracefully
        return Decimal('0.00')

    remaining_time = subscription.end_date - now
    total_time = subscription.end_date - subscription.start_date
    
    if total_time.total_seconds() <= 0:
        return Decimal('0.00')

    remaining_ratio = Decimal(remaining_time.total_seconds()) / Decimal(total_time.total_seconds())
    
    unused_value = subscription.plan.price * remaining_ratio
    new_plan_cost_for_remaining = new_plan.price * remaining_ratio
    
    prorated_amount = new_plan_cost_for_remaining - unused_value
    return prorated_amount.quantize(Decimal('0.01'))
