from django.db import models
from django.conf import settings
from django.utils import timezone

class Feature(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Plan(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_period = models.CharField(
        max_length=20, 
        choices=[
            ('monthly', 'Monthly'), 
            ('yearly', 'Yearly'),
            ('hourly', 'Hourly'),
            ('minute', 'Per Minute')
        ], 
        default='monthly'
    )
    # Overage billing: price per unit over the limit
    overage_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Price per unit when usage exceeds limit (0 = no overage billing)"
    )
    # Rate limiting: max calls per time window (in seconds)
    rate_limit = models.IntegerField(
        default=0,
        help_text="Max calls per rate_limit_window seconds (0 = no rate limiting)"
    )
    rate_limit_window = models.IntegerField(
        default=60,
        help_text="Time window in seconds for rate limiting (default: 60 = 1 minute)"
    )
    features = models.ManyToManyField(Feature, through='PlanFeature')

    def __str__(self):
        return self.name

class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, db_index=True)
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE)
    limit = models.IntegerField(default=-1, help_text="-1 for unlimited")

    class Meta:
        unique_together = ('plan', 'feature')
        indexes = [
            models.Index(fields=['plan', 'feature']),
        ]

class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions', db_index=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'active']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
