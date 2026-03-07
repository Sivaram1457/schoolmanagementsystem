"""
routers/timetable.py — Timetable Engine endpoints.

Admin endpoints (prefix /admin):
  POST   /admin/periods             — Create a school period
  GET    /admin/periods             — List all periods
  POST   /admin/rooms               — Create a classroom
  GET    /admin/rooms               — List all rooms
  POST   /admin/timetable           — Create a timetable slot
  PUT    /admin/timetable/{id}      — Update a timetable slot
  DELETE /admin/timetable/{id}      — Delete a timetable slot

Shared read endpoints (prefix /timetable):
  GET /timetable/class/{class_id}       — Weekly timetable for a class
  GET /timetable/teacher/{teacher_id}   — Weekly timetable for a teacher
  GET /timetable/student/{student_id}   — Weekly timetable for a student's class
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import (
    Class,
    Period,
    Room,
    Subject,
    TimetableSlot,
    User,
    UserRole,
)
from backend.schemas import (
    PeriodCreate,
    PeriodOut,
    RoomCreate,
    RoomOut,
    TimetableSlotCreate,
    TimetableSlotOut,
    TimetableSlotUpdate,
)

# ── Two separate routers merged into one module ───────────────────────────────
# Admin-gated management router
admin_router = APIRouter(
    prefix="/admin",
    tags=["Timetable — Admin"],
    dependencies=[Depends(require_role(["admin"]))],
)

# Shared read-only router (any authenticated user)
timetable_router = APIRouter(
    prefix="/timetable",
    tags=["Timetable"],
)

# ── Helper ────────────────────────────────────────────────────────────────────

def _get_slot_or_404(slot_id: int, db: Session) -> TimetableSlot:
    slot = db.query(TimetableSlot).filter(TimetableSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable slot not found")
    return slot


def _check_conflicts(
    db: Session,
    teacher_id: int,
    room_id: int,
    day_of_week: int,
    period_id: int,
    exclude_slot_id: int | None = None,
) -> None:
    """
    Raise 409 if the proposed slot would cause:
      • A teacher double-booking (same teacher, day, period)
      • A room double-booking  (same room, day, period)
    Pass *exclude_slot_id* when updating so the current slot is ignored.
    """
    teacher_q = db.query(TimetableSlot).filter(
        TimetableSlot.teacher_id == teacher_id,
        TimetableSlot.day_of_week == day_of_week,
        TimetableSlot.period_id == period_id,
    )
    room_q = db.query(TimetableSlot).filter(
        TimetableSlot.room_id == room_id,
        TimetableSlot.day_of_week == day_of_week,
        TimetableSlot.period_id == period_id,
    )

    if exclude_slot_id:
        teacher_q = teacher_q.filter(TimetableSlot.id != exclude_slot_id)
        room_q = room_q.filter(TimetableSlot.id != exclude_slot_id)

    if teacher_q.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Teacher ID {teacher_id} already has a slot on "
                f"day {day_of_week} during period {period_id}"
            ),
        )

    if room_q.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Room ID {room_id} is already booked on "
                f"day {day_of_week} during period {period_id}"
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — PERIODS
# ─────────────────────────────────────────────────────────────────────────────

@admin_router.post(
    "/periods",
    response_model=PeriodOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a school period (Admin only)",
)
def create_period(payload: PeriodCreate, db: Session = Depends(get_db)):
    """Create a named period with start/end time."""
    if db.query(Period).filter(Period.period_number == payload.period_number).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Period number {payload.period_number} already exists",
        )

    # Basic time sanity check
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time",
        )

    period = Period(**payload.model_dump())
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@admin_router.get(
    "/periods",
    response_model=List[PeriodOut],
    summary="List all school periods (Admin only)",
)
def list_periods(db: Session = Depends(get_db)):
    return db.query(Period).order_by(Period.period_number).all()


@admin_router.delete(
    "/periods/{period_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a school period (Admin only)",
)
def delete_period(period_id: int, db: Session = Depends(get_db)):
    """
    Delete a period.
    Returns 409 Conflict if any timetable slots reference this period —
    safe cascades are the caller's responsibility.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")

    # Cascade delete protection: refuse if slots reference this period
    slot_count = db.query(TimetableSlot).filter(TimetableSlot.period_id == period_id).count()
    if slot_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete period '{period.period_number}' — "
                f"{slot_count} timetable slot(s) are still using it. "
                "Remove or reassign those slots first."
            ),
        )

    db.delete(period)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — ROOMS
# ─────────────────────────────────────────────────────────────────────────────

@admin_router.post(
    "/rooms",
    response_model=RoomOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a classroom / lab (Admin only)",
)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)):
    if db.query(Room).filter(Room.room_name == payload.room_name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room '{payload.room_name}' already exists",
        )

    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@admin_router.get(
    "/rooms",
    response_model=List[RoomOut],
    summary="List all rooms (Admin only)",
)
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).order_by(Room.room_name).all()


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — TIMETABLE SLOTS
# ─────────────────────────────────────────────────────────────────────────────

