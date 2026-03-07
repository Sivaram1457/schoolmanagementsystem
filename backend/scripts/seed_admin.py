"""
seed_admin.py — Creates an initial admin user so you can use the /auth/register endpoint.

Usage:
    python seed_admin.py
"""

from backend.database import SessionLocal, engine, Base
from backend.models import User, UserRole
from backend.auth import hash_password

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

ADMIN_EMAIL = "admin@school.com"
ADMIN_PASSWORD = "admin123"  # Change this in production!

existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
if existing:
    print(f"Admin user already exists: {existing.email}")
else:
    admin = User(
        full_name="System Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.admin,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Admin user created: {admin.email} (id={admin.id})")

db.close()
