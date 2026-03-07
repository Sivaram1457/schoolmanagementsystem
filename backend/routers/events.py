"""
routers/events.py — Event Management System endpoints.

Teacher / Admin:
  POST   /events                         — Create an event
  PUT    /events/{id}                    — Update an event
  DELETE /events/{id}                    — Soft-delete an event
  GET    /events                         — List all active events
  PUT    /events/{id}/participants/{reg_id}/status
                                         — Update a participant's status

Students:
  POST   /events/{id}/register           — Register for an event
  DELETE /events/{id}/register           — Unregister from an event

Any authenticated user:
  GET    /events/{id}/participants       — List participants for an event
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import (
    Class,
    Event,
    EventRegistration,
    EventRegistrationStatus,
    User,
    UserRole,
)
from backend.schemas import (
    EventCreate,
    EventOut,
    EventRegistrationOut,
    EventRegistrationStatusUpdate,
    EventUpdate,
)

router = APIRouter(prefix="/events", tags=["Events"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_event_or_404(event_id: int, db: Session, include_deleted: bool = False) -> Event:
    q = db.query(Event).filter(Event.id == event_id)
    if not include_deleted:
        q = q.filter(Event.is_deleted == False)
    event = q.first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _assert_can_manage(current_user: User):
    """Only teachers and admins may create/update/delete events."""
    if current_user.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can manage events",
        )


def _assert_is_owner_or_admin(event: Event, current_user: User):
    """The teacher who created the event or an admin may modify it."""
    if current_user.role == UserRole.admin:
        return
    if event.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this event",
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEACHER / ADMIN — Event CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a school event (Teacher/Admin)",
)
def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new event.
    - title and event_date are required.
    - class_id is optional; NULL means the event is school-wide.
    - event_date must not be in the past.
    """
    _assert_can_manage(current_user)

    if payload.event_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event_date cannot be in the past",
        )

    if payload.class_id is not None:
        if not db.query(Class).filter(Class.id == payload.class_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    event = Event(
        title=payload.title,
        description=payload.description,
        event_date=payload.event_date,
        class_id=payload.class_id,
        created_by=current_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put(
    "/{event_id}",
    response_model=EventOut,
    summary="Update an event (owner teacher / Admin)",
)
def update_event(
    event_id: int,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_can_manage(current_user)
    event = _get_event_or_404(event_id, db)
    _assert_is_owner_or_admin(event, current_user)

    updates = payload.model_dump(exclude_none=True)

    if "event_date" in updates and updates["event_date"] < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event_date cannot be in the past",
        )

    if "class_id" in updates and updates["class_id"] is not None:
        if not db.query(Class).filter(Class.id == updates["class_id"]).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    for field, value in updates.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an event (owner teacher / Admin)",
)
def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_can_manage(current_user)
    event = _get_event_or_404(event_id, db)
    _assert_is_owner_or_admin(event, current_user)

    event.is_deleted = True
    db.commit()


@router.get(
    "/",
    response_model=List[EventOut],
    summary="List all active events",
)
def list_events(
    class_id: Optional[int] = Query(None, description="Filter by class (returns class-specific + school-wide)"),
    from_date: Optional[date] = Query(None, description="Filter events on or after this date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all non-deleted events.
    - Optionally filter by class_id (returns both class-specific and school-wide events).
    - Optionally filter by from_date.
    - Results are ordered by event_date ascending.
    """
    q = db.query(Event).filter(Event.is_deleted == False)

    if class_id is not None:
        # Show events for this class OR school-wide (class_id IS NULL)
        from sqlalchemy import or_
        q = q.filter(or_(Event.class_id == class_id, Event.class_id.is_(None)))

    if from_date is not None:
        q = q.filter(Event.event_date >= from_date)

    return q.order_by(Event.event_date.asc()).all()


# ─────────────────────────────────────────────────────────────────────────────
# PARTICIPANT STATUS MANAGEMENT — Teacher / Admin only
# ─────────────────────────────────────────────────────────────────────────────

@router.put(
    "/{event_id}/participants/{registration_id}/status",
    response_model=EventRegistrationOut,
    summary="Update a participant's status (Teacher/Admin)",
)
def update_participant_status(
    event_id: int,
    registration_id: int,
    payload: EventRegistrationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Advance a participant's status: registered → attended → winner.
    Only the event owner or an admin may call this.
    """
    _assert_can_manage(current_user)
    event = _get_event_or_404(event_id, db)
    _assert_is_owner_or_admin(event, current_user)

    reg = db.query(EventRegistration).filter(
        EventRegistration.id == registration_id,
        EventRegistration.event_id == event_id,
    ).first()
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    reg.status = payload.status
    db.commit()
    db.refresh(reg)
    return reg


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT — Event Registration
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{event_id}/register",
    response_model=EventRegistrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register for an event (Student)",
)
def register_for_event(
    event_id: int,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """
    Register the authenticated student for the specified event.
    - The event must exist and not be soft-deleted.
    - If the event is class-restricted, the student must belong to that class.
    - A student cannot register for the same event twice.
    """
    event = _get_event_or_404(event_id, db)

    # Class restriction check
    if event.class_id is not None and current_user.class_id != event.class_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This event is restricted to students of a specific class",
        )

    # Duplicate registration check
    existing = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.student_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already registered for this event",
        )

    reg = EventRegistration(
        event_id=event_id,
        student_id=current_user.id,
        status=EventRegistrationStatus.registered,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


@router.delete(
    "/{event_id}/register",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister from an event (Student)",
)
def unregister_from_event(
    event_id: int,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """Cancel the authenticated student's registration for an event."""
    _get_event_or_404(event_id, db)

    reg = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.student_id == current_user.id,
    ).first()
    if not reg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not registered for this event",
        )

    db.delete(reg)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ANY AUTHENTICATED USER — View Participants
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{event_id}/participants",
    response_model=List[EventRegistrationOut],
    summary="List participants for an event",
)
def list_participants(
    event_id: int,
    status_filter: Optional[EventRegistrationStatus] = Query(
        None, alias="status", description="Filter by registration status"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all registrations for the given event.
    - Any authenticated user may call this.
    - Optionally filter by status (registered / attended / winner).
    - Ordered by student name for consistent pagination.
    """
    _get_event_or_404(event_id, db)

    q = db.query(EventRegistration).filter(EventRegistration.event_id == event_id)

    if status_filter is not None:
        q = q.filter(EventRegistration.status == status_filter)

    return q.join(EventRegistration.student).order_by(User.full_name).all()