@admin_router.post(
    "/timetable",
    response_model=TimetableSlotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a timetable slot (Admin only)",
)
def create_timetable_slot(payload: TimetableSlotCreate, db: Session = Depends(get_db)):
    """
    Create a new timetable slot.
    Validates existence of class, subject, teacher, room, and period
    before checking scheduling conflicts.
    """
    # Validate FK references
    if not db.query(Class).filter(Class.id == payload.class_id).first():
        raise HTTPException(status_code=404, detail="Class not found")

    if not db.query(Subject).filter(Subject.id == payload.subject_id).first():
        raise HTTPException(status_code=404, detail="Subject not found")

    teacher = db.query(User).filter(
        User.id == payload.teacher_id, User.role == UserRole.teacher
    ).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or is not a teacher",
        )

    if not db.query(Room).filter(Room.id == payload.room_id).first():
        raise HTTPException(status_code=404, detail="Room not found")

    if not db.query(Period).filter(Period.id == payload.period_id).first():
        raise HTTPException(status_code=404, detail="Period not found")

    # Conflict detection
    _check_conflicts(
        db,
        teacher_id=payload.teacher_id,
        room_id=payload.room_id,
        day_of_week=payload.day_of_week,
        period_id=payload.period_id,
    )

    slot = TimetableSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@admin_router.put(
    "/timetable/{slot_id}",
    response_model=TimetableSlotOut,
    summary="Update a timetable slot (Admin only)",
)
def update_timetable_slot(
    slot_id: int,
    payload: TimetableSlotUpdate,
    db: Session = Depends(get_db),
):
    slot = _get_slot_or_404(slot_id, db)
    updates = payload.model_dump(exclude_none=True)

    # Validate any changed FK references
    if "class_id" in updates:
        if not db.query(Class).filter(Class.id == updates["class_id"]).first():
            raise HTTPException(status_code=404, detail="Class not found")
        slot.class_id = updates["class_id"]

    if "subject_id" in updates:
        if not db.query(Subject).filter(Subject.id == updates["subject_id"]).first():
            raise HTTPException(status_code=404, detail="Subject not found")
        slot.subject_id = updates["subject_id"]

    if "teacher_id" in updates:
        teacher = db.query(User).filter(
            User.id == updates["teacher_id"], User.role == UserRole.teacher
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found or is not a teacher",
            )
        slot.teacher_id = updates["teacher_id"]

    if "room_id" in updates:
        if not db.query(Room).filter(Room.id == updates["room_id"]).first():
            raise HTTPException(status_code=404, detail="Room not found")
        slot.room_id = updates["room_id"]

    if "period_id" in updates:
        if not db.query(Period).filter(Period.id == updates["period_id"]).first():
            raise HTTPException(status_code=404, detail="Period not found")
        slot.period_id = updates["period_id"]

    if "day_of_week" in updates:
        slot.day_of_week = updates["day_of_week"]

    # Re-check conflicts with the updated values, excluding self
    _check_conflicts(
        db,
        teacher_id=slot.teacher_id,
        room_id=slot.room_id,
        day_of_week=slot.day_of_week,
        period_id=slot.period_id,
        exclude_slot_id=slot_id,
    )

    db.commit()
    db.refresh(slot)
    return slot


@admin_router.delete(
    "/timetable/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a timetable slot (Admin only)",
)
def delete_timetable_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = _get_slot_or_404(slot_id, db)
    db.delete(slot)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SHARED READ ENDPOINTS — Any authenticated user
# ─────────────────────────────────────────────────────────────────────────────

def _build_weekly_timetable(
    slots: list[TimetableSlot],
) -> dict[int, list[TimetableSlotOut]]:
    """Organise slots into a dict keyed by day_of_week (0-6)."""
    from collections import defaultdict
    weekly: dict[int, list] = defaultdict(list)
    for slot in slots:
        weekly[slot.day_of_week].append(slot)
    # Sort each day by period number
    for day in weekly:
        weekly[day].sort(key=lambda s: s.period.period_number)
    return dict(weekly)


@timetable_router.get(
    "/class/{class_id}",
    response_model=dict[int, List[TimetableSlotOut]],
    summary="Weekly timetable for a class",
)
def get_class_timetable(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full weekly timetable for the given class, grouped by day."""
    if not db.query(Class).filter(Class.id == class_id).first():
        raise HTTPException(status_code=404, detail="Class not found")

    slots = (
        db.query(TimetableSlot)
        .filter(TimetableSlot.class_id == class_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_id)
        .all()
    )
    return _build_weekly_timetable(slots)


@timetable_router.get(
    "/teacher/{teacher_id}",
    response_model=dict[int, List[TimetableSlotOut]],
    summary="Weekly timetable for a teacher",
)
def get_teacher_timetable(
    teacher_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the full weekly timetable for a teacher.
    Teachers can only view their own timetable; admins can view any.
    """
    if current_user.role == UserRole.teacher and current_user.id != teacher_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teachers can only view their own timetable",
        )

    teacher = db.query(User).filter(
        User.id == teacher_id, User.role == UserRole.teacher
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    slots = (
        db.query(TimetableSlot)
        .filter(TimetableSlot.teacher_id == teacher_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_id)
        .all()
    )
    return _build_weekly_timetable(slots)


@timetable_router.get(
    "/student/{student_id}",
    response_model=dict[int, List[TimetableSlotOut]],
    summary="Weekly timetable for a student",
)
def get_student_timetable(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the weekly timetable for a student's assigned class.
    Students can only view their own timetable.
    Parents can view only their linked children's timetables.
    Teachers and Admins can view any student's timetable.
    """
    student = db.query(User).filter(
        User.id == student_id, User.role == UserRole.student
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Role-based access checks
    if current_user.role == UserRole.student and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only view their own timetable",
        )
    if current_user.role == UserRole.parent:
        child_ids = {child.id for child in current_user.children}
        if student_id not in child_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this student's timetable",
            )

    if not student.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not assigned to any class",
        )

    slots = (
        db.query(TimetableSlot)
        .filter(TimetableSlot.class_id == student.class_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_id)
        .all()
    )
    return _build_weekly_timetable(slots)
