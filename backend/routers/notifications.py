"""
routers/notifications.py — Per-user Notification Storage.

Endpoints
---------
GET    /notifications/me          any role  — own notifications
PUT    /notifications/{id}/read   any role  — mark as read
DELETE /notifications/{id}        any role  — delete own notification

Internal helper
---------------
create_notification(db, user_id, title, message)  — called by other routers
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Notification, User
from backend.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Internal helper (importable by other routers) ──────────────────────────────

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
) -> Notification:
    """
    Persist a new notification for *user_id*.

    Call this from any router that needs to push a notification, e.g.:

        from backend.routers.notifications import create_notification
        create_notification(db, student.id, "Homework due", "Math HW due tomorrow")
    """
    notif = Notification(user_id=user_id, title=title, message=message)
    db.add(notif)
    db.flush()  # caller should commit
    return notif


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=list[NotificationOut],
    summary="My notifications (newest first)",
)
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all notifications for the authenticated user, newest first."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.put(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark a notification as read",
)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark *notification_id* as read. Users may only update their own notifications."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hard-delete a notification. Users may only delete their own."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    db.delete(notif)
    db.commit()
