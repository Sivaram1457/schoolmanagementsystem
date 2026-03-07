#!/usr/bin/env python
"""
verify_system.py — Full QA verification script for the School Management System.

Covers all 12 test steps:
  1.  Database table check (psycopg2)
  2.  Route health check
  3.  Auth (login, /auth/me, refresh)
  4.  RBAC enforcement
  5.  Timetable rich-response
  6.  Event system
  7.  Certificate generation + ZIP download
  8.  File upload (multipart)
  9.  Announcements + role filtering
  10. Notification create + mark-read
  11. Analytics (all 4 endpoints)
  12. Final report

Usage:
    python verify_system.py

Requires the API server to be running on http://localhost:8000.
"""

import io
import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from typing import Any, Optional

import psycopg2
import requests

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
DB_URL   = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/school_db")

ADMIN_EMAIL    = "admin@school.com"
ADMIN_PASSWORD = "admin123"

# Timestamp to create unique test users per run
TS = int(time.time())


# ─────────────────────────────────────────────────────────────────────────────
# Reporting helpers
# ─────────────────────────────────────────────────────────────────────────────

PASS  = "\033[92m  PASS\033[0m"
FAIL  = "\033[91m  FAIL\033[0m"
WARN  = "\033[93m  WARN\033[0m"
INFO  = "\033[94m  INFO\033[0m"
BOLD  = "\033[1m"
RESET = "\033[0m"

_results: dict[str, list[tuple[str, bool, str]]] = {}   # section → [(label, ok, detail)]
_warn_sections: set[str] = set()


def _section(name: str) -> None:
    _results[name] = []
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  {name}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")


def _check(label: str, ok: bool, detail: str = "", section: Optional[str] = None) -> bool:
    tag = PASS if ok else FAIL
    msg = f"  {detail}" if detail else ""
    print(f"{tag}  {label}{msg}")
    # Store in most-recent section
    key = list(_results.keys())[-1] if _results else "misc"
    _results[key].append((label, ok, detail))
    return ok


def _info(msg: str) -> None:
    print(f"{INFO}  {msg}")


def _warn(msg: str) -> None:
    print(f"{WARN}  {msg}")
    # Mark the current section as having at least one warning
    if _results:
        key = list(_results.keys())[-1]
        _warn_sections.add(key)


def _safe(label: str, fn) -> Any:
    """Call fn(), return its result; on any exception mark as FAILED and return None."""
    try:
        result = fn()
        return result
    except Exception as exc:
        _check(label, False, f"Exception: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Database table check
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_TABLES = [
    "users", "classes", "subjects", "attendance", "homework",
    "homework_submissions", "academic_mappings", "periods", "rooms",
    "timetable_slots", "events", "event_registrations",
    "certificates", "announcements", "notifications", "academic_calendar",
]


def step1_database() -> bool:
    _section("STEP 1 — Database Table Check")
    try:
        # Parse DSN
        import urllib.parse as up
        p = up.urlparse(DB_URL)
        conn = psycopg2.connect(
            host=p.hostname, port=p.port or 5432,
            dbname=p.path.lstrip("/"), user=p.username, password=p.password,
        )
        _check("PostgreSQL connection", True)
    except Exception as exc:
        _check("PostgreSQL connection", False, str(exc))
        return False

    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name;"
    )
    existing = {row[0] for row in cur.fetchall()}

    all_ok = True
    for tbl in REQUIRED_TABLES:
        ok = tbl in existing
        _check(f"Table '{tbl}'", ok)
        if not ok:
            all_ok = False

    extra = existing - set(REQUIRED_TABLES) - {"alembic_version", "student_parents",
                                                "refresh_tokens", "password_reset_tokens",
                                                "email_verification_tokens"}
    if extra:
        _info(f"Extra tables (non-required): {', '.join(sorted(extra))}")

    # Check alembic head
    cur.execute("SELECT version_num FROM alembic_version;")
    row = cur.fetchone()
    _info(f"Alembic head: {row[0] if row else 'NONE'}")

    # Check photo_url column on users
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='users' AND column_name='photo_url';"
    )
    _check("users.photo_url column exists", bool(cur.fetchone()))

    conn.close()
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Route health check
# ─────────────────────────────────────────────────────────────────────────────

