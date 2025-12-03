import redis
import logging
import time
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)

# Redis connection with error handling
try:
    r = redis.from_url(settings.REDIS_URL, decode_responses=False)
    # Test connection
    r.ping()
except (redis.ConnectionError, redis.TimeoutError) as e:
    logger.error(f"Redis connection failed: {e}")
    r = None

# Default TTL for usage keys (90 days - should be reset on subscription renewal)
USAGE_KEY_TTL = 90 * 24 * 60 * 60  # 90 days in seconds

def get_usage_key(user_id, feature_code):
    return f"usage:{user_id}:{feature_code}"

def _ensure_redis():
    """Ensure Redis connection is available"""
    if r is None:
        raise redis.ConnectionError("Redis is not available")
    return r

def increment_usage(user_id, feature_code, amount=1):
    """
    Increment usage counter with TTL.
    Returns the new usage count.
    """
    try:
        redis_client = _ensure_redis()
        key = get_usage_key(user_id, feature_code)
        # Use pipeline for atomic operation
        pipe = redis_client.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, USAGE_KEY_TTL)  # Set TTL to prevent unbounded growth
        results = pipe.execute()
        return results[0]
    except redis.RedisError as e:
        logger.error(f"Redis error in increment_usage: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in increment_usage: {e}")
        raise

def get_usage(user_id, feature_code):
    """
    Get current usage count.
    Returns 0 if key doesn't exist or on error.
    """
    try:
        redis_client = _ensure_redis()
        key = get_usage_key(user_id, feature_code)
        val = redis_client.get(key)
        return int(val) if val else 0
    except redis.RedisError as e:
        logger.error(f"Redis error in get_usage: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error in get_usage: {e}")
        return 0

def increment_usage_if_below_limit(user_id, feature_code, limit, amount=1):
    """
    Atomically increment usage only if below limit.
    Returns (success: bool, new_count: int)
    """
    if limit == -1:  # Unlimited
        return True, increment_usage(user_id, feature_code, amount)
    
    try:
        redis_client = _ensure_redis()
        key = get_usage_key(user_id, feature_code)
        
        # Use WATCH/MULTI for atomic check-and-increment
        pipe = redis_client.pipeline()
        pipe.watch(key)
        current = get_usage(user_id, feature_code)
        
        if current >= limit:
            pipe.unwatch()
            return False, current
        
        pipe.multi()
        pipe.incrby(key, amount)
        pipe.expire(key, USAGE_KEY_TTL)
        results = pipe.execute()
        
        return True, results[0]
    except redis.WatchError:
        # Another process modified the key, retry
        logger.warning(f"Redis watch error for {key}, retrying")
        return increment_usage_if_below_limit(user_id, feature_code, limit, amount)
    except redis.RedisError as e:
        logger.error(f"Redis error in increment_usage_if_below_limit: {e}")
        return False, get_usage(user_id, feature_code)
    except Exception as e:
        logger.error(f"Unexpected error in increment_usage_if_below_limit: {e}")
        return False, get_usage(user_id, feature_code)

def check_idempotency(event_id):
    """
    Check if event_id has been processed (idempotency check).
    Returns True if event is new, False if duplicate.
    """
    try:
        redis_client = _ensure_redis()
        key = f"event:{event_id}"
        if redis_client.exists(key):
            return False
        redis_client.setex(key, 86400, 1)  # 24 hour TTL
        return True
    except redis.RedisError as e:
        logger.error(f"Redis error in check_idempotency: {e}")
        # On error, allow the event (fail open)
        return True
    except Exception as e:
        logger.error(f"Unexpected error in check_idempotency: {e}")
        return True

def reset_usage(user_id, feature_code):
    """
    Reset usage counter for a user/feature.
    """
    try:
        redis_client = _ensure_redis()
        key = get_usage_key(user_id, feature_code)
        redis_client.delete(key)
    except redis.RedisError as e:
        logger.error(f"Redis error in reset_usage: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in reset_usage: {e}")
        raise

def check_rate_limit(rate_limit_key, max_calls, window_seconds):
    """
    Check if rate limit is exceeded using sliding window algorithm.
    Uses Lua script for atomic operations to prevent race conditions.
    
    Purpose: Tests API gateway throttling, concurrency race conditions
    Used by: Rate-Limited Plan (5 calls per minute)
    
    Args:
        rate_limit_key: Redis key for rate limiting (e.g., "rate_limit:user_id:feature")
        max_calls: Maximum calls allowed in the window
        window_seconds: Time window in seconds
    
    Returns:
        True if within limit, False if exceeded
    """
    try:
        redis_client = _ensure_redis()
        now = int(time.time())
        window_start = now - window_seconds
        
        # Lua script for atomic rate limit check and increment
        # This ensures the check and add happen atomically
        # Uses sliding window: removes entries older than window_start, then checks count
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local max_calls = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])
        local unique_id = ARGV[5]
        
        -- Remove old entries outside the window (entries with score < window_start)
        -- This ensures the window slides correctly
        redis.call('zremrangebyscore', key, '-inf', window_start - 1)
        
        -- Count current calls in window (after removing old ones)
        local current_calls = redis.call('zcard', key)
        
        -- Check if we're at or over the limit BEFORE adding
        if current_calls >= max_calls then
            return 0  -- Rate limit exceeded
        end
        
        -- Add current call with timestamp as score
        redis.call('zadd', key, now, unique_id)
        
        -- Set expiration to window_seconds + small buffer
        redis.call('expire', key, window_seconds + 5)
        
        return 1  -- Within limit, call added
        """
        
        # Use sorted set to track calls with timestamps
        unique_id = f"{now}_{uuid.uuid4().hex[:8]}"
        
        # Execute Lua script atomically
        # Redis eval format: eval(script, num_keys, *keys_and_args)
        result = redis_client.eval(
            lua_script,
            1,  # Number of keys
            rate_limit_key,  # KEYS[1]
            str(now),  # ARGV[1]
            str(window_start),  # ARGV[2]
            str(max_calls),  # ARGV[3]
            str(window_seconds),  # ARGV[4]
            unique_id  # ARGV[5]
        )
        
        # Lua script returns 1 for success, 0 for rate limit exceeded
        return bool(result)
                    
    except redis.RedisError as e:
        logger.error(f"Redis error in check_rate_limit: {e}")
        # On error, allow the request (fail open)
        return True
    except Exception as e:
        logger.error(f"Unexpected error in check_rate_limit: {e}")
        return True
