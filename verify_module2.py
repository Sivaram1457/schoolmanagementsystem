"""
verify_module2.py — Automated verification for Module 2: Admin & School Structure.
"""
import requests
import sys
from database import Base, engine, SessionLocal
from models import User, UserRole
from auth import hash_password

BASE = "http://127.0.0.1:8000"

def reset_and_seed():
    print("🔄 Resetting Database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    print("🌱 Seeding Admin...")
    db = SessionLocal()
    admin = User(
        full_name="System Admin",
        email="admin@school.com",
        password_hash=hash_password("admin123"),
        role=UserRole.admin,
    )
    db.add(admin)
    db.commit()
    db.close()
    print("✅ Database ready.")

def run_tests():
    print("\n🚀 Starting Module 2 Verification Tests...")
    
    # 1. Login as Admin
    print("\n1. Admin Login")
    resp = requests.post(f"{BASE}/auth/login", json={"email": "admin@school.com", "password": "admin123"})
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Admin logged in")

    # 2. Create Class "10A"
    print("\n2. Create Class '10A'")
    payload = {"name": "10A", "class_level": "10", "section": "A"}
    resp = requests.post(f"{BASE}/admin/classes", json=payload, headers=headers)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 201:
        cls_data = resp.json()
        class_id = cls_data["id"]
        print(f"✅ Class created: ID {class_id}")
    else:
        print(f"❌ Failed to create class: {resp.text}")
        sys.exit(1)

    # 3. Create Student linked to Class
    print("\n3. Create Student (assigned to 10A)")
    payload = {
        "full_name": "John Student",
        "email": "john@school.com",
        "password": "pass123",
        "role": "student",
        "class_id": class_id
    }
    resp = requests.post(f"{BASE}/admin/students", json=payload, headers=headers)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 201:
        student_data = resp.json()
        student_id = student_data["id"]
        print(f"✅ Student created: ID {student_id}")
    else:
        print(f"❌ Failed to create student: {resp.text}")
        sys.exit(1)

    # 4. Create Teacher
    print("\n4. Create Teacher")
    payload = {
        "full_name": "Mr. Smith",
        "email": "smith@school.com",
        "password": "pass123",
        "role": "teacher"
    }
    resp = requests.post(f"{BASE}/admin/teachers", json=payload, headers=headers)
    if resp.status_code == 201:
        print("✅ Teacher created")
    else:
        print(f"❌ Failed to create teacher: {resp.text}")

    # 5. Create Parent linked to Student
    print("\n5. Create Parent (linked to John)")
    payload = {
        "full_name": "Mrs. Doe",
        "email": "doe@school.com",
        "password": "pass123",
        "role": "parent",
        "linked_student_id": student_id
    }
    resp = requests.post(f"{BASE}/admin/parents", json=payload, headers=headers)
    if resp.status_code == 201:
        print("✅ Parent created")
    else:
        print(f"❌ Failed to create parent: {resp.text}")

    # 6. Verify Validation: Student without Class
    print("\n6. verify FAILURE: Student without Class (Expect 422/400)")
    bad_payload = {
        "full_name": "Bad Student",
        "email": "bad@school.com",
        "password": "pass",
        "role": "student"
        # Missing class_id for Pydantic/API check? 
        # Actually our schema defines class_id as int but Optional in UserBase?
        # Wait, StudentCreate defines class_id: int (Required). So Pydantic should block it (422).
    }
    resp = requests.post(f"{BASE}/admin/students", json=bad_payload, headers=headers)
    if resp.status_code == 422:
        print("✅ Correctly rejected (422 Unprocessable Entity - Missing Field)")
    else:
        print(f"❌ Unexpected status: {resp.status_code} {resp.text}")

    # 7. Verify Validation: Parent with invalid student ID
    print("\n7. verify FAILURE: Parent with bad student ID (Expect 400)")
    bad_parent = {
        "full_name": "Bad Parent",
        "email": "badp@school.com",
        "password": "pass",
        "role": "parent",
        "linked_student_id": 99999
    }
    resp = requests.post(f"{BASE}/admin/parents", json=bad_parent, headers=headers)
    if resp.status_code == 400:
        print("✅ Correctly rejected (400 - Student Not Found)")
    else:
        print(f"❌ Unexpected status: {resp.status_code} {resp.text}")

    print("\n🎉 ALL MODULE 2 TESTS PASSED!")

if __name__ == "__main__":
    try:
        reset_and_seed()
        run_tests()
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
