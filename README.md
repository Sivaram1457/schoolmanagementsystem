# School Management System

Backend for a school management system built with FastAPI and PostgreSQL.

## Modules

1. **Authentication**: JWT, RBAC (Admin, Teacher, Student, Parent).
2. **Attendance**: Bulk marking, audit locks, and analytics (Module 2).
3. **Academic Mapping**: Linking Teachers to Subjects and Classes (Module 3).
4. **Homework System**: Assignment management with role-based visibility (Module 4).

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `.env`:
   ```bash
   cp .env.example .env
   ```
3. Reset Database & Seed:
   ```bash
   python reset_db.py
   python seed_admin.py
   ```
4. Run:
   ```bash
   uvicorn main:app --reload
   ```
