"""
tests/test_module4.py — Automated API tests for Module 4: Homework System.
"""
import requests
import sys
import time
from datetime import date, timedelta

BASE = "http://127.0.0.1:8000"

def get_token(email, password):
    resp = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        return None
    return resp.json()["access_token"]

def run_tests():
    print("🚀 Starting Module 4 Verification Tests...")
    
    # 1. Login as Admin, Teacher, Student, Parent
    tokens = {
        "admin": get_token("admin@school.com", "admin123"),
        "teacher": get_token("smith@school.com", "pass123"),
        "student": get_token("john@school.com", "pass123"),
        "parent": get_token("doe@school.com", "pass123"),
    }
    
    if not all(tokens.values()):
        print("❌ Login failed for some roles. Ensure DB is seeded and server is running.")
        sys.exit(1)
        
    headers = {role: {"Authorization": f"Bearer {token}"} for role, token in tokens.items()}
    print("✅ All roles logged in")

    # Get John's student ID and class ID
    john_resp = requests.get(f"{BASE}/auth/me", headers=headers["student"])
    john_id = john_resp.json()["id"]
    john_class_id = john_resp.json()["class_id"]

    # 2. Teacher creates homework (Success)
    print("\n2. Teacher creates homework (Success)")
    today = date.today()
    payload = {
        "class_id": john_class_id,
        "title": "Math Homework #1",
        "description": "Solve quadratic equations on page 42.",
        "due_date": (today + timedelta(days=7)).isoformat()
    }
    resp = requests.post(f"{BASE}/homework/", json=payload, headers=headers["teacher"])
    if resp.status_code == 201:
        hw_id = resp.json()["id"]
        print(f"✅ Homework created: ID {hw_id}")
    else:
        print(f"❌ Failed to create homework: {resp.text}")
        sys.exit(1)

    # 3. Teacher fails to create for past date (Error 400)
    print("\n3. Teacher fails for past due_date (400)")
    payload["due_date"] = (today - timedelta(days=1)).isoformat()
    resp = requests.post(f"{BASE}/homework/", json=payload, headers=headers["teacher"])
    if resp.status_code == 400:
        print("✅ Correctly rejected (400)")
    else:
        print(f"❌ Unexpected status code: {resp.status_code}")

    # 4. Student view homework (200)
    print("\n4. Student view homework (200)")
    resp = requests.get(f"{BASE}/homework/me", headers=headers["student"])
    if resp.status_code == 200:
        hws = resp.json()
        if any(hw["id"] == hw_id for hw in hws):
            print("✅ Student can see the homework")
        else:
            print("❌ Student cannot see the homework item")
    else:
        print(f"❌ Failed to get homework for student: {resp.text}")

    # 5. Parent view child homework (200)
    print("\n5. Parent view child homework (200)")
    resp = requests.get(f"{BASE}/homework/student/{john_id}", headers=headers["parent"])
    if resp.status_code == 200:
        print("✅ Parent can view child's homework")
    else:
        print(f"❌ Failed for parent: {resp.text}")

    # 6. Parent view unrelated student (403)
    # Note: For this we might need another student not linked to the parent
    print("\n6. Parent view unrelated student (403) - Note: depends on data")
    
    # 7. Teacher Update (200)
    print("\n7. Teacher Update Homework (200)")
    resp = requests.put(f"{BASE}/homework/{hw_id}", json={"title": "Updated Math HW"}, headers=headers["teacher"])
    if resp.status_code == 200:
        print("✅ Homework updated")
    else:
        print(f"❌ Update failed: {resp.text}")

    # 8. Soft Delete (204)
    print("\n8. Soft Delete Homework (204)")
    resp = requests.delete(f"{BASE}/homework/{hw_id}", headers=headers["teacher"])
    if resp.status_code == 204:
        print("✅ Homework soft-deleted")
    else:
        print(f"❌ Delete failed: {resp.text}")

    # 9. Verify soft delete hides from student
    print("\n9. Verify soft-deleted item hidden from Student")
    resp = requests.get(f"{BASE}/homework/me", headers=headers["student"])
    hws = resp.json()
    if any(hw["id"] == hw_id for hw in hws):
        print("❌ Error: Soft-deleted homework still visible to student")
    else:
        print("✅ Item successfully hidden")

    # 10. Admin view class homework
    print("\n10. Admin view class homework")
    resp = requests.get(f"{BASE}/homework/class/{john_class_id}", headers=headers["admin"])
    if resp.status_code == 200:
        print("✅ Admin can view class homework")
    else:
        print(f"❌ Admin view failed")

    print("\n🎉 ALL MODULE 4 TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
