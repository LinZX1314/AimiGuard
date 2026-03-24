import requests
import json

base_url = "http://127.0.0.1:5000"
login_url = f"{base_url}/api/v1/auth/login"
screen_url = f"{base_url}/api/v1/overview/screen"

data = {"username": "admin", "password": "admin123"}
headers = {"Content-Type": "application/json"}

try:
    print("Testing Login...")
    login_resp = requests.post(login_url, json=data, headers=headers)
    print(f"Login Status: {login_resp.status_code}")
    if login_resp.status_code == 200:
        token = login_resp.json().get("access_token")
        print("Login Success. Testing Overview Screen...")
        auth_headers = {"Authorization": f"Bearer {token}"}
        screen_resp = requests.get(screen_url, headers=auth_headers)
        print(f"Screen Status: {screen_resp.status_code}")
        
        print("Retrieving Backend Logs...")
        logs_url = f"{base_url}/api/logs"
        logs_resp = requests.get(logs_url)
        print(f"Logs Status: {logs_resp.status_code}")
        if logs_resp.status_code == 200:
            logs = logs_resp.json()
            for log in logs[-10:]:
                print(f"[{log.get('time')}] [{log.get('level')}] {log.get('message')}")
        
    else:
        print(f"Login Failed: {login_resp.text}")
except Exception as e:
    print(f"Error: {e}")
