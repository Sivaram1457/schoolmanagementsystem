"""
routers/admin.py — Admin-only endpoints for managing School Structure & Users.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import hash_password, require_role
from database import get_db
from models import Class, User, UserRole
from schemas import (
    ClassCreate, ClassOut,
    StudentCreate, TeacherCreate, ParentCreate, UserOut
)

# Protect all routes in this router with strictly "admin" role
router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"],
    dependencies=[Depends(require_role(["admin"]))]
)


# ── Classes Management ────────────────────────────────────────────────────────

@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    """Create a new class (e.g. 10A)."""
    # Check uniqueness
    existing = db.query(Class).filter(Class.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Class with this name already exists")
    
    new_class = Class(**payload.model_dump())
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return new_class


@router.get("/classes", response_model=List[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    """List all classes."""
    return db.query(Class).all()


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: Session = Depends(get_db)):
    """Delete a class by ID."""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Check if students are assigned? (Optional safety check)
    if db.query(User).filter(User.class_id == class_id).first():
       raise HTTPException(status_code=400, detail="Cannot delete class with assigned students")

    db.delete(cls)
    db.commit()


# ── Students Management ───────────────────────────────────────────────────────

@router.post("/students", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """Create a new Student assigned to a Class."""
    # Validate Class exists
    cls = db.query(Class).filter(Class.id == payload.class_id).first()
    if not cls:
        raise HTTPException(status_code=400, detail=f"Class ID {payload.class_id} does not exist")
    
    # Check Email Uniqueness
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.student,
        class_id=payload.class_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/students", response_model=List[UserOut])
def list_students(class_id: int | None = None, db: Session = Depends(get_db)):
    """List all students, optionally filtered by class_id."""
    query = db.query(User).filter(User.role == UserRole.student)
    if class_id:
        query = query.filter(User.class_id == class_id)
    return query.all()


@router.get("/students/{user_id}", response_model=UserOut)
def get_student(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    return user


@router.put("/students/{user_id}", response_model=UserOut)
def update_student(user_id: int, payload: StudentCreate, db: Session = Depends(get_db)):
    """Update student details."""
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Validate new class if changed
    if payload.class_id != user.class_id:
        if not db.query(Class).filter(Class.id == payload.class_id).first():
             raise HTTPException(status_code=400, detail="Invalid Class ID")

    user.full_name = payload.full_name
    user.email = payload.email # Could check unique again if changed
    user.class_id = payload.class_id
    # Password update logic omitted for brevity unless requested, usually separate endpoint
    # user.password_hash = hash_password(payload.password) 
    
    db.commit()
    db.refresh(user)
    return user


# ── Teachers Management ───────────────────────────────────────────────────────

@router.post("/teachers", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    """Create a new Teacher."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.teacher
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/teachers", response_model=List[UserOut])
def list_teachers(db: Session = Depends(get_db)):
    """List all teachers."""
    return db.query(User).filter(User.role == UserRole.teacher).all()


# ── Parents Management ────────────────────────────────────────────────────────

@router.post("/parents", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_parent(payload: ParentCreate, db: Session = Depends(get_db)):
    """Create a new Parent linked to one or more Students."""
    
    # 1. Check Email Uniqueness
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Verify all students exist
    # Convert list to set to remove duplicates if any
    student_ids = set(payload.student_ids)
    students = db.query(User).filter(User.id.in_(student_ids), User.role == UserRole.student).all()
    
    if len(students) != len(student_ids):
        found_ids = {s.id for s in students}
        missing = student_ids - found_ids
        raise HTTPException(status_code=400, detail=f"Student IDs not found: {missing}")

    # 3. Create Parent and Link Students
    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.parent,
        # linked_student_id removed
    )
    
    # SQLAlchemy M2M magic: just append to the relationship list
    new_user.children = students

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
