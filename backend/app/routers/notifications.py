from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationOut, UnreadCountOut
from app.core.deps import get_current_active_user
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=List[NotificationOut],
    summary="Get My Notifications",
    description="Retrieves notifications (booking confirmations, reminders, cancellations, completions) for the logged-in user.",
)
def get_my_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return notification_service.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    summary="Get Unread Notifications Count",
    description="Returns the number of unread notifications for badge counters in frontend.",
)
def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = notification_service.count_unread_notifications(db=db, user_id=current_user.id)
    return UnreadCountOut(unread_count=count)


@router.put(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark Notification as Read",
    description="Marks a single notification as read.",
)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_notification_as_read(
        db=db,
        notification_id=notification_id,
        current_user=current_user,
    )


@router.put(
    "/read-all",
    summary="Mark All Notifications as Read",
    description="Marks all unread notifications for the currently logged-in user as read.",
)
def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = notification_service.mark_all_notifications_as_read(db=db, current_user=current_user)
    return {"message": f"{count} notifications marked as read.", "updated_count": count}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Notification",
    description="Deletes a notification from user inbox.",
)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    notification_service.delete_notification(db=db, notification_id=notification_id, current_user=current_user)
    return None
