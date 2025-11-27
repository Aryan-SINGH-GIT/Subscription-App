import requests
import time
import threading

BASE_URL = 'http://127.0.0.1:8000'

def get_token():
    # Register or Login
    # Since we don't have a register endpoint exposed easily (admin only), 
    # we assume a user exists or we create one via shell.
    # For this script, let's assume we can get a token for 'testuser' created in tests? 
    # No, tests use a separate DB.
    # We need to create a user in the real DB first.
    
    try:
        response = requests.post(f'{BASE_URL}/api/auth/token/', data={
            'username': 'loadtestuser',
            'password': 'password123'
        })
        if response.status_code == 200:
            return response.json()['access']
    except:
        pass
    return None

def run_load_test(token, num_requests=100):
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Feature-Code': 'api_calls'
    }
    
    latencies = []
    
    for _ in range(num_requests):
        start = time.time()
        # We hit a dummy endpoint or just the usage event endpoint
        # Let's hit usage-summary as it's a GET and safe-ish, but middleware runs on all requests?
        # Middleware checks X-Feature-Code.
        # If we hit a non-existent endpoint, middleware still runs? Yes.
        requests.get(f'{BASE_URL}/api/metering/summary/', headers=headers)
        end = time.time()
        latencies.append((end - start) * 1000) # ms
        
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    
    print(f"Average Latency: {avg_latency:.2f}ms")
    print(f"P95 Latency: {p95_latency:.2f}ms")

if __name__ == '__main__':
    print("Starting load test...")
    token = get_token()
    if token:
        run_load_test(token)
    else:
        print("Failed to get token")
