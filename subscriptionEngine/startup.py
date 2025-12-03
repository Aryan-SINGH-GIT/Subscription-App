"""
Startup script to run migrations and setup on Render deployment
This runs automatically when the app starts
"""
import os
import sys
import django

def run_startup_tasks():
    """Run migrations and setup tasks on startup"""
    if os.environ.get('SKIP_STARTUP_TASKS') == 'true':
        return
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subscriptionEngine.settings')
    django.setup()
    
    from django.core.management import call_command
    from django.db import connection
    
    try:
        # Check if database is accessible
        connection.ensure_connection()
        
        # Run migrations
        print("Running migrations...")
        call_command('migrate', verbosity=0, interactive=False)
        
        # Check if plans exist, if not create them
        from subscriptions.models import Plan
        if Plan.objects.count() == 0:
            print("Setting up demo data...")
            call_command('setup_demo_data', verbosity=0)
        
        print("Startup tasks completed successfully")
    except Exception as e:
        print(f"Startup tasks error (non-critical): {e}")
        # Don't fail the app if migrations fail

# Run on import (when app starts)
if __name__ == '__main__':
    run_startup_tasks()