# (prefix, sample path, needs_auth)
ROUTE_PROBES = [
    ("Health /",                "/",                          False),
    ("Auth   /auth/login",      "/auth/login",                False),  # OPTIONS-style: will 405 ok
    ("Admin  /admin/classes",   "/admin/classes",             True),
    ("Attendance /attendance",  "/attendance/bulk",           True),
    ("Homework /homework",      "/homework",                  True),
    ("Timetable /admin/periods","/admin/periods",             True),
    ("Events /events",          "/events/",                   True),
    ("Upload /upload",          "/upload",                    True),
    ("Certs /certificates",     "/certificates/event/0",      True),
    ("Announce /announcements", "/announcements",             True),
    ("Notify /notifications",   "/notifications/me",          True),
    ("Calendar /calendar",      "/calendar/",                 True),
    ("Analytics /analytics",    "/analytics/student/1",       True),
]


def step2_routes(admin_token: str) -> bool:
    _section("STEP 2 — Route Health Check")
    h = {"Authorization": f"Bearer {admin_token}"}
    all_ok = True
    for label, path, needs_auth in ROUTE_PROBES:
        try:
            headers = h if needs_auth else {}
            r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5)
            # Accept any non-50x response as "route exists"
            alive = r.status_code < 500
            _check(label, alive, f"HTTP {r.status_code}")
            if not alive:
                all_ok = False
        except Exception as exc:
            _check(label, False, str(exc))
            all_ok = False
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Auth test
# ─────────────────────────────────────────────────────────────────────────────

