import requests
import socket
import sys

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def show_proof():
    host = "127.0.0.1"
    port = 8000
    base_url = f"http://{host}:{port}"
    
    print(f"--- SERVER STATUS CHECK ---")
    
    # 1. Check Port
    if check_port(host, port):
        print(f"✅ Port {port} is OPEN (Server is listening)")
    else:
        print(f"❌ Port {port} is CLOSED (Server NOT running)")
        return

    # 2. Health Check
    try:
        resp = requests.get(f"{base_url}/")
        print(f"\n--- HEALTH CHECK ({base_url}/) ---")
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")

    # 3. Auth Check (Unauthenticated)
    try:
        resp = requests.get(f"{base_url}/auth/me")
        print(f"\n--- AUTH CHECK ({base_url}/auth/me) ---")
        print(f"Status Code: {resp.status_code} (Expected 401)")
        print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"❌ Auth check failed: {e}")

if __name__ == "__main__":
    show_proof()
