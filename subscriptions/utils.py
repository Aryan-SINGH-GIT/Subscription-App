from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta

def calculate_subscription_end_date(subscription):
    """Calculate end_date based on billing period if not set"""
    if subscription.end_date:
        return subscription.end_date
    
    billing_period = subscription.plan.billing_period
    
    if billing_period == 'monthly':
        return subscription.start_date + relativedelta(months=1)
    elif billing_period == 'yearly':
        return subscription.start_date + relativedelta(years=1)
    elif billing_period == 'hourly':
        # High-frequency renewal plan: bills every hour
        return subscription.start_date + timedelta(hours=1)
    elif billing_period == 'minute':
        # Per-minute billing (for extreme stress testing)
        return subscription.start_date + timedelta(minutes=1)
    else:
        # Default to monthly if unknown
        return subscription.start_date + relativedelta(months=1)

def calculate_proration(subscription, new_plan):
    """
    Calculate prorated amount when switching from one plan to another.
    Handles null end_date by calculating it based on billing period.
    """
    now = timezone.now()
    
    # Calculate end_date if not set
    end_date = calculate_subscription_end_date(subscription)
    
    # Check if subscription has already expired
    if end_date <= now:
        # Subscription has expired, no proration needed
        return Decimal('0.00')
    
    # Calculate remaining time
    remaining_time = end_date - now
    total_time = end_date - subscription.start_date
    
    if total_time.total_seconds() <= 0:
        return Decimal('0.00')

    # Calculate proration ratio
    remaining_ratio = Decimal(remaining_time.total_seconds()) / Decimal(total_time.total_seconds())
    
    # Calculate unused value from current plan
    unused_value = subscription.plan.price * remaining_ratio
    
    # Calculate cost for remaining period on new plan
    new_plan_cost_for_remaining = new_plan.price * remaining_ratio
    
    # Prorated amount is the difference
    prorated_amount = new_plan_cost_for_remaining - unused_value
    return prorated_amount.quantize(Decimal('0.01'))
