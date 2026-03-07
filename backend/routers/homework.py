"""
routers/homework.py — Homework management endpoints.
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.auth import require_role
from backend.database import get_db
from backend.models import Homework, User, UserRole, Class, AcademicMapping, HomeworkSubmission
from backend.schemas import (
    HomeworkCreate, HomeworkUpdate, HomeworkResponse, HomeworkResponseWithCompletion,
    HomeworkCompletionOut, SubmissionOut
)

router = APIRouter(prefix="/homework", tags=["Homework"])


@router.post(
    "/",
    response_model=HomeworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create homework (Teachers only)",
)
def create_homework(
    payload: HomeworkCreate,
    current_user: User = Depends(require_role(["teacher"])),
    db: Session = Depends(get_db),
):
    """
    Create a new homework entry.
    - Only teachers can create.
    - Teacher must be academically mapped to the class.
    - Due date must be in the future (or today).
    """
    # 1. Validate due date
    if payload.due_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Due date cannot be in the past",
        )

    # 2. Verify class exists
    target_class = db.query(Class).filter(Class.id == payload.class_id).first()
    if not target_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # 3. Validate Academic Mapping
    mapping = db.query(AcademicMapping).filter(
        AcademicMapping.teacher_id == current_user.id,
        AcademicMapping.class_id == payload.class_id
    ).first()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not assigned to Class {payload.class_id}.",
        )

    # 4. Create record
    homework = Homework(
        class_id=payload.class_id,
        teacher_id=current_user.id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
    )
    db.add(homework)
    db.commit()
    db.refresh(homework)
    return homework


@router.put(
    "/{homework_id}",
    response_model=HomeworkResponse,
    summary="Update homework (Teacher/Admin only)",
)
def update_homework(
    homework_id: int,
    payload: HomeworkUpdate,
    current_user: User = Depends(require_role(["teacher", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Update an existing homework entry.
    - Original teacher OR Admin can update.
    - Cannot update if deleted.
    """
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework or homework.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Homework not found or deleted",
        )

    # Ownership check
    if current_user.role != UserRole.admin and homework.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this homework",
        )

    # Update fields
    if payload.title is not None:
        homework.title = payload.title
    if payload.description is not None:
        homework.description = payload.description
    if payload.due_date is not None:
        if payload.due_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Due date cannot be in the past",
            )
        homework.due_date = payload.due_date

    db.commit()
    db.refresh(homework)
    return homework


@router.delete(
    "/{homework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete homework (Teacher/Admin only)",
)
def delete_homework(
    homework_id: int,
    current_user: User = Depends(require_role(["teacher", "admin"])),
    db: Session = Depends(get_db),
):
    """Soft delete a homework entry."""
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework or homework.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Homework not found or already deleted",
        )

    # Ownership check
    if current_user.role != UserRole.admin and homework.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this homework",
        )

    homework.is_deleted = True
    db.commit()


@router.get(
    "/me",
    response_model=List[HomeworkResponseWithCompletion],
    summary="Get my class homework (Students only)",
)
def get_my_homework(
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """Fetch homework for the logged-in student's class."""
    if not current_user.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not assigned to any class",
        )

    homeworks = db.query(Homework).filter(
        Homework.class_id == current_user.class_id,
        Homework.is_deleted == False
    ).order_by(Homework.due_date.asc()).all()

    # Annotate each homework with 'completed' flag for this student
    for hw in homeworks:
        sub = db.query(HomeworkSubmission).filter(
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == current_user.id
        ).first()
        setattr(hw, "completed", bool(sub))

    return homeworks


@router.get(
    "/student/{student_id}",
    response_model=List[HomeworkResponseWithCompletion],
    summary="Get child's class homework (Parents only)",
)
def get_child_homework(
    student_id: int,
    current_user: User = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    """Fetch homework for a parent's linked student."""
    # Check if student is a child of this parent
    is_child = any(child.id == student_id for child in current_user.children)
    if not is_child:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this student's homework",
        )

    student = db.query(User).filter(User.id == student_id).first()
    if not student or not student.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student has no class assigned",
        )

    homeworks = db.query(Homework).filter(
        Homework.class_id == student.class_id,
        Homework.is_deleted == False
    ).order_by(Homework.due_date.asc()).all()

    for hw in homeworks:
        sub = db.query(HomeworkSubmission).filter(
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == student_id
        ).first()
        setattr(hw, "completed", bool(sub))

    return homeworks


# ── Student: Mark Homework Completed ─────────────────────────────────────────


@router.post(
    "/{homework_id}/complete",
    response_model=HomeworkCompletionOut,
    summary="Mark homework as completed (Students only)",
)
def complete_homework(
    homework_id: int,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    hw = db.query(Homework).filter(Homework.id == homework_id, Homework.is_deleted == False).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    # Student must belong to the class
    if current_user.class_id != hw.class_id:
        raise HTTPException(status_code=403, detail="You are not a student of this class")

    existing = db.query(HomeworkSubmission).filter(
        HomeworkSubmission.homework_id == homework_id,
        HomeworkSubmission.student_id == current_user.id
    ).with_for_update().first()

    if existing:
        existing.is_completed = True
        existing.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    sub = HomeworkSubmission(homework_id=homework_id, student_id=current_user.id, is_completed=True)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ── Teacher/Admin: View Submissions ──────────────────────────────────────────


@router.get(
    "/{homework_id}/submissions",
    response_model=List[SubmissionOut],
    summary="List submissions for a homework (Teacher/Admin)",
)
def list_homework_submissions(
    homework_id: int,
    current_user: User = Depends(require_role(["teacher", "admin"])),
    db: Session = Depends(get_db),
):
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    # Teacher must be the owner (admin bypasses)
    if current_user.role != UserRole.admin and hw.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to view submissions for this homework")

    subs = db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == homework_id).all()
    return subs


@router.get(
    "/my",
    response_model=List[HomeworkResponse],
    summary="Get my created homework (Teachers)",
)
def get_my_created_homework(
    current_user: User = Depends(require_role(["teacher"])),
    db: Session = Depends(get_db),
):
    return db.query(Homework).filter(Homework.teacher_id == current_user.id, Homework.is_deleted == False).order_by(Homework.due_date.asc()).all()


@router.get(
    "/class/{class_id}",
    response_model=List[HomeworkResponse],
    summary="Get class homework (Admin only)",
)
def get_class_homework(
    class_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Fetch all homework for a specific class (Admin only)."""
    return db.query(Homework).filter(
        Homework.class_id == class_id,
        Homework.is_deleted == False
    ).all()
