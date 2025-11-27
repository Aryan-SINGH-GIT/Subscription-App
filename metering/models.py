from django.db import models
from django.conf import settings
from subscriptions.models import Feature

class MeterEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meter_events')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    event_id = models.CharField(max_length=100, unique=True, help_text="Idempotency key")
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.feature.code} - {self.timestamp}"
