from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.schedule import (
    ScheduleOut,
    ScheduleCreate,
    ScheduleUpdate,
    BlockedPeriodOut,
    BlockedPeriodCreate,
    DailyScheduleDetail,
)
from app.core.deps import get_current_active_user, require_admin, require_barber
from app.services import schedule_service, barber_service

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.get(
    "/barber/{barber_id}",
    response_model=List[ScheduleOut],
    summary="Get Barber Working Schedules",
    description="Retrieves weekly recurring and date-specific schedules for a barber.",
)
def get_barber_schedules(
    barber_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    return schedule_service.get_barber_schedules(db, barber_id=barber_id, active_only=active_only)


@router.get(
    "/barber/{barber_id}/effective-date",
    response_model=DailyScheduleDetail,
    summary="Get Barber Effective Daily Shift",
    description="Resolves working hours, defined breaks, and active blocked periods for a specific date.",
)
def get_barber_effective_date(
    barber_id: int,
    target_date: date = Query(..., description="Target date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    return schedule_service.get_effective_daily_schedule(db, barber_id=barber_id, target_date=target_date)


@router.post(
    "",
    response_model=ScheduleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Working Schedule",
    description="Creates a recurring or date-specific working schedule with breaks for a barber.",
)
def create_schedule(
    schedule_in: ScheduleCreate,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    # If barber role, ensure they are configuring their own schedule
    if current_user.role == UserRole.BARBER:
        barber = barber_service.get_barber_by_user_id(db, current_user.id)
        if not barber or barber.id != schedule_in.barber_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Barbers can only manage schedules assigned to them.",
            )
    return schedule_service.create_schedule(db, schedule_in)


@router.put(
    "/{schedule_id}",
    response_model=ScheduleOut,
    summary="Update Schedule",
    description="Modifies working hours, breaks, or day-off status for a schedule.",
)
def update_schedule(
    schedule_id: int,
    schedule_in: ScheduleUpdate,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    schedule = schedule_service.get_schedule_by_id(db, schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found.",
        )
    if current_user.role == UserRole.BARBER:
        barber = barber_service.get_barber_by_user_id(db, current_user.id)
        if not barber or barber.id != schedule.barber_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Barbers can only modify schedules assigned to them.",
            )
    return schedule_service.update_schedule(db, schedule, schedule_in)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Schedule",
    description="Deletes a schedule record.",
)
def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    schedule = schedule_service.get_schedule_by_id(db, schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found.",
        )
    if current_user.role == UserRole.BARBER:
        barber = barber_service.get_barber_by_user_id(db, current_user.id)
        if not barber or barber.id != schedule.barber_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Barbers can only delete schedules assigned to them.",
            )
    schedule_service.delete_schedule(db, schedule)
    return None


@router.post(
    "/blocked-periods",
    response_model=BlockedPeriodOut,
    status_code=status.HTTP_201_CREATED,
    summary="Block a Time Period",
    description="Blocks off a specific time interval on a date for a barber.",
)
def create_blocked_period(
    block_in: BlockedPeriodCreate,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.BARBER:
        barber = barber_service.get_barber_by_user_id(db, current_user.id)
        if not barber or barber.id != block_in.barber_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Barbers can only block periods for their own chair.",
            )
    return schedule_service.create_blocked_period(db, block_in)


@router.get(
    "/blocked-periods",
    response_model=List[BlockedPeriodOut],
    summary="List Blocked Periods",
    description="Lists active blocked time periods for a barber or date.",
)
def list_blocked_periods(
    barber_id: Optional[int] = None,
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return schedule_service.list_blocked_periods(db, barber_id=barber_id, target_date=target_date)


@router.delete(
    "/blocked-periods/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Blocked Period",
    description="Removes a blocked period.",
)
def delete_blocked_period(
    block_id: int,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    schedule_service.delete_blocked_period(db, block_id)
    return None
