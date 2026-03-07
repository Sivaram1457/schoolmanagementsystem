"""
routers/admin.py — Admin-only endpoints for managing School Structure & Users.
"""

import csv
import io
import secrets
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import EmailStr, ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import hash_password, require_role
from backend.database import get_db
from backend.models import AcademicMapping, Class, Subject, User, UserRole
from backend.schemas import (
    AcademicMappingCreate,
    AcademicMappingOut,
    BulkUploadError,
    ClassCreate,
    ClassOut,
    MessageResponse,
    ParentCreate,
    ParentUpdate,
    PaginatedResponse,
    StudentBulkUploadResponse,
    StudentCreate,
    StudentUpdate,
    SubjectCreate,
    SubjectOut,
    TeacherCreate,
    TeacherUpdate,
    UserOut,
)

# Protect all routes in this router with strictly "admin" role
router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"],
    dependencies=[Depends(require_role(["admin"]))],
)

MAX_BULK_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB
CSV_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}
EXPECTED_STUDENT_COLUMNS = {"full_name", "email", "class_id"}


def _paginate(query, page: int, limit: int):
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return total, items


# ── Classes Management ────────────────────────────────────────────────────────

@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    """Create a new class (e.g. 10A)."""
    if db.query(Class).filter(Class.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class with this name already exists")

    new_class = Class(**payload.model_dump())
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return new_class


@router.get("/classes", response_model=PaginatedResponse[ClassOut])
def list_classes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all classes with pagination."""
    query = db.query(Class)
    total, items = _paginate(query, page, limit)
    return PaginatedResponse[ClassOut](items=items, total=total, page=page, limit=limit)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: Session = Depends(get_db)):
    """Delete a class by ID."""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    if db.query(User).filter(User.class_id == class_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete class with assigned students")

    db.delete(cls)
    db.commit()


# ── Students Management ───────────────────────────────────────────────────────

@router.post("/students", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """Create a new Student assigned to a Class."""
    cls = db.query(Class).filter(Class.id == payload.class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Class ID {payload.class_id} does not exist")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.student,
        class_id=payload.class_id,
        is_email_verified=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/students", response_model=PaginatedResponse[UserOut])
def list_students(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    class_id: int | None = None,
    search: str | None = None,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List students with optional filters and pagination."""
    query = db.query(User).filter(User.role == UserRole.student)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    if class_id:
        query = query.filter(User.class_id == class_id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    total, items = _paginate(query, page, limit)
    return PaginatedResponse[UserOut](items=items, total=total, page=page, limit=limit)


@router.get("/students/{user_id}", response_model=UserOut)
def get_student(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return user


@router.put("/students/{user_id}", response_model=UserOut)
def update_student(user_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    """Update student details."""
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    updates = payload.model_dump(exclude_none=True)
    if "email" in updates:
        email = updates["email"]
        if db.query(User).filter(User.email == email, User.id != user_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = email
    if "full_name" in updates:
        user.full_name = updates["full_name"]
    if "class_id" in updates:
        class_id = updates["class_id"]
        if class_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student must belong to a class")
        if not db.query(Class).filter(Class.id == class_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Class ID")
        user.class_id = class_id

    db.commit()
    db.refresh(user)
    return user


# ── Teachers Management ───────────────────────────────────────────────────────

@router.post("/teachers", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    """Create a new Teacher."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.teacher,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/teachers", response_model=PaginatedResponse[UserOut])
def list_teachers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List teachers with pagination and optional search."""
    query = db.query(User).filter(User.role == UserRole.teacher)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    total, items = _paginate(query, page, limit)
    return PaginatedResponse[UserOut](items=items, total=total, page=page, limit=limit)


@router.put("/teachers/{user_id}", response_model=UserOut)
def update_teacher(user_id: int, payload: TeacherUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.teacher).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    updates = payload.model_dump(exclude_none=True)
    if "email" in updates:
        email = updates["email"]
        if db.query(User).filter(User.email == email, User.id != user_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = email
    if "full_name" in updates:
        user.full_name = updates["full_name"]

    db.commit()
    db.refresh(user)
    return user


# ── Parents Management ────────────────────────────────────────────────────────

@router.post("/parents", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_parent(payload: ParentCreate, db: Session = Depends(get_db)):
    """Create a new Parent linked to one or more Students."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    student_ids = set(payload.student_ids)
    students = db.query(User).filter(User.id.in_(student_ids), User.role == UserRole.student).all()
    if len(students) != len(student_ids):
        found_ids = {s.id for s in students}
        missing = student_ids - found_ids
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student IDs not found: {missing}")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.parent,
    )
    new_user.children = students

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/parents", response_model=PaginatedResponse[UserOut])
def list_parents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List parents with pagination and optional search."""
    query = db.query(User).filter(User.role == UserRole.parent)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    total, items = _paginate(query, page, limit)
    return PaginatedResponse[UserOut](items=items, total=total, page=page, limit=limit)


@router.put("/parents/{user_id}", response_model=UserOut)
def update_parent(user_id: int, payload: ParentUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.parent).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")

    updates = payload.model_dump(exclude_none=True)
    if "email" in updates:
        email = updates["email"]
        if db.query(User).filter(User.email == email, User.id != user_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = email
    if "full_name" in updates:
        user.full_name = updates["full_name"]
    if "student_ids" in updates:
        student_ids = set(updates["student_ids"])
        if student_ids:
            students = db.query(User).filter(User.id.in_(student_ids), User.role == UserRole.student).all()
            if len(students) != len(student_ids):
                found_ids = {s.id for s in students}
                missing = student_ids - found_ids
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student IDs not found: {missing}")
            user.children = students
        else:
            user.children = []

    db.commit()
    db.refresh(user)
    return user


@router.post("/students/bulk-upload", response_model=StudentBulkUploadResponse)
def bulk_upload_students(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Bulk upload students via CSV. Skips invalid rows and reports errors."""
    if file.content_type not in CSV_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file required")

    file.file.seek(0, io.SEEK_END)
    size = file.file.tell()
    if size > MAX_BULK_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file must be <= 2MB")
    file.file.seek(0)

    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to decode CSV as UTF-8")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must include a header row")

    header_keys = {header.strip().lower() for header in reader.fieldnames if header}
    if not EXPECTED_STUDENT_COLUMNS.issubset(header_keys):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must include columns: full_name, email, class_id")

    existing_emails = {email.lower() for (email,) in db.query(User.email).all()}
    valid_class_ids = {class_id for (class_id,) in db.query(Class.id).all()}
    errors: List[BulkUploadError] = []
    created = 0
    seen_emails: set[str] = set()

    for row in reader:
        row_number = reader.line_num
        normalized = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        if not any(normalized.values()):
            continue

        full_name = normalized.get("full_name", "")
        email_raw = normalized.get("email", "")
        class_raw = normalized.get("class_id", "")

        if not full_name:
            errors.append(BulkUploadError(row=row_number, error="Full name is required"))
            continue
        if not email_raw:
            errors.append(BulkUploadError(row=row_number, error="Email is required"))
            continue
        try:
            email = EmailStr.validate(email_raw)
        except ValidationError:
            errors.append(BulkUploadError(row=row_number, error="Invalid email format"))
            continue
        email_key = email.lower()
        if email_key in existing_emails or email_key in seen_emails:
            errors.append(BulkUploadError(row=row_number, error="Email already exists"))
            continue

        if not class_raw:
            errors.append(BulkUploadError(row=row_number, error="Class ID is required"))
            continue
        try:
            class_id = int(class_raw)
        except ValueError:
            errors.append(BulkUploadError(row=row_number, error="Class ID must be a number"))
            continue
        if class_id not in valid_class_ids:
            errors.append(BulkUploadError(row=row_number, error="Invalid class_id"))
            continue

        password = secrets.token_urlsafe(12)
        student = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.student,
            class_id=class_id,
            is_email_verified=True,
        )
        db.add(student)
        created += 1
        seen_emails.add(email_key)
        existing_emails.add(email_key)

    if created:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk upload failed due to duplicate or constraint violation.",
            )
    else:
        db.rollback()

    return StudentBulkUploadResponse(created=created, failed=len(errors), errors=errors)


@router.patch("/users/{user_id}/deactivate", response_model=MessageResponse)
def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """Soft deactivate any user so they cannot log in."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        return MessageResponse(detail="User already deactivated")

    user.is_active = False
    db.commit()
    return MessageResponse(detail="User deactivated")


# ── Subjects Management ────────────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    """Create a new subject."""
    if db.query(Subject).filter(Subject.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject already exists")

    new_subject = Subject(**payload.model_dump())
    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)
    return new_subject


@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    """List all subjects."""
    return db.query(Subject).all()


# ── Academic Mapping Management ───────────────────────────────────────────────

@router.post("/mappings", response_model=AcademicMappingOut, status_code=status.HTTP_201_CREATED)
def create_mapping(payload: AcademicMappingCreate, db: Session = Depends(get_db)):
    """Map a Teacher to a Subject and Class."""
    teacher = db.query(User).filter(User.id == payload.teacher_id, User.role == UserRole.teacher).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Teacher ID")

    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Subject ID")

    cls = db.query(Class).filter(Class.id == payload.class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Class ID")

    if db.query(AcademicMapping).filter(
        AcademicMapping.teacher_id == payload.teacher_id,
        AcademicMapping.subject_id == payload.subject_id,
        AcademicMapping.class_id == payload.class_id,
    ).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mapping already exists")

    new_mapping = AcademicMapping(**payload.model_dump())
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)
    return new_mapping


@router.get("/mappings", response_model=List[AcademicMappingOut])
def list_mappings(teacher_id: int | None = None, db: Session = Depends(get_db)):
    """List all mappings, optionally filtered by teacher."""
    query = db.query(AcademicMapping)
    if teacher_id:
        query = query.filter(AcademicMapping.teacher_id == teacher_id)
    return query.all()
