import requests
from datetime import date, timedelta

BASE = 'http://127.0.0.1:8000'

def test():
    # 1. Login
    roles = [
        ('admin', 'admin@school.com', 'admin123'),
        ('teacher', 'smith@school.com', 'pass123'),
        ('student', 'john@school.com', 'pass123'),
        ('parent', 'doe@school.com', 'pass123')
    ]
    tokens = {}
    for role, email, password in roles:
        resp = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            tokens[role] = resp.json()["access_token"]
            print(f"✅ {role.capitalize()} logged in")
        else:
            print(f"❌ {role.capitalize()} login failed: {resp.text}")
            return

    headers = {r: {"Authorization": f"Bearer {t}"} for r, t in tokens.items()}

    # 2. Get Student Info
    john = requests.get(f"{BASE}/auth/me", headers=headers["student"]).json()
    john_id = john["id"]
    john_class_id = john["class_id"]
    print(f"ℹ️ Student ID: {john_id}, Class ID: {john_class_id}")

    # 3. Create Homework
    payload = {
        "class_id": john_class_id,
        "title": "Verif Homework",
        "description": "Manual verification desc",
        "due_date": (date.today() + timedelta(days=5)).isoformat()
    }
    resp = requests.post(f"{BASE}/homework/", json=payload, headers=headers["teacher"])
    if resp.status_code == 201:
        hw = resp.json()
        hw_id = hw["id"]
        print(f"✅ Homework created: ID {hw_id}")
    else:
        print(f"❌ Failed to create homework: {resp.text}")
        return

    # 4. Verify Visibility (Student)
    me_hws = requests.get(f"{BASE}/homework/me", headers=headers["student"]).json()
    visible = any(h["id"] == hw_id for h in me_hws)
    print(f"✅ Student can see homework: {visible}")

    # 5. Verify Visibility (Parent)
    parent_hws = requests.get(f"{BASE}/homework/student/{john_id}", headers=headers["parent"]).json()
    parent_visible = any(h["id"] == hw_id for h in parent_hws)
    print(f"✅ Parent can see student's homework: {parent_visible}")

    # 6. Delete (Soft)
    del_resp = requests.delete(f"{BASE}/homework/{hw_id}", headers=headers["teacher"])
    print(f"✅ Homework status on delete: {del_resp.status_code}")

    # 7. Verify Hidden (Student)
    me_hws_after = requests.get(f"{BASE}/homework/me", headers=headers["student"]).json()
    hidden = not any(h["id"] == hw_id for h in me_hws_after)
    print(f"✅ Homework hidden from student after soft-delete: {hidden}")

    print("🎉 Verification Finished!")

if __name__ == "__main__":
    test()
