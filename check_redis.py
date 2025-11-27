#!/usr/bin/env python
"""
Quick script to check Redis usage counts
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subscriptionEngine.settings')
django.setup()

from metering.services import get_usage, check_idempotency
from core.models import User
import redis
from django.conf import settings

def main():
    print("=" * 60)
    print("Redis Usage Count Checker")
    print("=" * 60)
    
    # Connect to Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        print("✅ Redis is connected!\n")
    except redis.ConnectionError:
        print("❌ Redis is NOT running!\n")
        return
    
    # Show all keys
    print("📋 All Redis Keys:")
    all_keys = r.keys('*')
    if all_keys:
        for key in all_keys:
            key_str = key.decode('utf-8')
            value = r.get(key)
            value_str = value.decode('utf-8') if value else 'N/A'
            print(f"  - {key_str} = {value_str}")
    else:
        print("  (No keys found - no usage recorded yet)")
    
    print("\n" + "=" * 60)
    print("👥 Usage by User:")
    print("=" * 60)
    
    # Get all users
    users = User.objects.all()
    if not users:
        print("  (No users found)")
        return
    
    for user in users:
        print(f"\n👤 User: {user.username} (ID: {user.id})")
        
        # Check for common feature codes
        feature_codes = ['demo_feature', 'api_calls', 'pdf_exports', 'ai_text_generation']
        
        has_usage = False
        for feature_code in feature_codes:
            usage = get_usage(user.id, feature_code)
            if usage > 0:
                has_usage = True
                print(f"   ├─ {feature_code}: {usage} uses")
        
        if not has_usage:
            print(f"   └─ No usage recorded")
    
    print("\n" + "=" * 60)
    print("🔑 Idempotency (Recent Event IDs):")
    print("=" * 60)
    
    event_keys = r.keys('event:*')
    if event_keys:
        for i, key in enumerate(event_keys[:10], 1):  # Show max 10
            key_str = key.decode('utf-8')
            event_id = key_str.replace('event:', '')
            ttl = r.ttl(key)
            print(f"  {i}. {event_id} (expires in {ttl}s)")
    else:
        print("  (No event IDs stored)")
    
    print("\n" + "=" * 60)
    print("Summary Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
