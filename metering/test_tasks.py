from django.test import TestCase
from django.contrib.auth import get_user_model
from subscriptions.models import Plan, Feature, PlanFeature, Subscription
from metering.services import increment_usage, get_usage, reset_usage
from metering.tasks import generate_monthly_invoices, generate_daily_usage_reports
from unittest.mock import patch

User = get_user_model()

class TaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='taskuser', password='password')
        self.feature = Feature.objects.create(code='task_feature', name='Task Feature')
        self.plan = Plan.objects.create(name='Task Plan', price=50.00)
        PlanFeature.objects.create(plan=self.plan, feature=self.feature, limit=100)
        self.subscription = Subscription.objects.create(user=self.user, plan=self.plan)
        
        # Ensure clean state
        import redis
        from django.conf import settings
        r = redis.from_url(settings.REDIS_URL)
        r.flushdb()
        
        # Simulate usage
        increment_usage(self.user.id, 'task_feature', amount=10)

    def tearDown(self):
        import redis
        from django.conf import settings
        r = redis.from_url(settings.REDIS_URL)
        r.flushdb()

    @patch('metering.tasks.notify_user')
    def test_daily_usage_report(self, mock_notify):
        print("\n" + "="*60)
        print("TEST: Daily Usage Report Generation")
        print("="*60)
        print(f"  Setup: User '{self.user.username}' with {get_usage(self.user.id, 'task_feature')} usage on 'task_feature'")
        print(f"  Action: Running generate_daily_usage_reports() task...")
        
        generate_daily_usage_reports()
        
        print(f"  ✓ Task executed successfully")
        
        self.assertTrue(mock_notify.called)
        print(f"  ✓ Webhook notification triggered")
        
        call_args = mock_notify.call_args
        user = call_args[0][0]
        event = call_args[0][1]
        payload = call_args[0][2]
        
        self.assertEqual(user, self.user)
        print(f"  ✓ Correct user targeted: {user.username}")
        
        self.assertEqual(event, 'daily_usage_report')
        print(f"  ✓ Event type correct: '{event}'")
        
        self.assertEqual(payload['usage'][0]['feature'], 'Task Feature')
        self.assertEqual(payload['usage'][0]['used'], 10)
        print(f"  ✓ Payload verified: {payload['usage'][0]['feature']} = {payload['usage'][0]['used']}/{payload['usage'][0]['limit']}")
        print("  " + "="*58)
        print("  PASSED ✓")
        print("="*60)

    @patch('metering.tasks.notify_user')
    def test_monthly_invoice(self, mock_notify):
        print("\n" + "="*60)
        print("TEST: Monthly Invoice Generation & Counter Reset")
        print("="*60)
        
        # Verify usage before reset
        usage_before = get_usage(self.user.id, 'task_feature')
        self.assertEqual(usage_before, 10)
        print(f"  Setup: User '{self.user.username}' has {usage_before} usage")
        print(f"  Action: Running generate_monthly_invoices() task...")
        
        generate_monthly_invoices()
        
        print(f"  ✓ Task executed successfully")
        
        # Verify notification
        self.assertTrue(mock_notify.called)
        print(f"  ✓ Invoice webhook notification triggered")
        
        call_args = mock_notify.call_args
        event = call_args[0][1]
        self.assertEqual(event, 'invoice_generated')
        print(f"  ✓ Event type correct: '{event}'")
        
        # Verify usage reset
        usage_after = get_usage(self.user.id, 'task_feature')
        self.assertEqual(usage_after, 0)
        print(f"  ✓ Usage counter reset: {usage_before} → {usage_after}")
        print("  " + "="*58)
        print("  PASSED ✓")
        print("="*60)
