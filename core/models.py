from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    webhook_url = models.URLField(
        blank=True, 
        null=True,
        help_text="Webhook URL to receive notifications (e.g., when API limits are hit)"
    )


