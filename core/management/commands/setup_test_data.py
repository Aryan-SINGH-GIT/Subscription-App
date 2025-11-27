from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from subscriptions.models import Plan, Feature, PlanFeature, Subscription

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup test data for load testing'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(username='loadtestuser')
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write('Created user loadtestuser')
            
        feature, _ = Feature.objects.get_or_create(code='api_calls', defaults={'name': 'API Calls'})
        plan, _ = Plan.objects.get_or_create(name='LoadTestPlan', defaults={'price': 100})
        
        PlanFeature.objects.get_or_create(plan=plan, feature=feature, defaults={'limit': 10000})
        
        Subscription.objects.get_or_create(user=user, defaults={'plan': plan})
        
        self.stdout.write(self.style.SUCCESS('Test data setup complete'))
