"""
tests/test_phase1.py — Integration tests for Phase 1 (Timetable + Events).

Runs against a live server. Start with:
    uvicorn backend.main:app --reload --port 8000

Then run:
    python -m pytest backend/tests/test_phase1.py -v
"""

import time
import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"
TS = int(time.time())


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_token(email: str, password: str) -> str:
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures (created once per test-session)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    return get_token("admin@school.com", "admin123")


@pytest.fixture(scope="module")
def setup_data(admin_token):
    """
    Create all supporting entities needed by timetable & event tests:
      - 2 classes (A and B)
      - 2 teachers
      - 2 students (one in each class)
      - 1 parent linked to student A
      - 1 subject
      - 1 room
      - 1 period
      - academic mappings: teacher1 → subject → classA
    """
    h = auth(admin_token)

    # Classes
    classA = requests.post(f"{BASE_URL}/admin/classes", headers=h,
        json={"name": f"TT_A_{TS}", "class_level": "10", "section": "A"}).json()
    classB = requests.post(f"{BASE_URL}/admin/classes", headers=h,
        json={"name": f"TT_B_{TS}", "class_level": "10", "section": "B"}).json()

    # Teachers
    t1_email = f"tt_teacher1_{TS}@school.com"
    t2_email = f"tt_teacher2_{TS}@school.com"
    teacher1 = requests.post(f"{BASE_URL}/admin/teachers", headers=h,
        json={"full_name": "Teacher One", "email": t1_email, "password": "Pass1word"}).json()
    teacher2 = requests.post(f"{BASE_URL}/admin/teachers", headers=h,
        json={"full_name": "Teacher Two", "email": t2_email, "password": "Pass1word"}).json()

    # Students
    s1_email = f"tt_student1_{TS}@school.com"
    s2_email = f"tt_student2_{TS}@school.com"
    student1 = requests.post(f"{BASE_URL}/admin/students", headers=h,
        json={"full_name": "Student Alpha", "email": s1_email, "password": "Pass1word",
              "class_id": classA["id"]}).json()
    student2 = requests.post(f"{BASE_URL}/admin/students", headers=h,
        json={"full_name": "Student Beta", "email": s2_email, "password": "Pass1word",
              "class_id": classB["id"]}).json()

    # Parent (linked to student1)
    p1_email = f"tt_parent1_{TS}@school.com"
    p2_email = f"tt_parent2_{TS}@school.com"
    parent1 = requests.post(f"{BASE_URL}/admin/parents", headers=h,
        json={"full_name": "Parent Alpha", "email": p1_email, "password": "Pass1word",
              "student_ids": [student1["id"]]}).json()
    # Unrelated parent (linked to student2)
    parent2 = requests.post(f"{BASE_URL}/admin/parents", headers=h,
        json={"full_name": "Parent Beta", "email": p2_email, "password": "Pass1word",
              "student_ids": [student2["id"]]}).json()

    # Subject
    subject = requests.post(f"{BASE_URL}/admin/subjects", headers=h,
        json={"name": f"Math_{TS}", "code": f"MTH{TS}"}).json()

    # Room
    room = requests.post(f"{BASE_URL}/admin/rooms", headers=h,
        json={"room_name": f"Room_{TS}", "capacity": 30}).json()

    # Period
    period = requests.post(f"{BASE_URL}/admin/periods", headers=h,
        json={"period_number": TS % 1000, "start_time": "08:00", "end_time": "08:45"}).json()

    # Academic mapping (teacher1 can teach this subject in classA)
    mapping = requests.post(f"{BASE_URL}/admin/mappings", headers=h,
        json={"teacher_id": teacher1["id"], "subject_id": subject["id"],
              "class_id": classA["id"]}).json()

    # ── Cache tokens now (admin already used 1/5 login slots; we use 4 more) ──
    # The rate limiter is 5/minute per IP; fetching all tokens here avoids
    # repeated mid-test logins that would trip the limit.
    time.sleep(0.3)
    t2_token = get_token(t2_email, "Pass1word")
    time.sleep(0.3)
    s1_token = get_token(s1_email, "Pass1word")
    time.sleep(0.3)
    s2_token = get_token(s2_email, "Pass1word")
    time.sleep(0.3)
    p1_token = get_token(p1_email, "Pass1word")

    return {
        "classA": classA, "classB": classB,
        "teacher1": teacher1, "teacher2": teacher2,
        "t1_email": t1_email, "t2_email": t2_email,
        "t2_token": t2_token,
        "student1": student1, "student2": student2,
        "s1_email": s1_email, "s2_email": s2_email,
        "s1_token": s1_token, "s2_token": s2_token,
        "parent1": parent1, "parent2": parent2,
        "p1_email": p1_email, "p2_email": p2_email,
        "p1_token": p1_token,
        "subject": subject, "room": room, "period": period,
        "mapping": mapping,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Create a valid timetable slot, then test teacher conflict (409)
# ─────────────────────────────────────────────────────────────────────────────

class TestTimetableConflicts:

    def test_create_slot_success(self, admin_token, setup_data):
        """Admin can create a valid slot."""
        h = auth(admin_token)
        d = setup_data
        resp = requests.post(f"{BASE_URL}/admin/timetable", headers=h, json={
            "class_id": d["classA"]["id"],
            "subject_id": d["subject"]["id"],
            "teacher_id": d["teacher1"]["id"],
            "room_id": d["room"]["id"],
            "day_of_week": 1,
            "period_id": d["period"]["id"],
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["period"]["id"] == d["period"]["id"]
        assert data["teacher"]["id"] == d["teacher1"]["id"]
        setup_data["slot_id"] = data["id"]

    def test_teacher_conflict_returns_409(self, admin_token, setup_data):
        """Same teacher, same day, same period → 409."""
        h = auth(admin_token)
        d = setup_data
        resp = requests.post(f"{BASE_URL}/admin/timetable", headers=h, json={
            "class_id": d["classB"]["id"],     # different class
            "subject_id": d["subject"]["id"],
            "teacher_id": d["teacher1"]["id"], # SAME teacher
            "room_id": d["room"]["id"],
            "day_of_week": 1,                  # SAME day
            "period_id": d["period"]["id"],    # SAME period
        })
        assert resp.status_code == 409, f"Expected 409 teacher conflict, got {resp.status_code}: {resp.text}"
        assert "Teacher" in resp.json()["detail"] or "teacher" in resp.json()["detail"].lower()
        print(f"\n  [PASS] Teacher conflict: {resp.json()['detail']}")

    def test_room_conflict_returns_409(self, admin_token, setup_data):
        """Same room, same day, same period → 409."""
        h = auth(admin_token)
        d = setup_data
        resp = requests.post(f"{BASE_URL}/admin/timetable", headers=h, json={
            "class_id": d["classB"]["id"],
            "subject_id": d["subject"]["id"],
            "teacher_id": d["teacher2"]["id"], # different teacher (avoids teacher conflict)
            "room_id": d["room"]["id"],        # SAME room
            "day_of_week": 1,                  # SAME day
            "period_id": d["period"]["id"],    # SAME period
        })
        assert resp.status_code == 409, f"Expected 409 room conflict, got {resp.status_code}: {resp.text}"
        assert "oom" in resp.json()["detail"]  # "Room" in message
        print(f"\n  [PASS] Room conflict: {resp.json()['detail']}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Cascade delete protection for periods
# ─────────────────────────────────────────────────────────────────────────────

class TestPeriodCascadeProtection:

    def test_cannot_delete_period_in_use(self, admin_token, setup_data):
        """Period referenced by a slot cannot be deleted → 409."""
        h = auth(admin_token)
        period_id = setup_data["period"]["id"]
        resp = requests.delete(f"{BASE_URL}/admin/periods/{period_id}", headers=h)
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        assert "Cannot delete" in resp.json()["detail"]
        print(f"\n  [PASS] Period cascade guard: {resp.json()['detail']}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Timetable access control — students and parents
# ─────────────────────────────────────────────────────────────────────────────

class TestTimetableAccessControl:

    def test_student_cannot_see_other_student_timetable(self, setup_data):
        """Student A trying to get Student B's timetable → 403."""
        h = auth(setup_data["s1_token"])
        student2_id = setup_data["student2"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/student/{student2_id}", headers=h)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Student cross-access blocked: {resp.json()['detail']}")

    def test_student_can_see_own_timetable(self, setup_data):
        """Student A can retrieve their own timetable (200)."""
        h = auth(setup_data["s1_token"])
        student1_id = setup_data["student1"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/student/{student1_id}", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Student own timetable: 200 OK, days={list(resp.json().keys())}")

    def test_parent_cannot_see_unrelated_student_timetable(self, setup_data):
        """Parent A (linked to student1) cannot see student2's timetable → 403."""
        h = auth(setup_data["p1_token"])
        student2_id = setup_data["student2"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/student/{student2_id}", headers=h)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Parent cross-access blocked: {resp.json()['detail']}")

    def test_parent_can_see_linked_child_timetable(self, setup_data):
        """Parent A (linked to student1) can see student1's timetable → 200."""
        h = auth(setup_data["p1_token"])
        student1_id = setup_data["student1"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/student/{student1_id}", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Parent linked child timetable: 200 OK")

    def test_teacher_cannot_see_another_teachers_timetable(self, setup_data):
        """Teacher 2 cannot see Teacher 1's timetable → 403."""
        h = auth(setup_data["t2_token"])
        teacher1_id = setup_data["teacher1"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/teacher/{teacher1_id}", headers=h)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Teacher cross-access blocked: {resp.json()['detail']}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Event registration logic
# ─────────────────────────────────────────────────────────────────────────────

class TestEventRegistration:

    @pytest.fixture(scope="class")
    def school_event(self, admin_token, setup_data):
        """Create a school-wide event (no class restriction)."""
        h = auth(admin_token)
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=7)).isoformat()
        resp = requests.post(f"{BASE_URL}/events/", headers=h, json={
            "title": f"Science Fair {TS}",
            "description": "Annual science fair",
            "event_date": future,
        })
        assert resp.status_code == 201, f"Event creation failed: {resp.text}"
        return resp.json()

    @pytest.fixture(scope="class")
    def class_restricted_event(self, admin_token, setup_data):
        """Create an event restricted to classA only."""
        h = auth(admin_token)
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=7)).isoformat()
        resp = requests.post(f"{BASE_URL}/events/", headers=h, json={
            "title": f"ClassA Only Event {TS}",
            "description": "Restricted to class A",
            "event_date": future,
            "class_id": setup_data["classA"]["id"],
        })
        assert resp.status_code == 201, f"Class-restricted event creation failed: {resp.text}"
        return resp.json()

    def test_student_registers_for_event(self, setup_data, school_event):
        """Student A successfully registers for a school-wide event → 201."""
        h = auth(setup_data["s1_token"])
        resp = requests.post(f"{BASE_URL}/events/{school_event['id']}/register", headers=h)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "registered"
        print(f"\n  [PASS] Student registered for event: {resp.json()['status']}")

    def test_duplicate_registration_returns_400(self, setup_data, school_event):
        """Student A tries to register again → 400."""
        h = auth(setup_data["s1_token"])
        resp = requests.post(f"{BASE_URL}/events/{school_event['id']}/register", headers=h)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "already registered" in resp.json()["detail"].lower()
        print(f"\n  [PASS] Duplicate registration blocked: {resp.json()['detail']}")

    def test_class_restricted_event_wrong_class_returns_403(self, setup_data, class_restricted_event):
        """Student B (classB) tries to register for classA-only event → 403."""
        h = auth(setup_data["s2_token"])
        resp = requests.post(f"{BASE_URL}/events/{class_restricted_event['id']}/register", headers=h)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        assert "restricted" in resp.json()["detail"].lower() or "class" in resp.json()["detail"].lower()
        print(f"\n  [PASS] Class restriction enforced: {resp.json()['detail']}")

    def test_class_restricted_event_correct_class_succeeds(self, setup_data, class_restricted_event):
        """Student A (classA) registers for classA-only event → 201."""
        h = auth(setup_data["s1_token"])
        resp = requests.post(f"{BASE_URL}/events/{class_restricted_event['id']}/register", headers=h)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        print(f"\n  [PASS] Correct class can register: {resp.json()['status']}")

    def test_admin_can_update_participant_status(self, admin_token, setup_data, school_event):
        """Admin updates student A's registration status to 'attended' → 200."""
        h = auth(admin_token)
        # Get registration id
        parts = requests.get(f"{BASE_URL}/events/{school_event['id']}/participants", headers=h)
        assert parts.status_code == 200
        reg = next((p for p in parts.json() if p["student"]["id"] == setup_data["student1"]["id"]), None)
        assert reg is not None, "Student registration not found in participants list"

        resp = requests.put(
            f"{BASE_URL}/events/{school_event['id']}/participants/{reg['id']}/status",
            headers=h,
            json={"status": "attended"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "attended"
        print(f"\n  [PASS] Participant status updated to: {resp.json()['status']}")

    def test_list_participants_shows_registrations(self, admin_token, setup_data, school_event):
        """List participants returns at least student A's entry."""
        h = auth(admin_token)
        resp = requests.get(f"{BASE_URL}/events/{school_event['id']}/participants", headers=h)
        assert resp.status_code == 200
        ids = [p["student"]["id"] for p in resp.json()]
        assert setup_data["student1"]["id"] in ids
        print(f"\n  [PASS] Participants listed: {len(resp.json())} entries")

    def test_event_soft_delete(self, admin_token, setup_data):
        """Admin soft-deletes an event; it disappears from the list."""
        h = auth(admin_token)
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=3)).isoformat()
        event = requests.post(f"{BASE_URL}/events/", headers=h,
            json={"title": f"Delete Me {TS}", "event_date": future}).json()

        del_resp = requests.delete(f"{BASE_URL}/events/{event['id']}", headers=h)
        assert del_resp.status_code == 204, f"Delete failed: {del_resp.status_code}"

        # Should no longer appear in listing
        all_events = requests.get(f"{BASE_URL}/events/", headers=h).json()
        ids = [e["id"] for e in all_events]
        assert event["id"] not in ids
        print(f"\n  [PASS] Event soft-deleted and removed from listing")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Full readable timetable response
# ─────────────────────────────────────────────────────────────────────────────

class TestTimetableReadability:

    def test_class_timetable_returns_rich_response(self, admin_token, setup_data):
        """GET /timetable/class/{id} returns subject name, teacher name, room, period times."""
        h = auth(admin_token)
        class_id = setup_data["classA"]["id"]
        resp = requests.get(f"{BASE_URL}/timetable/class/{class_id}", headers=h)
        assert resp.status_code == 200
        weekly = resp.json()
        # Day 1 (Monday) should have one slot
        assert "1" in weekly or 1 in weekly
        day_key = "1" if "1" in weekly else 1
        slots = weekly[day_key]
        assert len(slots) >= 1
        slot = slots[0]
        # Rich nested data must be present
        assert "subject" in slot and "name" in slot["subject"]
        assert "teacher" in slot and "full_name" in slot["teacher"]
        assert "room" in slot and "room_name" in slot["room"]
        assert "period" in slot and "start_time" in slot["period"] and "end_time" in slot["period"]
        print(f"\n  [PASS] Rich timetable slot: "
              f"subject={slot['subject']['name']}, "
              f"teacher={slot['teacher']['full_name']}, "
              f"room={slot['room']['room_name']}, "
              f"period={slot['period']['start_time']}-{slot['period']['end_time']}")


if __name__ == "__main__":
    # Quick standalone run (no pytest needed)
    import sys

    print("=" * 60)
    print("Phase 1 Verification — Manual Run")
    print("=" * 60)

    try:
        resp = requests.get(f"{BASE_URL}/", timeout=3)
        print(f"[OK] Server reachable at {BASE_URL}")
    except Exception as e:
        print(f"[FAIL] Cannot reach server at {BASE_URL}: {e}")
        sys.exit(1)

    print("\nRun with: python -m pytest backend/tests/test_phase1.py -v")
