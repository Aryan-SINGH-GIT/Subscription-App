import requests
import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

def notify_user(user, event_type, payload):
    """Send webhook notification to a specific user's webhook URL"""
    if not user.webhook_url:
        return
    
    data = {
        'event': event_type,
        'payload': payload
    }
    
    try:
        response = requests.post(user.webhook_url, json=data, timeout=5)
        response.raise_for_status()
        logger.info(f"User webhook sent to {user.username}: {event_type}")
    except requests.RequestException as e:
        logger.error(f"Failed to send user webhook to {user.webhook_url}: {e}")




