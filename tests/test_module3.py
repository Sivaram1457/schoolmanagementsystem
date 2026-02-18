"""
tests/test_module3.py — Integration tests for Module 3 (Attendance).
"""

import requests
from datetime import date

BASE_URL = "http://127.0.0.1:8000"

def get_token(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]

def test_attendance_flow():
    import time
    ts = int(time.time())

    # 1. Setup Data - Use existing admin to create class and teacher/student
    admin_token = get_token("admin@school.com", "admin123")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Class
    class_name = f"AttendTest_{ts}"
    class_resp = requests.post(f"{BASE_URL}/admin/classes", headers=headers, json={
        "name": class_name, "class_level": "10", "section": "T"
    })
    if class_resp.status_code != 201:
        print(f"Class Creation Failed: {class_resp.status_code} - Body: {class_resp.text}")
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    # Create Teacher
    teacher_email = f"teacher_{ts}@school.com"
    teacher_resp = requests.post(f"{BASE_URL}/admin/teachers", headers=headers, json={
        "full_name": "Teacher Att", "email": teacher_email, "password": "password123"
    })
    assert teacher_resp.status_code == 201
    
    # Create Student
    student_email = f"student_{ts}@school.com"
    student_resp = requests.post(f"{BASE_URL}/admin/students", headers=headers, json={
        "full_name": "Student Att", "email": student_email, "password": "password123", "class_id": class_id
    })
    assert student_resp.status_code == 201
    student_id = student_resp.json()["id"]

    # Create Parent and link student
    parent_email = f"parent_{ts}@school.com"
    parent_resp = requests.post(f"{BASE_URL}/admin/parents", headers=headers, json={
        "full_name": "Parent Att", "email": parent_email, "password": "password123", "student_ids": [student_id]
    })
    assert parent_resp.status_code == 201

    # 2. Test Teacher Bulk Mark
    teacher_token = get_token(teacher_email, "password123")
    t_headers = {"Authorization": f"Bearer {teacher_token}"}
    
    today = date.today().isoformat()
    bulk_payload = {
        "class_id": class_id,
        "date": today,
        "students": [
            {"student_id": student_id, "status": "present"}
        ]
    }
    
    bulk_resp = requests.post(f"{BASE_URL}/attendance/bulk", headers=t_headers, json=bulk_payload)
    if bulk_resp.status_code != 201:
        print(f"Bulk Marking Failed: {bulk_resp.status_code} - {bulk_resp.text}")
    assert bulk_resp.status_code == 201
    assert len(bulk_resp.json()) == 1
    assert bulk_resp.json()[0]["status"] == "present"

    # 3. Test Unauthorized Access (Student cannot mark)
    student_token = get_token(student_email, "password123")
    s_headers = {"Authorization": f"Bearer {student_token}"}
    fail_bulk = requests.post(f"{BASE_URL}/attendance/bulk", headers=s_headers, json=bulk_payload)
    assert fail_bulk.status_code == 403

    # 4. Test Student /me endpoint
    me_resp = requests.get(f"{BASE_URL}/attendance/me", headers=s_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["attendance_percentage"] == 100.0
    assert me_resp.json()["total_days"] == 1

    # 5. Test Parent /student/{id} endpoint
    parent_token = get_token(parent_email, "password123")
    p_headers = {"Authorization": f"Bearer {parent_token}"}
    
    p_view_resp = requests.get(f"{BASE_URL}/attendance/student/{student_id}", headers=p_headers)
    assert p_view_resp.status_code == 200
    assert p_view_resp.json()["attendance_percentage"] == 100.0

    # 6. Test Duplicate Blocking
    dup_resp = requests.post(f"{BASE_URL}/attendance/bulk", headers=t_headers, json=bulk_payload)
    assert dup_resp.status_code == 400
    assert "already marked" in dup_resp.text.lower()

    # 7. Test Future Date Blocking
    future_date = "2099-01-01"
    future_payload = bulk_payload.copy()
    future_payload["date"] = future_date
    future_resp = requests.post(f"{BASE_URL}/attendance/bulk", headers=t_headers, json=future_payload)
    assert future_resp.status_code == 400
    assert "future date" in future_resp.text.lower()

    print("\n[OK] Module 3 Verification Passed!")

if __name__ == "__main__":
    test_attendance_flow()
