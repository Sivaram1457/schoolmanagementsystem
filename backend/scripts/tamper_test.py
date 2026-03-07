import requests
import json

BASE = "http://127.0.0.1:8000"

print("--- JWT TAMPER TEST ---")

# 1. Login
resp = requests.post(f"{BASE}/auth/login", json={"email": "admin@school.com", "password": "admin123"})
if resp.status_code != 200:
    print(f"❌ Login failed! {resp.text}")
    exit(1)

token = resp.json()["access_token"]
print(f"✅ Got valid token: {token[:20]}...")

# 2. Tamper the token (change last char)
# JWT is header.payload.signature
# Changing last char of signature invalidates it
tampered_token = token[:-1] + ("A" if token[-1] != "A" else "B")
print(f"😈 Tampered token:  {tampered_token[:20]}... (modified last char)")

# 3. Call protected route
resp = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})

print(f"   Status Code: {resp.status_code}")
print(f"   Response:    {resp.text}")

if resp.status_code == 401:
    print("\n✅ SUCCESS: Server REJECTED the tampered token!")
else:
    print("\n❌ FAILURE: Server ACCEPTED the tampered token! (Safety Check FAILED)")
