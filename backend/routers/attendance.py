"""
routers/attendance.py — Attendance management endpoints.
"""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import Attendance, User, UserRole, AttendanceStatus, Class, AcademicMapping
from backend.schemas import (
    AttendanceBulkRequest, AttendanceResponse, AttendanceHistoryResponse, 
    ClassAttendanceStats
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def calculate_percentage(total: int, present: int) -> float:
    if total == 0:
        return 0.0
    return round((present / total) * 100, 2)


@router.post(
    "/bulk",
    response_model=List[AttendanceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk mark attendance (Teachers/Admins)",
)
def bulk_mark_attendance(
    payload: AttendanceBulkRequest,
    current_user: User = Depends(require_role(["teacher", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Mark attendance for multiple students in a class for a specific date.
    - Validate no future dates.
    - 7-Day Lock for Teachers (Admin bypasses).
    - Mapping validation for Teachers (Admin bypasses).
    - Upsert logic for corrections.
    """
    is_admin = current_user.role == UserRole.admin

    if payload.date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark attendance for a future date",
        )

    # 7-Day Lock: Teachers cannot modify records older than 7 days (Admin Bypasses)
    if not is_admin:
        days_diff = (date.today() - payload.date).days
        if days_diff > 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attendance is locked for records older than 7 days. Contact Admin for changes."
            )

    # 1. Verify class exists
    target_class = db.query(Class).filter(Class.id == payload.class_id).first()
    if not target_class:
        raise HTTPException(status_code=404, detail="Class not found")

    # 2. VALIDATE MAPPING: Does this teacher teach this class? (Admin Bypasses)
    if not is_admin:
        mapping = db.query(AcademicMapping).filter(
            AcademicMapping.teacher_id == current_user.id,
            AcademicMapping.class_id == payload.class_id
        ).first()
        
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You are not assigned to Class {payload.class_id}."
            )

    # 3. Extract student IDs
    student_ids = [s.student_id for s in payload.students]

    # 4. Verify all students exist and belong to the correct class
    students_in_db = db.query(User).filter(
        User.id.in_(student_ids), 
        User.role == UserRole.student,
        User.class_id == payload.class_id
    ).all()

    found_ids = {s.id for s in students_in_db}
    missing_ids = [sid for sid in student_ids if sid not in found_ids]

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The following students are not in class {payload.class_id}: {missing_ids}",
        )

    # 5. Bulk Create/Update (UPSERT with Pessimistic Locking)
    new_records = []
    for s in payload.students:
        # Check if record exists for this student + date (including soft-deleted)
        # We use with_for_update() to lock the row and prevent race conditions
        existing_record = db.query(Attendance).filter(
            Attendance.student_id == s.student_id,
            Attendance.date == payload.date
        ).with_for_update().first()

        if existing_record:
            # Update existing status and reactivate if it was soft-deleted
            existing_record.status = s.status
            existing_record.last_updated_by = current_user.id
            existing_record.is_deleted = False
            new_records.append(existing_record)
        else:
            # Create new record
            record = Attendance(
                student_id=s.student_id,
                class_id=payload.class_id,
                date=payload.date,
                status=s.status,
                marked_by=current_user.id
            )
            db.add(record)
            new_records.append(record)

    try:
        db.commit()
        for r in new_records:
            db.refresh(r)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during bulk insert: {str(e)}")

    return new_records


@router.get(
    "/me",
    response_model=AttendanceHistoryResponse,
    summary="Get my attendance history (Students only)",
)
def get_my_attendance(
    current_student: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """Returns the attendance history and percentage for the logged-in student."""
    records = db.query(Attendance).filter(
        Attendance.student_id == current_student.id,
        Attendance.is_deleted == False
    ).order_by(Attendance.date.desc()).all()
    
    total_days = len(records)
    present_days = len([r for r in records if r.status == AttendanceStatus.present])
    
    return AttendanceHistoryResponse(
        history=records,
        attendance_percentage=calculate_percentage(total_days, present_days),
        total_days=total_days,
        days_present=present_days
    )


@router.get(
    "/student/{student_id}",
    response_model=AttendanceHistoryResponse,
    summary="Get child's attendance (Parents only)",
)
def get_child_attendance(
    student_id: int,
    current_parent: User = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    """
    Returns history for a student if the current user is their linked parent.
    """
    # Check if this student is a child of the current parent
    # Using the relationship defined in User model (M2M)
    is_child = any(child.id == student_id for child in current_parent.children)
    
    if not is_child:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this student's attendance",
        )

    records = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.is_deleted == False
    ).order_by(Attendance.date.desc()).all()
    
    total_days = len(records)
    present_days = len([r for r in records if r.status == AttendanceStatus.present])
    
    return AttendanceHistoryResponse(
        history=records,
        attendance_percentage=calculate_percentage(total_days, present_days),
        total_days=total_days,
        days_present=present_days
    )


# ── Admin Analytics ────────────────────────────────────────────────────────────

@router.get(
    "/stats/class/{class_id}",
    response_model=ClassAttendanceStats,
    summary="Get class attendance statistics (Admin only)",
)
def get_class_stats(
    class_id: int,
    current_admin: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Returns analytics for a specific class."""
    target_class = db.query(Class).filter(Class.id == class_id).first()
    if not target_class:
        raise HTTPException(status_code=404, detail="Class not found")
    
    total_students = db.query(User).filter(User.class_id == class_id, User.role == UserRole.student).count()
    
    # All attendance records for this class
    records = db.query(Attendance).filter(
        Attendance.class_id == class_id,
        Attendance.is_deleted == False
    ).all()
    total_records = len(records)
    days_present = len([r for r in records if r.status == AttendanceStatus.present])
    
    return ClassAttendanceStats(
        class_id=class_id,
        class_name=target_class.name,
        total_students=total_students,
        total_records=total_records,
        attendance_percentage=calculate_percentage(total_records, days_present)
    )