def step3_auth() -> tuple[str, str, dict]:
    """Returns (access_token, refresh_token, admin_user_dict). Raises on failure."""
    _section("STEP 3 — Authentication")

    # Login
    r = requests.post(f"{BASE_URL}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=5)
    _check("POST /auth/login → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise RuntimeError(f"Admin login failed: {r.text[:200]}")

    data = r.json()
    access_token  = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")

    _check("access_token present",  bool(access_token))
    _check("refresh_token present", bool(refresh_token))

    # /auth/me
    h = {"Authorization": f"Bearer {access_token}"}
    me = requests.get(f"{BASE_URL}/auth/me", headers=h, timeout=5)
    _check("GET /auth/me → 200", me.status_code == 200, f"HTTP {me.status_code}")
    user = me.json() if me.ok else {}
    _check("me.email matches",  user.get("email") == ADMIN_EMAIL)
    _check("me.role == admin",  user.get("role")  == "admin")
    _info(f"Logged in as: {user.get('full_name')} <{user.get('email')}>")

    # Token refresh
    ref = requests.post(f"{BASE_URL}/auth/refresh",
                        json={"refresh_token": refresh_token}, timeout=5)
    _check("POST /auth/refresh → 200", ref.status_code == 200, f"HTTP {ref.status_code}")
    body = ref.json() if ref.ok else {}
    new_access = body.get("access_token", "") if ref.ok else ""
    new_refresh = body.get("refresh_token", "") if ref.ok else ""
    _check("new access_token returned", bool(new_access))
    _check("new refresh_token returned", bool(new_refresh))
    if new_access:
        access_token = new_access   # use fresh token for the rest

    # Refresh token rotation: old token must not work twice
    second = requests.post(f"{BASE_URL}/auth/refresh",
                           json={"refresh_token": refresh_token}, timeout=5)
    _check("Second /auth/refresh with old token → 401",
           second.status_code == 401, f"HTTP {second.status_code}")

    return access_token, new_refresh or refresh_token, user


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _unwrap_list(data: Any) -> list:
    """Unwrap paginated responses like {items: [...]} or plain lists."""
    if isinstance(data, dict):
        return data.get("items", [])
    return data if isinstance(data, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — RBAC enforcement
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_class(h_admin: dict) -> int:
    """Return the ID of an existing class, creating one if needed."""
    classes_r = requests.get(f"{BASE_URL}/admin/classes", headers=h_admin, timeout=5).json()
    classes_list = _unwrap_list(classes_r)
    if classes_list:
        return classes_list[0]["id"]
    # No class yet — create a temporary one
    cr = requests.post(f"{BASE_URL}/admin/classes", headers=h_admin,
                       json={"name": f"QA-Class-{TS}", "grade_level": 1}, timeout=5)
    if cr.ok:
        return cr.json()["id"]
    raise RuntimeError(f"Could not get or create a class: {cr.text[:120]}")


def step4_rbac(admin_token: str) -> bool:
    _section("STEP 4 — RBAC Enforcement")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # Create a real student user (requires class_id)
    try:
        class_id = _ensure_class(h_admin)
    except RuntimeError as exc:
        _check("Ensure class exists for RBAC", False, str(exc))
        return False
    _check("Ensure class exists", True, f"class_id={class_id}")

    student_email = f"qa_student_{TS}@test.com"
    cr = requests.post(f"{BASE_URL}/admin/students", headers=h_admin, json={
        "full_name": "QA Student",
        "email": student_email,
        "password": "TestPass1!",
        "class_id": class_id,
    }, timeout=5)
    if not cr.ok:
        _check("Create test student for RBAC", False, cr.text[:200])
        return False
    _check("Create test student", True)

    # Login as student
    lr = requests.post(f"{BASE_URL}/auth/login",
                       json={"email": student_email, "password": "TestPass1!"}, timeout=5)
    _check("Student login → 200", lr.status_code == 200, f"HTTP {lr.status_code}")
    if not lr.ok:
        return False

    student_token = lr.json()["access_token"]
    h_student = {"Authorization": f"Bearer {student_token}"}

    all_ok = True

    # Test each admin-only endpoint — pass a minimal body so auth runs before validation
    future = str(date.today() + timedelta(days=7))
    checks = [
        # (label, method, path, expected_status, body)
        ("Student → GET /admin/classes",         "GET",  "/admin/classes",   403, {}),
        ("Student → POST /admin/teachers",        "POST", "/admin/teachers",  403, {
            "full_name": "X", "email": f"x_{TS}@t.com", "password": "Pass1!"}),
        ("Student → GET /announcements (admin)",  "GET",  "/announcements",   403, {}),
        ("Student → POST /events (admin only)",   "POST", "/events/",         403, {
            "title": "X", "description": "X", "event_date": future}),
        ("Student → GET /analytics/class/1",      "GET",  "/analytics/class/1", 403, {}),
    ]
    for label, method, path, expected, body in checks:
        r = requests.request(method, f"{BASE_URL}{path}", headers=h_student,
                             json=body, timeout=5)
        ok = r.status_code == expected
        _check(label, ok, f"got {r.status_code}, want {expected}")
        if not ok:
            all_ok = False

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Timetable rich response
# ─────────────────────────────────────────────────────────────────────────────

def step5_timetable(admin_token: str) -> bool:
    _section("STEP 5 — Timetable Rich Response")
    h = {"Authorization": f"Bearer {admin_token}"}

    # Get first class
    classes_raw = requests.get(f"{BASE_URL}/admin/classes", headers=h, timeout=5).json()
    classes = _unwrap_list(classes_raw)
    if not classes:
        _warn("No classes found — skipping timetable check")
        return True

    class_id = classes[0]["id"]
    r = requests.get(f"{BASE_URL}/timetable/class/{class_id}", headers=h, timeout=5)
    _check(f"GET /timetable/class/{class_id} → 200", r.ok, f"HTTP {r.status_code}")
    if not r.ok:
        return False

    weekly = r.json()
    if not weekly:
        _warn("Timetable is empty (no slots defined yet) — schedule routes work but no test data")
        return True

    # Inspect first available slot
    day_key = str(list(weekly.keys())[0])
    slots = weekly[day_key]
    _check("Timetable has at least one slot", len(slots) > 0)
    slot = slots[0]

    required_nested = {
        "subject.name":      ("subject",  "name"),
        "teacher.full_name": ("teacher",  "full_name"),
        "room.room_name":    ("room",     "room_name"),
        "period.start_time": ("period",   "start_time"),
        "period.end_time":   ("period",   "end_time"),
    }
    all_ok = True
    for label, (parent, field) in required_nested.items():
        val = (slot.get(parent) or {}).get(field)
        ok = bool(val)
        _check(f"slot.{label} present", ok, val or "MISSING")
        if not ok:
            all_ok = False

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5b — Teacher timetable permissions
# ─────────────────────────────────────────────────────────────────────────────

def step5b_teacher_timetable_permissions(admin_token: str) -> bool:
    """Ensure a teacher cannot view another teacher's timetable."""
    _section("STEP 5b — Teacher Timetable Permissions")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # Use seeded teachers (see backend/scripts/seed_test_data.py)
    teachers_raw = requests.get(f"{BASE_URL}/admin/teachers", headers=h_admin, timeout=5).json()
    teachers = _unwrap_list(teachers_raw)
    if not teachers:
        _warn("No teachers found — skipping teacher timetable RBAC check")
        return True

    by_email = {t.get("email"): t for t in teachers}
    known_emails = ["smith@school.com", "johnson@school.com", "brown@school.com"]
    available = [by_email[e] for e in known_emails if e in by_email]
    if len(available) < 2:
        _warn("Fewer than two seeded teachers available — skipping teacher timetable RBAC check")
        return True

    t1, t2 = available[0], available[1]

    # Login as teacher 1 (seeded password 'pass123')
    lr = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": t1["email"], "password": "pass123"},
        timeout=5,
    )
    _check("Teacher login → 200", lr.status_code == 200, f"HTTP {lr.status_code}")
    if not lr.ok:
        return False

    teacher_token = lr.json().get("access_token", "")
    h_teacher = {"Authorization": f"Bearer {teacher_token}"}

    # Teacher A should be forbidden from viewing teacher B's timetable
    r = requests.get(f"{BASE_URL}/timetable/teacher/{t2['id']}", headers=h_teacher, timeout=5)
    ok = r.status_code == 403
    _check("Teacher A cannot view teacher B timetable", ok,
           f"got {r.status_code}, want 403")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Event system
# ─────────────────────────────────────────────────────────────────────────────

def step6_events(admin_token: str, student_id: int) -> Optional[int]:
    """Returns event_id if successful, else None."""
    _section("STEP 6 — Event System")
    h = {"Authorization": f"Bearer {admin_token}"}

    future_date = str(date.today() + timedelta(days=14))

    # Create event
    cr = requests.post(f"{BASE_URL}/events/", headers=h, json={
        "title":       f"QA Science Fair {TS}",
        "description": "Annual QA verification event",
        "event_date":  future_date,
    }, timeout=5)
    _check("POST /events/ → 201", cr.status_code == 201, f"HTTP {cr.status_code}")
    if not cr.ok:
        _info(cr.text[:200])
        return None

    event = cr.json()
    event_id = event["id"]
    _info(f"Created event id={event_id} title={event['title']!r}")

    # Register student (admin registers on their behalf)
    # We use the admin token — the register endpoint accepts admin role
    rr = requests.post(f"{BASE_URL}/events/{event_id}/register",
                       headers=h, timeout=5)
    # Admin self-registration may 403 — try registering via a student login
    if rr.status_code == 403:
        _info("Admin cannot self-register — creating dedicated event student")
        student_email2 = f"qa_evtstudent_{TS}@test.com"
        cls_raw = requests.get(f"{BASE_URL}/admin/classes", headers=h, timeout=5).json()
        class_id = _unwrap_list(cls_raw)[0]["id"] if _unwrap_list(cls_raw) else None
        sc = requests.post(f"{BASE_URL}/admin/students", headers=h, json={
            "full_name": "QA Event Student",
            "email": student_email2,
            "password": "TestPass1!",
            "class_id": class_id,
        }, timeout=5)
        if sc.ok:
            sl2 = requests.post(f"{BASE_URL}/auth/login",
                                json={"email": student_email2, "password": "TestPass1!"}, timeout=5)
            st2 = sl2.json().get("access_token", "") if sl2.ok else ""
            if st2:
                rr = requests.post(f"{BASE_URL}/events/{event_id}/register",
                                   headers={"Authorization": f"Bearer {st2}"}, timeout=5)

    _check(f"POST /events/{event_id}/register → 201",
           rr.status_code == 201, f"HTTP {rr.status_code}")
    if rr.ok:
        _check("registration.status == 'registered'",
               rr.json().get("status") == "registered")

    # List participants
    pr = requests.get(f"{BASE_URL}/events/{event_id}/participants", headers=h, timeout=5)
    _check(f"GET /events/{event_id}/participants → 200",
           pr.status_code == 200, f"HTTP {pr.status_code}")
    if pr.ok:
        _check("participants list is non-empty", len(pr.json()) > 0,
               f"{len(pr.json())} registrations")

    # List all events
    lr = requests.get(f"{BASE_URL}/events/", headers=h, timeout=5)
    _check("GET /events/ → 200", lr.ok, f"HTTP {lr.status_code}")
    ids = [e["id"] for e in lr.json()] if lr.ok else []
    _check("New event appears in listings", event_id in ids)

    return event_id


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Certificate generation + ZIP download
# ─────────────────────────────────────────────────────────────────────────────

def step7_certificates(admin_token: str, event_id: Optional[int]) -> bool:
    _section("STEP 7 — Certificate Generation")
    h = {"Authorization": f"Bearer {admin_token}"}

    if event_id is None:
        _warn("No event_id from Step 6 — skipping certificate tests")
        return True

    # Generate
    gr = requests.post(f"{BASE_URL}/certificates/generate/{event_id}",
                       headers=h, timeout=30)
    _check(f"POST /certificates/generate/{event_id} → 201",
           gr.status_code == 201, f"HTTP {gr.status_code}")
    if gr.ok:
        body = gr.json()
        _check("generated count > 0", body.get("generated", 0) > 0,
               f"generated={body.get('generated')}, skipped={body.get('skipped')}")
        _check("certificates list non-empty", len(body.get("certificates", [])) > 0)
        certs = body.get("certificates", [])
        if certs:
            _check("certificate.file_url starts with /uploads",
                   certs[0].get("file_url", "").startswith("/uploads"))
    else:
        _info(f"Generate error: {gr.text[:200]}")

    # List
    lr = requests.get(f"{BASE_URL}/certificates/event/{event_id}", headers=h, timeout=5)
    _check(f"GET /certificates/event/{event_id} → 200",
           lr.ok, f"HTTP {lr.status_code}")
    if lr.ok:
        _check("certificate list non-empty", len(lr.json()) > 0,
               f"{len(lr.json())} certificates")

    # ZIP download
    zr = requests.get(f"{BASE_URL}/certificates/download/{event_id}",
                      headers=h, timeout=15)
    _check(f"GET /certificates/download/{event_id} → 200",
           zr.ok, f"HTTP {zr.status_code}")
    if zr.ok:
        _check("Content-Type is application/zip",
               "zip" in zr.headers.get("Content-Type", ""))
        _check("Content-Disposition contains 'attachment'",
               "attachment" in zr.headers.get("Content-Disposition", ""))
        _check("ZIP body non-empty (>0 bytes)", len(zr.content) > 0,
               f"{len(zr.content)} bytes")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — File upload
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_valid_png() -> bytes:
    """Return a minimal 1×1 red PNG as bytes (no Pillow required)."""
    import struct, zlib
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr   = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw    = b"\x00\xff\x00\x00"          # filter byte + R G B
    idat   = chunk(b"IDAT", zlib.compress(raw))
    iend   = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def step8_upload(admin_token: str) -> bool:
    _section("STEP 8 — File Upload")
    h = {"Authorization": f"Bearer {admin_token}"}

    png_bytes = _minimal_valid_png()
    files = {"file": ("qa_test.png", io.BytesIO(png_bytes), "image/png")}
    r = requests.post(f"{BASE_URL}/upload", headers=h, files=files, timeout=10)
    _check("POST /upload → 201", r.status_code == 201, f"HTTP {r.status_code}")
    if not r.ok:
        _info(r.text[:200])
        return False

    body = r.json()
    file_url = body.get("file_url", "")
    _check("file_url present in response",     bool(file_url), file_url)
    _check("file_url starts with /uploads",    file_url.startswith("/uploads"))
    _check("file_url contains 'general'",      "general" in file_url)

    # Verify the file is served via static mount
    static = requests.get(f"{BASE_URL}{file_url}", timeout=5)
    _check(f"GET {file_url} → 200 (static serving)", static.ok,
           f"HTTP {static.status_code}")

    # Upload student photo (to /uploads/students/)
    classes_raw2 = requests.get(f"{BASE_URL}/admin/classes", headers=h, timeout=5).json()
    classes2     = _unwrap_list(classes_raw2)
    class_id2    = classes2[0]["id"] if classes2 else None
    stu = requests.post(f"{BASE_URL}/admin/students", headers=h, json={
        "full_name": "QA PhotoTest Student",
        "email": f"qa_photo_{TS}@test.com",
        "password": "TestPass1!",
        "class_id": class_id2,
    }, timeout=5)
    if stu.ok:
        sid = stu.json().get("id") or stu.json().get("user_id")
        pf  = {"file": ("qa_photo.png", io.BytesIO(_minimal_valid_png()), "image/png")}
        pr  = requests.post(f"{BASE_URL}/students/{sid}/photo", headers=h,
                           files=pf, timeout=10)
        _check(f"POST /students/{sid}/photo → 200", pr.ok, f"HTTP {pr.status_code}")
        if pr.ok:
            url = pr.json().get("file_url", "")
            _check("Student photo URL contains 'students'", "students" in url, url)

    # Attempt to upload a file larger than 5 MB — should be rejected with 413
    big_bytes = b"0" * (6 * 1024 * 1024)
    big_files = {"file": ("too_big.png", io.BytesIO(big_bytes), "image/png")}
    big_r = requests.post(f"{BASE_URL}/upload", headers=h, files=big_files, timeout=30)
    _check("Large file (>5MB) rejected with 413", big_r.status_code == 413,
           f"HTTP {big_r.status_code}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — Announcements
# ─────────────────────────────────────────────────────────────────────────────

def step9_announcements(admin_token: str) -> bool:
    _section("STEP 9 — Announcement System")
    h = {"Authorization": f"Bearer {admin_token}"}

    targets = [
        ("all",     "Announcement for everyone"),
        ("student", "Student-only announcement"),
        ("teacher", "Teacher-only announcement"),
    ]
    created_ids = []
    for target, msg in targets:
        cr = requests.post(f"{BASE_URL}/announcements", headers=h, json={
            "title":       f"QA {target.title()} Announcement {TS}",
            "message":     msg,
            "target_role": target,
        }, timeout=5)
        ok = cr.status_code == 201
        _check(f"POST /announcements (target={target}) → 201",
               ok, f"HTTP {cr.status_code}")
        if ok:
            created_ids.append(cr.json()["id"])

    # Admin sees all
    all_r = requests.get(f"{BASE_URL}/announcements", headers=h, timeout=5)
    _check("GET /announcements (admin) → 200", all_r.ok, f"HTTP {all_r.status_code}")

    # Admin /me — admin role; target_role='all' and 'admin' should appear
    me_r = requests.get(f"{BASE_URL}/announcements/me", headers=h, timeout=5)
    _check("GET /announcements/me (admin) → 200", me_r.ok, f"HTTP {me_r.status_code}")
    if me_r.ok:
        my_titles = [a["title"] for a in me_r.json()]
        has_all_ann = any(f"QA All Announcement {TS}" in t for t in my_titles)
        _check("'all' announcement visible to admin via /me", has_all_ann)

    # Create a test student and check their /me only shows correct targets
    s_email = f"qa_ann_student_{TS}@test.com"
    cls_raw_ann = requests.get(f"{BASE_URL}/admin/classes", headers=h, timeout=5).json()
    cls_ann     = _unwrap_list(cls_raw_ann)
    class_id_ann = cls_ann[0]["id"] if cls_ann else None
    sr = requests.post(f"{BASE_URL}/admin/students", headers=h, json={
        "full_name": "QA Ann Student", "email": s_email, "password": "TestPass1!",
        "class_id": class_id_ann,
    }, timeout=5)
    if sr.ok:
        sl = requests.post(f"{BASE_URL}/auth/login",
                           json={"email": s_email, "password": "TestPass1!"}, timeout=5)
        if sl.ok:
            st  = sl.json()["access_token"]
            sh  = {"Authorization": f"Bearer {st}"}
            sm  = requests.get(f"{BASE_URL}/announcements/me", headers=sh, timeout=5)
            _check("GET /announcements/me (student) → 200",
                   sm.ok, f"HTTP {sm.status_code}")
            if sm.ok:
                student_titles = [a["title"] for a in sm.json()]
                has_student = any(f"QA Student Announcement {TS}" in t for t in student_titles)
                has_all     = any(f"QA All Announcement {TS}" in t for t in student_titles)
                no_teacher  = all(f"QA Teacher Announcement {TS}" not in t for t in student_titles)
                _check("Student sees 'student' announcements", has_student)
                _check("Student sees 'all' announcements",     has_all)
                _check("Student does NOT see 'teacher' announcements", no_teacher)

    # Cleanup
    for ann_id in created_ids:
        requests.delete(f"{BASE_URL}/announcements/{ann_id}", headers=h, timeout=5)

    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 10 — Notifications
# ─────────────────────────────────────────────────────────────────────────────

def step10_notifications(admin_token: str) -> bool:
    _section("STEP 10 — Notification System")
    h = {"Authorization": f"Bearer {admin_token}"}

    # Insert a notification directly via DB (testing the internal helper pathway)
    import urllib.parse as up
    p = up.urlparse(DB_URL)
    try:
        conn = psycopg2.connect(
            host=p.hostname, port=p.port or 5432,
            dbname=p.path.lstrip("/"), user=p.username, password=p.password,
        )
        cur = conn.cursor()

        # Get admin user id
        cur.execute("SELECT id FROM users WHERE email = %s;", (ADMIN_EMAIL,))
        row = cur.fetchone()
        if not row:
            _warn("Admin user not found in DB")
            conn.close()
            return False
        admin_id = row[0]

        # Insert notification
        cur.execute(
            "INSERT INTO notifications (user_id, title, message, is_read) "
            "VALUES (%s, %s, %s, FALSE) RETURNING id;",
            (admin_id, f"QA Notification {TS}", "Verification system: DB-inserted notification"),
        )
        notif_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        _check("Notification inserted via DB helper", True, f"id={notif_id}")
    except Exception as exc:
        _check("Notification inserted via DB helper", False, str(exc))
        return False

    # GET /notifications/me — must include the one we just inserted
    r = requests.get(f"{BASE_URL}/notifications/me", headers=h, timeout=5)
    _check("GET /notifications/me → 200", r.ok, f"HTTP {r.status_code}")

    if r.ok:
        notifs = r.json()
        target = next((n for n in notifs if n["id"] == notif_id), None)
        _check("Inserted notification appears in /me", target is not None)
        if target:
            _check("Notification is_read == False", not target["is_read"])

            # Mark as read
            mr = requests.put(f"{BASE_URL}/notifications/{notif_id}/read",
                              headers=h, timeout=5)
            _check(f"PUT /notifications/{notif_id}/read → 200",
                   mr.ok, f"HTTP {mr.status_code}")
            if mr.ok:
                _check("is_read flipped to True", mr.json().get("is_read") is True)

            # Delete
            dr = requests.delete(f"{BASE_URL}/notifications/{notif_id}",
                                 headers=h, timeout=5)
            _check(f"DELETE /notifications/{notif_id} → 204",
                   dr.status_code == 204, f"HTTP {dr.status_code}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 11 — Analytics
# ─────────────────────────────────────────────────────────────────────────────

def step11_analytics(admin_token: str) -> bool:
    _section("STEP 11 — Analytics Engine")
    h = {"Authorization": f"Bearer {admin_token}"}

    # Resolve a student & class
    classes_raw = requests.get(f"{BASE_URL}/admin/classes", headers=h, timeout=5).json()
    classes = _unwrap_list(classes_raw)
    if not classes:
        _warn("No classes found — skipping analytics")
        return True

    class_id = classes[0]["id"]

    students_raw = requests.get(f"{BASE_URL}/admin/students", headers=h, timeout=5).json()
    students_list = _unwrap_list(students_raw)
    student_id = students_list[0]["id"] if students_list else None

    all_ok = True

    # Student analytics
    if student_id:
        r = requests.get(f"{BASE_URL}/analytics/student/{student_id}",
                         headers=h, timeout=10)
        _check(f"GET /analytics/student/{student_id} → 200",
               r.ok, f"HTTP {r.status_code}")
        if r.ok:
            body = r.json()
            for field in ("attendance_pct", "homework_completion_pct",
                          "total_school_days", "days_present", "days_absent",
                          "total_homework", "homework_submitted", "holidays_excluded"):
                present = field in body
                _check(f"  student_analytics.{field} present", present,
                       str(body.get(field, "MISSING")))
                if not present:
                    all_ok = False
            # Values must be valid percentages
            att_pct = body.get("attendance_pct", -1)
            hw_pct  = body.get("homework_completion_pct", -1)
            _check("  attendance_pct in [0, 100]",   0 <= att_pct <= 100, str(att_pct))
            _check("  homework_completion_pct in [0, 100]", 0 <= hw_pct <= 100, str(hw_pct))

    # Class analytics
    r = requests.get(f"{BASE_URL}/analytics/class/{class_id}",
                     headers=h, timeout=10)
    _check(f"GET /analytics/class/{class_id} → 200",
           r.ok, f"HTTP {r.status_code}")
    if r.ok:
        body = r.json()
        for field in ("avg_attendance_pct", "avg_homework_completion_pct",
                      "total_students", "class_name"):
            _check(f"  class_analytics.{field} present", field in body,
                   str(body.get(field, "MISSING")))

    # Attendance trends
    r = requests.get(f"{BASE_URL}/analytics/attendance-trends/{class_id}?weeks=4",
                     headers=h, timeout=10)
    _check(f"GET /analytics/attendance-trends/{class_id}?weeks=4 → 200",
           r.ok, f"HTTP {r.status_code}")
    if r.ok:
        body = r.json()
        _check("  trend.class_id present",  "class_id"   in body)
        _check("  trend.class_name present", "class_name" in body)
        _check("  trend.trend is a list",    isinstance(body.get("trend"), list))

    # Homework completion
    r = requests.get(f"{BASE_URL}/analytics/homework-completion/{class_id}",
                     headers=h, timeout=10)
    _check(f"GET /analytics/homework-completion/{class_id} → 200",
           r.ok, f"HTTP {r.status_code}")
    if r.ok:
        items = r.json()
        _check("  Result is a list", isinstance(items, list))
        if items:
            _check("  Item has completion_pct",  "completion_pct"  in items[0])
            _check("  Item has total_students",  "total_students"  in items[0])

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# STEP 12 — Final Report
# ─────────────────────────────────────────────────────────────────────────────

def step12_report() -> bool:
    _section("STEP 12 — Final Report")

    total_pass = total_fail = total_warn = 0

    print(f"\n  {'Section':<24} {'STATUS':>8} {'PASS':>5} {'FAIL':>5}")
    print(f"  {'─' * 24}  {'─' * 8}  {'─' * 5}  {'─' * 5}")

    SUMMARY_LABELS = {
        "STEP 1 — Database Table Check": "Database",
        "STEP 2 — Route Health Check": "Routes",
        "STEP 3 — Authentication": "Authentication",
        "STEP 4 — RBAC Enforcement": "RBAC",
        "STEP 5 — Timetable Rich Response": "Timetable",
        "STEP 5b — Teacher Timetable Permissions": "Timetable RBAC",
        "STEP 6 — Event System": "Events",
        "STEP 7 — Certificate Generation": "Certificates",
        "STEP 8 — File Upload": "Uploads",
        "STEP 9 — Announcement System": "Announcements",
        "STEP 10 — Notification System": "Notifications",
        "STEP 11 — Analytics Engine": "Analytics",
        "STEP 12 — Final Report": "Final Report",
    }

    for section, checks in _results.items():
        passed = sum(1 for _, ok, _ in checks if ok)
        failed = sum(1 for _, ok, _ in checks if not ok)
        has_warn = section in _warn_sections
        total_pass += passed
        total_fail += failed
        if has_warn:
            total_warn += 1

        if failed > 0:
            status_text = "FAIL"
        elif has_warn:
            status_text = "WARN"
        else:
            status_text = "PASS"

        label = SUMMARY_LABELS.get(section, section.split("—")[-1].strip())
        print(f"  {label:<24} {status_text:>8} {passed:>5} {failed:>5}")

    print(f"\n  {'─' * 50}")
    total = total_pass + total_fail
    print(f"  Total checks  : {total}")
    print(f"  Passed        : {total_pass}")
    print(f"  Warnings      : {total_warn}")
    print(f"  Failed        : {total_fail}")

    overall_ok = total_fail == 0
    if overall_ok and total_warn == 0:
        health = f"{BOLD}\033[92m  SYSTEM HEALTH: OK{RESET}"
    elif overall_ok and total_warn > 0:
        health = f"{BOLD}\033[93m  SYSTEM HEALTH: OK (with warnings){RESET}"
    else:
        health = f"{BOLD}\033[91m  SYSTEM HEALTH: FAILED  ({total_fail} check(s) failed){RESET}"

    print(f"\n{health}\n")
    return overall_ok


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\n{BOLD}{'═' * 62}{RESET}")
    print(f"{BOLD}  School Management System — QA Verification Script{RESET}")
    print(f"{BOLD}  Target: {BASE_URL}{RESET}")
    print(f"{BOLD}{'═' * 62}{RESET}")

    # Server reachability pre-check
    try:
        ping = requests.get(f"{BASE_URL}/", timeout=5)
        if ping.status_code != 200:
            print(f"\n{FAIL}  Server at {BASE_URL} returned HTTP {ping.status_code}. Aborting.")
            return 1
    except requests.exceptions.ConnectionError:
        print(f"\n{FAIL}  Cannot reach {BASE_URL}. Is the server running?")
        return 1

    ok = True

    # Step 1 — DB
    ok &= step1_database()

    # Step 3 — Auth (must succeed before other steps that need token)
    try:
        access_token, refresh_token, admin_user = step3_auth()
    except RuntimeError as exc:
        print(f"{FAIL}  Auth failed: {exc} — cannot continue")
        step12_report()
        return 1

    # Steps that only need admin_token
    ok &= step2_routes(access_token)
    ok &= step4_rbac(access_token)
    ok &= step5_timetable(access_token)
    ok &= step5b_teacher_timetable_permissions(access_token)

    event_id = step6_events(access_token, admin_user.get("id"))
    ok &= step7_certificates(access_token, event_id)
    ok &= step8_upload(access_token)
    ok &= step9_announcements(access_token)
    ok &= step10_notifications(access_token)
    ok &= step11_analytics(access_token)

    overall = step12_report()
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
