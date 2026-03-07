"""
routers/announcements.py — Announcement System.

Endpoints
---------
POST /announcements          admin only  — create
GET  /announcements          admin only  — list all
GET  /announcements/me       any role    — filtered by caller's role
DELETE /announcements/{id}   admin only  — hard delete
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.models import Announcement, AnnouncementTargetRole, User
from backend.schemas import AnnouncementCreate, AnnouncementOut

router = APIRouter(prefix="/announcements", tags=["Announcements"])


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an announcement (admin only)",
)
def create_announcement(
    payload: AnnouncementCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Create a new announcement.

    - ``target_role`` defaults to ``all`` if omitted.
    - Only admin callers can create announcements.
    """
    ann = Announcement(
        title=payload.title,
        message=payload.message,
        target_role=payload.target_role,
        created_by=current_user.id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.get(
    "",
    response_model=list[AnnouncementOut],
    summary="List all announcements (admin only)",
)
def list_all_announcements(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Return every announcement in reverse-chronological order."""
    return (
        db.query(Announcement)
        .order_by(Announcement.created_at.desc())
        .all()
    )


@router.get(
    "/me",
    response_model=list[AnnouncementOut],
    summary="My announcements — filtered by caller role",
)
def my_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return announcements the caller is entitled to see:

    - ``target_role = all`` is always visible.
    - ``target_role = <caller's role>`` is also visible.

    Results are newest-first.
    """
    caller_role = current_user.role.value  # e.g. "student", "teacher", …
    return (
        db.query(Announcement)
        .filter(
            Announcement.target_role.in_(
                [AnnouncementTargetRole.all, AnnouncementTargetRole(caller_role)]
            )
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an announcement (admin only)",
)
def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Hard-delete an announcement by id."""
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Announcement with id={announcement_id} not found",
        )
    db.delete(ann)
    db.commit()
