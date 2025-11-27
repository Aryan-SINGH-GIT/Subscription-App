import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subscriptionEngine.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

BASE_URL = 'http://127.0.0.1:8000'

def test_profile_update():
    print("=" * 60)
    print("Testing User Profile Update")
    print("=" * 60)
    
    # 1. Create/Get test user
    print("\n1. Setting up test user...")
    user, created = User.objects.get_or_create(
        username='profile_test_user',
        defaults={'email': 'profile@test.com'}
    )
    if created:
        user.set_password('password123')
        user.save()
    print(f"✓ User: {user.username}")
    
    # 2. Login to get token
    print("\n2. Logging in...")
    response = requests.post(f'{BASE_URL}/api/auth/token/', data={
        'username': 'profile_test_user',
        'password': 'password123'
    })
    
    if response.status_code != 200:
        print(f"✗ Login failed: {response.text}")
        return
    
    token = response.json()['access']
    print(f"✓ Got token: {token[:20]}...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    # 3. Get current profile
    print("\n3. Getting current profile...")
    response = requests.get(f'{BASE_URL}/api/auth/profile/', headers=headers)
    
    if response.status_code == 200:
        profile = response.json()
        print(f"✓ Current profile:")
        print(f"  - Username: {profile.get('username')}")
        print(f"  - Email: {profile.get('email')}")
        print(f"  - Webhook URL: {profile.get('webhook_url') or '(not set)'}")
    else:
        print(f"✗ Failed to get profile: {response.text}")
        return
    
    # 4. Update webhook URL
    print("\n4. Updating webhook URL...")
    new_webhook_url = 'https://webhook.site/2e2ceb7c-9e07-4de0-ac77-6239bb114fc3'
    response = requests.patch(
        f'{BASE_URL}/api/auth/profile/',
        headers=headers,
        json={'webhook_url': new_webhook_url}
    )
    
    if response.status_code == 200:
        updated_profile = response.json()
        print(f"✓ Profile updated!")
        print(f"  - New Webhook URL: {updated_profile.get('webhook_url')}")
        
        # Verify in DB
        user.refresh_from_db()
        assert user.webhook_url == new_webhook_url
        print("✓ Verified in database")
    else:
        print(f"✗ Failed to update: {response.text}")
        return
    
    # 5. Try to update username (should fail)
    print("\n5. Testing read-only username...")
    response = requests.patch(
        f'{BASE_URL}/api/auth/profile/',
        headers=headers,
        json={'username': 'hacker'}
    )
    
    # Refresh and check
    user.refresh_from_db()
    if user.username == 'profile_test_user':
        print("✓ Username correctly protected (read-only)")
    else:
        print("✗ Username was changed (security issue!)")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    test_profile_update()
