"""Test all three auth endpoints."""
import requests
import json

BASE = "http://127.0.0.1:8000"

# 1. Login as admin
print("=" * 60)
print("1. POST /auth/login")
resp = requests.post(f"{BASE}/auth/login", json={"email": "admin@school.com", "password": "admin123"})
print(f"   Status: {resp.status_code}")
data = resp.json()
print(f"   Response: {json.dumps(data, indent=2)}")
token = data.get("access_token", "")
assert resp.status_code == 200, "Login failed!"
print("   ✓ Login OK\n")

headers = {"Authorization": f"Bearer {token}"}

# 2. Register a new student
print("=" * 60)
print("2. POST /auth/register (admin-only)")
resp = requests.post(f"{BASE}/auth/register", json={
    "full_name": "John Doe",
    "email": "john@school.com",
    "password": "student123",
    "role": "student",
    "class_level": "10th"
}, headers=headers)
print(f"   Status: {resp.status_code}")
print(f"   Response: {json.dumps(resp.json(), indent=2)}")
assert resp.status_code == 201, f"Register failed: {resp.text}"
print("   ✓ Register OK\n")

# 3. Get current user (/auth/me)
print("=" * 60)
print("3. GET /auth/me (protected)")
resp = requests.get(f"{BASE}/auth/me", headers=headers)
print(f"   Status: {resp.status_code}")
print(f"   Response: {json.dumps(resp.json(), indent=2)}")
assert resp.status_code == 200, "Me failed!"
print("   ✓ Me OK\n")

# 4. Unauthorized access (no token)
print("=" * 60)
print("4. GET /auth/me (no token — expect 401)")
resp = requests.get(f"{BASE}/auth/me")
print(f"   Status: {resp.status_code}")
print(f"   Response: {json.dumps(resp.json(), indent=2)}")
assert resp.status_code == 401, "Should have been 401!"
print("   ✓ Unauthorized rejected OK\n")

# 5. Non-admin tries to register (expect 403)
print("=" * 60)
print("5. POST /auth/register as student (expect 403)")
login_resp = requests.post(f"{BASE}/auth/login", json={"email": "john@school.com", "password": "student123"})
student_token = login_resp.json().get("access_token", "")
resp = requests.post(f"{BASE}/auth/register", json={
    "full_name": "Jane Doe",
    "email": "jane@school.com",
    "password": "pass123",
    "role": "student",
}, headers={"Authorization": f"Bearer {student_token}"})
print(f"   Status: {resp.status_code}")
print(f"   Response: {json.dumps(resp.json(), indent=2)}")
assert resp.status_code == 403, f"Should have been 403, got {resp.status_code}"
print("   ✓ Non-admin registration blocked OK\n")

print("=" * 60)
print("ALL TESTS PASSED ✓")
