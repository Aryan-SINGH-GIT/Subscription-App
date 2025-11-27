import requests
import time

BASE_URL = 'http://127.0.0.1:8000'

def register_and_login(username, email):
    # Register
    print(f"[{username}] Registering...")
    requests.post(f'{BASE_URL}/api/auth/register/', data={
        'username': username,
        'email': email,
        'password': 'password123',
        'password_confirm': 'password123'
    })
    
    # Login
    print(f"[{username}] Logging in...")
    resp = requests.post(f'{BASE_URL}/api/auth/token/', data={
        'username': username,
        'password': 'password123'
    })
    if resp.status_code != 200:
        print(f"[{username}] Login failed: {resp.text}")
        return None
    return resp.json()['access']

def subscribe(token, plan_name):
    # Get Plan ID
    resp = requests.get(f'{BASE_URL}/api/subscriptions/plans/')
    plans = resp.json()
    plan_id = next((p['id'] for p in plans if p['name'] == plan_name), None)
    
    if not plan_id:
        print(f"Plan {plan_name} not found")
        return
        
    # Subscribe
    print(f"Subscribing to {plan_name}...")
    headers = {'Authorization': f'Bearer {token}'}
    requests.post(f'{BASE_URL}/api/subscriptions/subscribe/', headers=headers, data={'plan_id': plan_id})

def use_feature(token, username, count):
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Feature-Code': 'demo_feature'
    }
    
    print(f"\n[{username}] Using feature {count} times...")
    for i in range(count):
        resp = requests.post(f'{BASE_URL}/api/metering/event/', headers=headers, data={
            'feature_code': 'demo_feature',
            'event_id': f'{username}_{time.time()}_{i}'
        })
        status = "Allowed" if resp.status_code == 201 else f"Blocked ({resp.status_code})"
        print(f"  Request {i+1}: {status}")

def run_demo():
    print("--- Setting up Demo Data ---")
    # We assume setup_demo_data has been run
    
    # User A - Basic Plan (Limit 5)
    token_a = register_and_login('user_basic', 'basic@test.com')
    if token_a:
        subscribe(token_a, 'Basic Plan')
        use_feature(token_a, 'user_basic', 7) # Should fail after 5

    # User B - Pro Plan (Limit 10)
    token_b = register_and_login('user_pro', 'pro@test.com')
    if token_b:
        subscribe(token_b, 'Pro Plan')
        use_feature(token_b, 'user_pro', 7) # Should all succeed

if __name__ == '__main__':
    run_demo()
