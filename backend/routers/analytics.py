"""
routers/analytics.py — Analytics Engine for the School Management System.

All aggregate queries exclude calendar entries typed as ``holiday`` or
``non_working`` from the school-days denominator when computing attendance %.

Endpoints
---------
GET /analytics/student/{student_id}                  admin | teacher | self
GET /analytics/class/{class_id}                      admin | teacher
GET /analytics/attendance-trends/{class_id}          admin | teacher
GET /analytics/homework-completion/{class_id}        admin | teacher
"""

from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import (
    AcademicCalendar,
    Attendance,
    AttendanceStatus,
    CalendarEntryType,
    Class,
    Homework,
    HomeworkSubmission,
    User,
    UserRole,
)
from backend.schemas import (
    AttendanceTrend,
    AttendanceTrendPoint,
    ClassAnalytics,
    HomeworkAnalyticsItem,
    StudentAnalytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# ── Private helpers ────────────────────────────────────────────────────────────

def _holiday_dates(db: Session, year: Optional[int] = None):
    """
    Return a set of ``date`` objects that are holidays or non-working days.
    If *year* is None, returns all recorded holidays.
    """
    from sqlalchemy import extract
    q = db.query(AcademicCalendar.date).filter(
        AcademicCalendar.type.in_([
            CalendarEntryType.holiday,
            CalendarEntryType.non_working,
        ])
    )
    if year:
        q = q.filter(extract("year", AcademicCalendar.date) == year)
    return {row[0] for row in q.all()}


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/student/{student_id}",
    response_model=StudentAnalytics,
    summary="Full analytics for a single student (admin | teacher | self)",
)
def student_analytics(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns:

    - Attendance rate (holidays / non-working days excluded from denominator)
    - Homework completion rate

    **Access rules**:
    - Admin / teacher: any student
    - Student: only themselves
    - Parent: their linked children (enforced by 403 check)
    """
    # RBAC
    is_admin_or_teacher = current_user.role in (UserRole.admin, UserRole.teacher)
    if not is_admin_or_teacher:
        if current_user.role == UserRole.student and current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Students can only view their own analytics")
        if current_user.role == UserRole.parent:
            child_ids = {c.id for c in current_user.children}
            if student_id not in child_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Parents can only view analytics for their linked children")

    student = db.query(User).filter(
        User.id == student_id,
        User.role == UserRole.student,
        User.is_active == True,  # noqa: E712
    ).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Active student with id={student_id} not found")

    cls = db.query(Class).filter(Class.id == student.class_id).first() if student.class_id else None

    # ── Attendance ────────────────────────────────────────────────────────────
    holidays = _holiday_dates(db)

    attendance_records = (
        db.query(Attendance)
        .filter(
            Attendance.student_id == student_id,
            Attendance.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    # Exclude holiday/non-working dates from the denominator
    non_holiday_records = [a for a in attendance_records if a.date not in holidays]
    total_school_days = len(non_holiday_records)
    holidays_excluded = len(attendance_records) - total_school_days
    days_present = sum(1 for a in non_holiday_records if a.status == AttendanceStatus.present)
    days_absent = total_school_days - days_present

    # ── Homework ──────────────────────────────────────────────────────────────
    if student.class_id:
        total_hw = (
            db.query(func.count(Homework.id))
            .filter(
                Homework.class_id == student.class_id,
                Homework.is_deleted == False,  # noqa: E712
            )
            .scalar()
        ) or 0

        submitted_hw = (
            db.query(func.count(HomeworkSubmission.id))
            .join(Homework, HomeworkSubmission.homework_id == Homework.id)
            .filter(
                Homework.class_id == student.class_id,
                Homework.is_deleted == False,  # noqa: E712
                HomeworkSubmission.student_id == student_id,
                HomeworkSubmission.is_completed == True,  # noqa: E712
            )
            .scalar()
        ) or 0
    else:
        total_hw = submitted_hw = 0

    return StudentAnalytics(
        student_id=student.id,
        student_name=student.full_name,
        class_id=student.class_id,
        class_name=cls.name if cls else None,
        total_school_days=total_school_days,
        holidays_excluded=holidays_excluded,
        days_present=days_present,
        days_absent=days_absent,
        attendance_pct=_pct(days_present, total_school_days),
        total_homework=total_hw,
        homework_submitted=submitted_hw,
        homework_completion_pct=_pct(submitted_hw, total_hw),
    )


@router.get(
    "/class/{class_id}",
    response_model=ClassAnalytics,
    summary="Aggregate analytics for an entire class (admin | teacher)",
)
def class_analytics(
    class_id: int,
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Returns:

    - ``avg_attendance_pct`` — mean of each student's individual attendance %
    - ``avg_homework_completion_pct`` — mean completion rate across all active homework
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Class {class_id} not found")

    students = (
        db.query(User)
        .filter(User.class_id == class_id, User.role == UserRole.student, User.is_active == True)  # noqa: E712
        .all()
    )
    total_students = len(students)
    if total_students == 0:
        return ClassAnalytics(
            class_id=class_id, class_name=cls.name,
            total_students=0,
            avg_attendance_pct=0.0,
            avg_homework_completion_pct=0.0,
        )

    holidays = _holiday_dates(db)

    # Per-student attendance %
    att_pcts: list[float] = []
    for s in students:
        records = (
            db.query(Attendance)
            .filter(Attendance.student_id == s.id, Attendance.is_deleted == False)  # noqa: E712
            .all()
        )
        non_hol = [r for r in records if r.date not in holidays]
        present = sum(1 for r in non_hol if r.status == AttendanceStatus.present)
        att_pcts.append(_pct(present, len(non_hol)))

    avg_att = round(sum(att_pcts) / total_students, 2)

    # Class homework completion % — per-assignment then averaged
    homework_list = (
        db.query(Homework)
        .filter(Homework.class_id == class_id, Homework.is_deleted == False)  # noqa: E712
        .all()
    )
    if homework_list:
        hw_pcts: list[float] = []
        for hw in homework_list:
            submitted = (
                db.query(func.count(HomeworkSubmission.id))
                .filter(
                    HomeworkSubmission.homework_id == hw.id,
                    HomeworkSubmission.is_completed == True,  # noqa: E712
                )
                .scalar()
            ) or 0
            hw_pcts.append(_pct(submitted, total_students))
        avg_hw = round(sum(hw_pcts) / len(hw_pcts), 2)
    else:
        avg_hw = 0.0

    return ClassAnalytics(
        class_id=class_id,
        class_name=cls.name,
        total_students=total_students,
        avg_attendance_pct=avg_att,
        avg_homework_completion_pct=avg_hw,
    )


@router.get(
    "/attendance-trends/{class_id}",
    response_model=AttendanceTrend,
    summary="Weekly attendance trend for a class (admin | teacher)",
)
def attendance_trends(
    class_id: int,
    weeks: int = Query(12, ge=1, le=52, description="Number of past weeks to include"),
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Returns one data point per ISO calendar week for the last *weeks* weeks.

    Each point contains:
    - ``period_label`` — ISO week string like ``"2026-W10"``
    - ``school_days`` — distinct dates attendance was recorded (minus holidays)
    - ``present_count`` — total PRESENT marks across all students that week
    - ``attendance_pct`` — present / (students × school_days) × 100

    Holidays and non-working days are excluded from ``school_days``.
    """
    from datetime import timedelta

    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Class {class_id} not found")

    today = DateType.today()
    start_date = today - timedelta(weeks=weeks)

    holidays = _holiday_dates(db)

    # Count students
    total_students = (
        db.query(func.count(User.id))
        .filter(User.class_id == class_id, User.role == UserRole.student, User.is_active == True)  # noqa: E712
        .scalar()
    ) or 0

    # Fetch all attendance in window for this class
    records = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == class_id,
            Attendance.is_deleted == False,  # noqa: E712
            Attendance.date >= start_date,
            Attendance.date <= today,
        )
        .order_by(Attendance.date)
        .all()
    )

    # Group into ISO weeks
    from collections import defaultdict
    week_data: dict[str, dict] = defaultdict(lambda: {"dates": set(), "present": 0})

    for rec in records:
        if rec.date in holidays:
            continue
        iso = rec.date.isocalendar()
        week_label = f"{iso.year}-W{iso.week:02d}"
        week_data[week_label]["dates"].add(rec.date)
        if rec.status == AttendanceStatus.present:
            week_data[week_label]["present"] += 1

    # Build trend sorted chronologically
    trend: list[AttendanceTrendPoint] = []
    for label in sorted(week_data.keys()):
        info = week_data[label]
        school_days = len(info["dates"])
        present = info["present"]
        denom = total_students * school_days
        trend.append(AttendanceTrendPoint(
            period_label=label,
            school_days=school_days,
            present_count=present,
            attendance_pct=_pct(present, denom),
        ))

    return AttendanceTrend(class_id=class_id, class_name=cls.name, trend=trend)


