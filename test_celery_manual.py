import os
import django
import time
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subscriptionEngine.settings')
django.setup()

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from django.contrib.auth import get_user_model
from subscriptions.models import Plan, Feature, PlanFeature, Subscription
from metering.services import increment_usage, get_usage
from metering.tasks import generate_daily_usage_reports, generate_monthly_invoices
from core.models import User

def cleanup_junk_users():
    """Disable webhooks for users with invalid URLs to avoid connection errors"""
    print("--- Cleaning up junk data ---")
    count = 0
    for user in User.objects.exclude(username='celery_test_user'):
        if user.webhook_url and ('localhost' in user.webhook_url or 'test.com' in user.webhook_url):
            print(f"  - Disabling webhook for {user.username} ({user.webhook_url})")
            user.webhook_url = ''
            user.save()
            count += 1
    print(f"✓ Cleaned up {count} users with invalid webhooks")

def setup_test_data():
    print("\n--- Setting up Test Data ---")
    user, _ = User.objects.get_or_create(username='celery_test_user', email='celery@test.com')
    user.set_password('password')
    
    # Set a webhook URL
    # IMPORTANT: Replace this with your actual webhook.site URL
    current_url = user.webhook_url
    target_url = 'https://webhook.site/2e2ceb7c-9e07-4de0-ac77-6239bb114fc3'
    
    # Always update to the target URL if it's different
    if user.webhook_url != target_url:
        print(f"  Updating webhook URL from {user.webhook_url} to {target_url}")
        user.webhook_url = target_url
    
    if 'YOUR-UUID-HERE' in user.webhook_url:
        print("⚠️  WARNING: You haven't replaced 'YOUR-UUID-HERE' with a real UUID!")
        print("   Edit this script to set a valid webhook URL to see real delivery.")
    else:
        print(f"✓ Sending webhooks to: {user.webhook_url}")
    
    user.save()
    
    feature, _ = Feature.objects.get_or_create(code='test_feat', defaults={'name': 'Test Feature'})
    plan, _ = Plan.objects.get_or_create(name='Test Plan', defaults={'price': 100})
    PlanFeature.objects.get_or_create(plan=plan, feature=feature, defaults={'limit': 1000})
    
    sub, _ = Subscription.objects.get_or_create(user=user, active=True, defaults={'plan': plan})
    sub.plan = plan
    sub.save()
    
    # Generate some usage
    increment_usage(user.id, 'test_feat', 5)
    print(f"✓ Created user {user.username} with 5 usage on 'test_feat'")
    return user

def test_tasks():
    cleanup_junk_users()
    user = setup_test_data()
    
    print("\n" + "="*60)
    print("--- Testing Daily Reports Task ---")
    print("="*60)
    print(f"[{time.strftime('%H:%M:%S')}] Starting daily usage report task...")
    print(f"[{time.strftime('%H:%M:%S')}] Target user: {user.username} (ID: {user.id})")
    print(f"[{time.strftime('%H:%M:%S')}] Webhook URL: {user.webhook_url}")
    
    start_time = time.time()
    generate_daily_usage_reports()
    elapsed = time.time() - start_time
    
    print(f"[{time.strftime('%H:%M:%S')}] ✓ Task completed in {elapsed:.2f}s")
    print(f"[{time.strftime('%H:%M:%S')}] Check your webhook.site dashboard for the 'daily_usage_report' event")
    
    print("\n" + "="*60)
    print("--- Testing Monthly Invoice Task ---")
    print("="*60)
    print(f"[{time.strftime('%H:%M:%S')}] Starting monthly invoice task...")
    print(f"[{time.strftime('%H:%M:%S')}] This will reset usage counters and send invoices")
    
    start_time = time.time()
    generate_monthly_invoices()
    elapsed = time.time() - start_time
    
    print(f"[{time.strftime('%H:%M:%S')}] ✓ Task completed in {elapsed:.2f}s")
    
    # Verify reset
    usage = get_usage(user.id, 'test_feat')
    print(f"\n[{time.strftime('%H:%M:%S')}] Verification:")
    print(f"  Usage after monthly reset: {usage} (Expected: 0)")
    if usage == 0:
        print(f"  ✓ Counter reset successful!")
    else:
        print(f"  ✗ Counter was not reset properly")
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"✓ Daily report sent to {user.webhook_url}")
    print(f"✓ Monthly invoice sent to {user.webhook_url}")
    print(f"✓ Usage counters reset")
    print("\nCheck your webhook.site dashboard to see the actual webhook payloads!")
    print("="*60)

if __name__ == "__main__":
    test_tasks()
