from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

files = {
    'backend/models.py': ['is_active = Column'],
    'backend/routers/auth.py': ['if not user.is_active'],
    'backend/routers/admin.py': ['def list_students', 'def bulk_upload_students', 'def deactivate_user'],
    'backend/schemas.py': ['class PaginatedResponse', 'class StudentBulkUploadResponse'],
    'alembic/versions/8c9d1ef4b5a4_add_active_flag_to_users.py': ['def upgrade', 'def downgrade'],
    'backend/data/example_student_bulk_upload.csv': ['full_name']
}

for rel_path, keywords in files.items():
    path = ROOT / rel_path
    if not path.exists():
        continue
    print(f"=== {rel_path} ===")
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        for keyword in keywords:
            if keyword in line:
                print(f"{i}: {line.strip()}")
    print()