@router.get(
    "/homework-completion/{class_id}",
    response_model=list[HomeworkAnalyticsItem],
    summary="Per-homework completion stats for a class (admin | teacher)",
)
def homework_completion(
    class_id: int,
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Returns one item per active homework assignment for *class_id*.

    Each item shows:
    - ``total_students`` in the class
    - ``submitted`` count (is_completed=True)
    - ``completion_pct``
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Class {class_id} not found")

    total_students = (
        db.query(func.count(User.id))
        .filter(User.class_id == class_id, User.role == UserRole.student, User.is_active == True)  # noqa: E712
        .scalar()
    ) or 0

    homework_list = (
        db.query(Homework)
        .filter(Homework.class_id == class_id, Homework.is_deleted == False)  # noqa: E712
        .order_by(Homework.due_date.desc())
        .all()
    )

    result: list[HomeworkAnalyticsItem] = []
    for hw in homework_list:
        submitted = (
            db.query(func.count(HomeworkSubmission.id))
            .filter(
                HomeworkSubmission.homework_id == hw.id,
                HomeworkSubmission.is_completed == True,  # noqa: E712
            )
            .scalar()
        ) or 0
        result.append(HomeworkAnalyticsItem(
            homework_id=hw.id,
            title=hw.title,
            due_date=hw.due_date,
            total_students=total_students,
            submitted=submitted,
            completion_pct=_pct(submitted, total_students),
        ))

    return result
