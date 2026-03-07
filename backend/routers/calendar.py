"""
routers/calendar.py — Academic Calendar System.

Admin manages calendar entries (holidays, exams, events, non-working days).
All authenticated users can read entries.

Endpoints
---------
POST   /calendar/                      admin only  — create entry
GET    /calendar/                      any role    — list (optional ?year=, ?type=)
GET    /calendar/{entry_id}            any role    — single entry
PUT    /calendar/{entry_id}            admin only  — update
DELETE /calendar/{entry_id}            admin only  — delete
GET    /calendar/holidays/{year}       any role    — only holiday/non_working dates
"""

from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import AcademicCalendar, CalendarEntryType, User
from backend.schemas import CalendarEntryCreate, CalendarEntryOut

router = APIRouter(prefix="/calendar", tags=["Academic Calendar"])


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=CalendarEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create calendar entry (admin only)",
)
def create_calendar_entry(
    payload: CalendarEntryCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Add a date to the academic calendar.

    ``type`` must be one of: ``holiday``, ``exam``, ``event``, ``non_working``.

    Unique constraint: same date + same type cannot be inserted twice.
    """
    # Check for duplicate date+type
    existing = db.query(AcademicCalendar).filter(
        AcademicCalendar.date == payload.date,
        AcademicCalendar.type == payload.type,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A '{payload.type.value}' entry for {payload.date} already exists (id={existing.id})",
        )

    entry = AcademicCalendar(
        date=payload.date,
        type=payload.type,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get(
    "/holidays/{year}",
    response_model=list[CalendarEntryOut],
    summary="List all non-school days in a given year (holidays + non_working)",
)
def list_holidays(
    year: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns every ``holiday`` and ``non_working`` entry for *year*.

    Used by the analytics engine to exclude these dates from attendance denominators.
    """
    from sqlalchemy import extract
    return (
        db.query(AcademicCalendar)
        .filter(
            extract("year", AcademicCalendar.date) == year,
            AcademicCalendar.type.in_([
                CalendarEntryType.holiday,
                CalendarEntryType.non_working,
            ]),
        )
        .order_by(AcademicCalendar.date)
        .all()
    )


@router.get(
    "/",
    response_model=list[CalendarEntryOut],
    summary="List calendar entries (all roles)",
)
def list_calendar_entries(
    year: Optional[int] = Query(None, description="Filter by year, e.g. 2026"),
    type: Optional[CalendarEntryType] = Query(None, description="Filter by entry type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List academic calendar entries.

    - Optionally filter by ``year`` and/or ``type``.
    - Results ordered chronologically.
    """
    from sqlalchemy import extract
    q = db.query(AcademicCalendar)
    if year:
        q = q.filter(extract("year", AcademicCalendar.date) == year)
    if type:
        q = q.filter(AcademicCalendar.type == type)
    return q.order_by(AcademicCalendar.date).all()


@router.get(
    "/{entry_id}",
    response_model=CalendarEntryOut,
    summary="Get a single calendar entry",
)
def get_calendar_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(AcademicCalendar).filter(AcademicCalendar.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar entry {entry_id} not found",
        )
    return entry


@router.put(
    "/{entry_id}",
    response_model=CalendarEntryOut,
    summary="Update a calendar entry (admin only)",
)
def update_calendar_entry(
    entry_id: int,
    payload: CalendarEntryCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    entry = db.query(AcademicCalendar).filter(AcademicCalendar.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar entry {entry_id} not found",
        )
    entry.date = payload.date
    entry.type = payload.type
    entry.description = payload.description
    db.commit()
    db.refresh(entry)
    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a calendar entry (admin only)",
)
def delete_calendar_entry(
    entry_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    entry = db.query(AcademicCalendar).filter(AcademicCalendar.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar entry {entry_id} not found",
        )
    db.delete(entry)
    db.commit()
