from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Plan, Feature, PlanFeature, Subscription

User = get_user_model()

class SubscriptionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        # Use existing API Calls feature or create it
        self.feature, _ = Feature.objects.get_or_create(code='api_calls', defaults={'name': 'API Calls'})
        
        # Use existing plans from setup_demo_data or create test plans
        self.plan_basic, _ = Plan.objects.get_or_create(
            name='Basic Monthly Plan',
            defaults={'price': 100.00, 'billing_period': 'monthly'}
        )
        PlanFeature.objects.get_or_create(
            plan=self.plan_basic, 
            feature=self.feature, 
            defaults={'limit': 5}
        )
        
        self.plan_pro, _ = Plan.objects.get_or_create(
            name='Quota Plan',
            defaults={'price': 200.00, 'billing_period': 'monthly'}
        )
        PlanFeature.objects.get_or_create(
            plan=self.plan_pro, 
            feature=self.feature, 
            defaults={'limit': 100}
        )

    def test_list_plans(self):
        print("\n" + "="*60)
        print("TEST: List Available Plans")
        print("="*60)
        print(f"  Action: GET /api/subscriptions/plans/")
        
        response = self.client.get('/api/subscriptions/plans/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(f"  ✓ Status: {response.status_code} OK")
        
        self.assertEqual(len(response.data), 2)
        print(f"  ✓ Plans returned: {len(response.data)}")
        
        for plan in response.data:
            print(f"    - {plan['name']}: ₹{plan['price']}")
        
        print("  " + "="*58)
        print("  PASSED ✓")
        print("="*60)

    def test_subscribe(self):
        print("\n" + "="*60)
        print("TEST: Subscribe to a Plan")
        print("="*60)
        print(f"  User: {self.user.username}")
        print(f"  Plan: {self.plan_basic.name} (₹{self.plan_basic.price})")
        print(f"  Action: POST /api/subscriptions/subscribe/")
        
        response = self.client.post('/api/subscriptions/subscribe/', {'plan_id': self.plan_basic.id})
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print(f"  ✓ Status: {response.status_code} CREATED")
        
        self.assertTrue(Subscription.objects.filter(user=self.user, plan=self.plan_basic, active=True).exists())
        print(f"  ✓ Subscription created in database")
        print(f"  ✓ Subscription is active")
        print("  " + "="*58)
        print("  PASSED ✓")
        print("="*60)

    def test_upgrade_plan(self):
        print("\n" + "="*60)
        print("TEST: Upgrade Subscription Plan")
        print("="*60)
        
        # Subscribe to Basic first
        Subscription.objects.create(user=self.user, plan=self.plan_basic)
        print(f"  Setup: User subscribed to {self.plan_basic.name} (₹{self.plan_basic.price})")
        print(f"  Action: Upgrading to {self.plan_pro.name} (₹{self.plan_pro.price})")
        print(f"  Request: PUT /api/subscriptions/subscribe/")
        
        # Upgrade to Pro
        response = self.client.put('/api/subscriptions/subscribe/', {'plan_id': self.plan_pro.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(f"  ✓ Status: {response.status_code} OK")
        
        self.assertTrue(Subscription.objects.filter(user=self.user, plan=self.plan_pro, active=True).exists())
        print(f"  ✓ Plan upgraded successfully")
        print(f"  ✓ New subscription active in database")
        print("  " + "="*58)
        print("  PASSED ✓")
        print("="*60)
