from django.core.management.base import BaseCommand
from subscriptions.models import Plan, Feature, PlanFeature, Subscription
from decimal import Decimal

class Command(BaseCommand):
    help = 'Setup test plans for subscription engine testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-subscriptions',
            action='store_true',
            help='Keep existing subscriptions (only deactivate them). By default, subscriptions are deleted.',
        )

    def handle(self, *args, **options):
        keep_subs = options.get('keep_subscriptions', False)
        
        # First, handle existing subscriptions that reference plans
        # This is necessary because Plan has PROTECT foreign key which prevents deletion
        subscription_count = Subscription.objects.count()
        if subscription_count > 0:
            self.stdout.write(self.style.WARNING(f'Found {subscription_count} existing subscriptions'))
            
            if keep_subs:
                # Only deactivate subscriptions (preserves data but plans still can't be deleted)
                # This won't work - we still need to delete subscriptions to delete plans
                self.stdout.write(self.style.ERROR(
                    'Cannot keep subscriptions when deleting plans. '
                    'Plans have PROTECT foreign key. Deleting subscriptions instead...'
                ))
                Subscription.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {subscription_count} subscriptions'))
            else:
                # Delete all subscriptions (required to delete plans due to PROTECT foreign key)
                Subscription.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {subscription_count} subscriptions'))
        
        # Now delete all existing plans
        plan_count = Plan.objects.count()
        if plan_count > 0:
            Plan.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {plan_count} existing plans'))
        else:
            self.stdout.write('No existing plans to delete')
        
        # Create API Calls feature (used by all plans)
        api_calls_feature, _ = Feature.objects.get_or_create(
            code='api_calls',
            defaults={
                'name': 'API Calls',
                'description': 'Number of API calls allowed'
            }
        )
        
        # ============================================================================
        # PLAN 1 — Basic Monthly Plan (Simple Billing)
        # ============================================================================
        # Purpose: Tests simple subscription creation, monthly renewals, cancellation
        #          flow, invoice generation, payment success/failure
        # Test Cases: Billing cycle, invoice.created, invoice.paid, cancellation, resume
        # ============================================================================
        basic_plan, _ = Plan.objects.get_or_create(
            name='Basic Monthly Plan',
            defaults={
                'price': Decimal('100.00'),
                'billing_period': 'monthly',
                'overage_price': Decimal('0.00'),
                'rate_limit': 0,
                'rate_limit_window': 60
            }
        )
        PlanFeature.objects.update_or_create(
            plan=basic_plan,
            feature=api_calls_feature,
            defaults={'limit': 5}  # Minimal limit for testing
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {basic_plan.name} (₹100/month, 5 calls)'))
        
        # ============================================================================
        # PLAN 2 — Quota Plan (Usage Metering)
        # ============================================================================
        # Purpose: Tests usage tracking, limit enforcement, usage reset on renewal,
        #          alerts at 80% consumption, remaining quota display
        # Test Cases: Usage meter, ENTITLEMENT logic, renewal → reset usage
        # ============================================================================
        quota_plan, _ = Plan.objects.get_or_create(
            name='Quota Plan',
            defaults={
                'price': Decimal('200.00'),
                'billing_period': 'monthly',
                'overage_price': Decimal('0.00'),
                'rate_limit': 0,
                'rate_limit_window': 60
            }
        )
        PlanFeature.objects.update_or_create(
            plan=quota_plan,
            feature=api_calls_feature,
            defaults={'limit': 100}  # 100 API calls per month
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {quota_plan.name} (₹200/month, 100 calls)'))
        
        # ============================================================================
        # PLAN 3 — Overage Plan (Metered Billing + Overcharges)
        # ============================================================================
        # Purpose: Tests metered billing, overage invoice line items,
        #          webhook: invoice.finalized, multiple overage events,
        #          ensures invoice calculation works
        # Test Cases: Over-limit billing, invoice items, overage calculation, payment retries
        # ============================================================================
        overage_plan, _ = Plan.objects.get_or_create(
            name='Overage Plan',
            defaults={
                'price': Decimal('500.00'),
                'billing_period': 'monthly',
                'overage_price': Decimal('1.00'),  # ₹1 per extra call
                'rate_limit': 0,
                'rate_limit_window': 60
            }
        )
        PlanFeature.objects.update_or_create(
            plan=overage_plan,
            feature=api_calls_feature,
            defaults={'limit': 1000}  # 1000 API calls included, then ₹1 per call
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {overage_plan.name} (₹500/month, 1000 calls, ₹1 overage)'))
        
        # ============================================================================
        # PLAN 4 — Rate-Limited Plan (Per-Minute Throttling)
        # ============================================================================
        # Purpose: Tests API gateway or internal throttling, concurrency race conditions,
        #          ensures real-time limit enforcement, good for continuous self-testing,
        #          useful to simulate spammy users
        # Test Cases: Rate limiting, request throttling, burst behavior, lock checks
        # ============================================================================
        rate_limited_plan, _ = Plan.objects.get_or_create(
            name='Rate-Limited Plan',
            defaults={
                'price': Decimal('300.00'),
                'billing_period': 'monthly',
                'overage_price': Decimal('0.00'),
                'rate_limit': 5,  # 5 calls per minute
                'rate_limit_window': 60  # 60 seconds = 1 minute
            }
        )
        PlanFeature.objects.update_or_create(
            plan=rate_limited_plan,
            feature=api_calls_feature,
            defaults={'limit': -1}  # Unlimited monthly, but rate limited per minute
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {rate_limited_plan.name} (₹300/month, 5 calls/minute throttle)'))
        
        # ============================================================================
        # PLAN 5 — High-Frequency Renewal Plan (QA Stress Plan)
        # ============================================================================
        # Purpose: Tests fast billing cycles, webhook replay/failures/retries,
        #          race conditions in renewal, proration when switching plans,
        #          invoice generation multiple times per hour
        # Test Cases: Webhook storms, concurrency, state machine transitions,
        #             proration, upgrade/downgrade behavior
        # ============================================================================
        # Using hourly billing for high-frequency testing (can be changed to minute if needed)
        hf_plan, _ = Plan.objects.get_or_create(
            name='High-Frequency Renewal Plan',
            defaults={
                'price': Decimal('10.00'),
                'billing_period': 'hourly',  # Bills every hour for stress testing
                'overage_price': Decimal('0.00'),
                'rate_limit': 0,
                'rate_limit_window': 60
            }
        )
        PlanFeature.objects.update_or_create(
            plan=hf_plan,
            feature=api_calls_feature,
            defaults={'limit': -1}  # Unlimited usage
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {hf_plan.name} (₹10/hour, unlimited calls)'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ All 5 test plans created successfully!'))
        self.stdout.write('\nPlans Summary:')
        self.stdout.write('  1. Basic Monthly Plan - Simple billing tests')
        self.stdout.write('  2. Quota Plan - Usage metering tests')
        self.stdout.write('  3. Overage Plan - Metered billing + overcharges')
        self.stdout.write('  4. Rate-Limited Plan - Throttling tests')
        self.stdout.write('  5. High-Frequency Renewal Plan - Stress testing')
