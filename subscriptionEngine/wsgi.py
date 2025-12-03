"""
WSGI config for subscriptionEngine project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subscriptionEngine.settings')

# Get WSGI application first (Django must be initialized)
from django.core.wsgi import get_wsgi_application

# Run migrations automatically on startup (only once per deployment)
# This allows free tier deployment without Shell access
_startup_done = False

def run_startup_tasks():
    """Run migrations and setup on first app load"""
    global _startup_done
    if _startup_done:
        return
    
    # Skip if explicitly disabled
    if os.environ.get('SKIP_STARTUP_TASKS') == 'true':
        return
    
    try:
        # Django is already initialized via get_wsgi_application()
        from django.core.management import call_command
        from django.db import connection
        from django.conf import settings
        
        # Check if database is configured
        db_name = settings.DATABASES['default'].get('NAME')
        if not db_name or db_name == '':
            print("Database not configured yet, skipping migrations", file=sys.stderr)
            return
        
        # Test database connection
        try:
            connection.ensure_connection()
        except Exception as e:
            print(f"Database connection failed: {e}", file=sys.stderr)
            return
        
        # Check if migrations are needed by trying to query a table
        try:
            from subscriptions.models import Plan
            Plan.objects.count()  # This will fail if table doesn't exist
            print("Tables exist, skipping migrations", file=sys.stderr)
            _startup_done = True
            return
        except:
            # Tables don't exist, run migrations
            pass
        
        # Run migrations
        print("Running migrations on startup...", file=sys.stderr)
        call_command('migrate', verbosity=1, interactive=False)
        
        # Setup demo data if no plans exist
        try:
            from subscriptions.models import Plan
            if Plan.objects.count() == 0:
                print("Setting up demo data...", file=sys.stderr)
                call_command('setup_demo_data', verbosity=0)
        except Exception as e:
            print(f"Demo data setup failed: {e}", file=sys.stderr)
        
        _startup_done = True
        print("Startup tasks completed", file=sys.stderr)
    except Exception as e:
        # Don't fail app startup if migrations fail
        import traceback
        print(f"Startup tasks error (non-critical): {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)

# Get WSGI application (this initializes Django)
application = get_wsgi_application()

# Run startup tasks after Django is initialized
try:
    run_startup_tasks()
except:
    pass  # Ignore errors during startup
