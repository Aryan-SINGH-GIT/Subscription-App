from django.core.management.base import BaseCommand
from subscriptions.models import Plan, Feature, PlanFeature

class Command(BaseCommand):
    help = 'Setup demo data with Basic and Pro plans'

    def handle(self, *args, **options):
        feature, _ = Feature.objects.get_or_create(code='demo_feature', defaults={'name': 'Demo Feature'})
        
        # Basic Plan - Limit 5
        basic_plan, _ = Plan.objects.get_or_create(name='Basic Plan', defaults={'price': 10})
        PlanFeature.objects.update_or_create(plan=basic_plan, feature=feature, defaults={'limit': 5})
        
        # Pro Plan - Limit 10
        pro_plan, _ = Plan.objects.get_or_create(name='Pro Plan', defaults={'price': 20})
        PlanFeature.objects.update_or_create(plan=pro_plan, feature=feature, defaults={'limit': 10})
        
        self.stdout.write(self.style.SUCCESS(f'Created Plans: {basic_plan.name} (Limit 5), {pro_plan.name} (Limit 10)'))
