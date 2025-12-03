from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, PlanFeature
from metering.models import Invoice
from metering.invoice_generator import generate_invoice_pdf, generate_invoice_number
from metering.services import get_usage
from django.core.files.base import ContentFile
from dateutil.relativedelta import relativedelta
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Generate a test invoice for the current user or a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username to generate invoice for (default: current logged in user)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate invoices for all users with active subscriptions',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        generate_all = options.get('all')

        if generate_all:
            subscriptions = Subscription.objects.filter(active=True).select_related('user', 'plan')
            self.stdout.write(f'Generating invoices for {subscriptions.count()} active subscriptions...')
            
            for sub in subscriptions:
                self.generate_invoice_for_subscription(sub)
        elif username:
            try:
                user = User.objects.get(username=username)
                subscription = Subscription.objects.filter(user=user, active=True).first()
                
                if not subscription:
                    self.stdout.write(self.style.ERROR(f'No active subscription found for user: {username}'))
                    return
                
                self.generate_invoice_for_subscription(subscription)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User not found: {username}'))
        else:
            self.stdout.write(self.style.ERROR('Please provide --username or use --all to generate for all users'))
            self.stdout.write('Example: python manage.py generate_test_invoice --username myuser')
            self.stdout.write('Or: python manage.py generate_test_invoice --all')

    def generate_invoice_for_subscription(self, subscription):
        """Generate invoice for a specific subscription"""
        user = subscription.user
        plan = subscription.plan
        
        today = timezone.now().date()
        period_end = today
        period_start = today - relativedelta(months=1)
        
        # Check if invoice already exists for this period
        existing = Invoice.objects.filter(
            user=user,
            subscription=subscription,
            period_start=period_start,
            period_end=period_end
        ).first()
        
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'Invoice already exists for {user.username} for period {period_start} to {period_end}'
                )
            )
            return
        
        # Calculate usage for features
        invoice_items = []
        total_cost = plan.price
        
        for pf in plan.planfeature_set.all():
            used = get_usage(user.id, pf.feature.code)
            invoice_items.append({
                'feature': pf.feature.name,
                'used': used,
                'limit': pf.limit
            })
        
        # Generate invoice number
        invoice_number = generate_invoice_number(user.id, today)
        
        # Create invoice
        invoice = Invoice.objects.create(
            user=user,
            subscription=subscription,
            invoice_number=invoice_number,
            invoice_date=today,
            period_start=period_start,
            period_end=period_end,
            subtotal=total_cost,
            tax=Decimal('0.00'),
            total=total_cost,
            status='finalized',
            items=invoice_items
        )
        
        # Generate PDF
        try:
            pdf_content = generate_invoice_pdf(invoice)
            invoice.pdf_file.save(
                f'{invoice_number}.pdf',
                ContentFile(pdf_content),
                save=True
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Generated invoice {invoice_number} for {user.username} (₹{total_cost})'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error generating PDF for invoice {invoice_number}: {e}')
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created invoice {invoice_number} for {user.username} (PDF generation failed)'
                )
            )

