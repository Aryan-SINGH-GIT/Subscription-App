from django.core.management.base import BaseCommand
from metering.models import MeterEvent
from metering.services import reset_usage, increment_usage

class Command(BaseCommand):
    help = 'Rebuilds Redis counters from MeterEvent logs'

    def handle(self, *args, **options):
        self.stdout.write('Rebuilding counters...')
        
        # This is a naive implementation. In production, you'd want to be more selective.
        # First, clear all known counters? Or just iterate events?
        # Iterating events is safer.
        
        # Group by user and feature?
        # For simplicity, we'll just iterate all events and increment.
        # But we need to reset first to avoid double counting if we run this on existing data.
        
        # Let's find all unique user/feature pairs first.
        events = MeterEvent.objects.all()
        pairs = set()
        for event in events:
            pairs.add((event.user.id, event.feature.code))
            
        for user_id, feature_code in pairs:
            reset_usage(user_id, feature_code)
            
        count = 0
        for event in events:
            increment_usage(event.user.id, event.feature.code)
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} events'))
