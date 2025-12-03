import requests
import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

def notify_user(user, event_type, payload, raise_on_error=False):
    """
    Send webhook notification to a specific user's webhook URL
    
    Args:
        user: User instance with webhook_url
        event_type: Type of event (e.g., 'test_webhook', 'limit_reached')
        payload: Dictionary with event data
        raise_on_error: If True, raises exception on failure instead of just logging
    
    Returns:
        bool: True if webhook sent successfully, False otherwise
    """
    if not user.webhook_url:
        if raise_on_error:
            raise ValueError("No webhook URL configured for user")
        return False
    
    data = {
        'event': event_type,
        'payload': payload
    }
    
    try:
        response = requests.post(user.webhook_url, json=data, timeout=5)
        response.raise_for_status()
        logger.info(f"User webhook sent to {user.username}: {event_type}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send user webhook to {user.webhook_url}: {e}")
        if raise_on_error:
            raise
        return False




