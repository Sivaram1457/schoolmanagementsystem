# School Management System

A production-grade School Management System featuring a high-performance backend built with **FastAPI** and **PostgreSQL**, and a modern, responsive frontend built with **Flutter**.

## 🚀 Key Modules

### 1. 🔐 Authentication & Security
- **JWT-based Security**: Secure token-based authentication.
- **RBAC (Role-Based Access Control)**: Granular permissions for Admins, Teachers, Students, and Parents.
- **Rate Limiting**: Protects API endpoints from abuse.

### 2. 📋 Attendance Management
- **Bulk Marking**: Efficiently mark attendance for whole classes.
- **Audit Locks**: Ensures data integrity after marking.
- **Advanced Analytics**: Visual insights for administrators and parents.

### 3. 🗺️ Academic Mapping
- **Resource Linking**: Seamlessly connect Teachers to specific Subjects and Classes.
- **Schedule Management**: Organized class-subject-teacher hierarchies.

### 4. 📝 Homework System
- **Assignment Tracking**: Professional management of student tasks.
- **Visibility Toggles**: Role-based access to homework details.

## 🛠️ Technical Stack
- **Backend**: FastAPI, SQLAlchemy (PostgreSQL), Alembic.
- **Frontend**: Flutter, Provider (State Management), Dio (API Client).
- **Tooling**: Python 3.10+, Dart/Flutter SDK.

## ⚙️ Quick Start

### Backend Setup
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your PostgreSQL credentials
   ```
3. **Initialize Database**:
   ```bash
   python backend/scripts/reset_db.py
   python backend/scripts/seed_admin.py
   ```
4. **Run Server**:
   ```bash
   uvicorn backend.main:app --reload
   ```

### Frontend Setup
1. **Get Packages**: `flutter pub get`
2. **Run App**: `flutter run`

## 🧪 Verification
Run the verification suite to ensure system integrity:
```bash
python backend/scripts/verify_security.py
python backend/scripts/verify_module2.py
```
