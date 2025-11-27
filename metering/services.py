import redis
from django.conf import settings

r = redis.from_url(settings.REDIS_URL)

def get_usage_key(user_id, feature_code):
    return f"usage:{user_id}:{feature_code}"

def increment_usage(user_id, feature_code, amount=1):
    key = get_usage_key(user_id, feature_code)
    return r.incrby(key, amount)

def get_usage(user_id, feature_code):
    key = get_usage_key(user_id, feature_code)
    val = r.get(key)
    return int(val) if val else 0

def check_idempotency(event_id):
    key = f"event:{event_id}"
    if r.exists(key):
        return False
    r.setex(key, 86400, 1) # 24 hour TTL
    return True

def reset_usage(user_id, feature_code):
    key = get_usage_key(user_id, feature_code)
    r.delete(key)
