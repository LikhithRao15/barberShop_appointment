import logging
from datetime import date, time
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.barber import Barber
from app.models.schedule import Schedule, ScheduleBreak, BlockedPeriod
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    BlockedPeriodCreate,
    DailyScheduleDetail,
    BreakBase,
    BlockedPeriodBase,
)
from app.services.barber_service import get_barber_by_id

logger = logging.getLogger(__name__)


def get_schedule_by_id(db: Session, schedule_id: int) -> Optional[Schedule]:
    return db.query(Schedule).filter(Schedule.id == schedule_id).first()


def get_barber_schedules(
    db: Session,
    barber_id: int,
    active_only: bool = True,
) -> List[Schedule]:
    query = db.query(Schedule).filter(Schedule.barber_id == barber_id)
    if active_only:
        query = query.filter(Schedule.is_active == True)
    return query.order_by(Schedule.day_of_week, Schedule.schedule_date).all()


def create_schedule(db: Session, schedule_in: ScheduleCreate) -> Schedule:
    barber = get_barber_by_id(db, schedule_in.barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {schedule_in.barber_id} not found.",
        )

    # Validate that any breaks fall entirely within working hours
    if not schedule_in.is_day_off and schedule_in.breaks:
        for brk in schedule_in.breaks:
            if brk.start_time < schedule_in.start_time or brk.end_time > schedule_in.end_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Break '{brk.name}' ({brk.start_time}-{brk.end_time}) must fall entirely "
                        f"within working hours ({schedule_in.start_time}-{schedule_in.end_time})."
                    ),
                )

    # Check for duplicate schedule on the same specific date or day_of_week
    existing_query = db.query(Schedule).filter(Schedule.barber_id == schedule_in.barber_id)
    if schedule_in.schedule_date:
        existing = existing_query.filter(Schedule.schedule_date == schedule_in.schedule_date).first()
        if existing:
            # Overwrite/update existing date override
            db.delete(existing)
            db.flush()
    elif schedule_in.day_of_week is not None:
        existing = existing_query.filter(
            Schedule.day_of_week == schedule_in.day_of_week,
            Schedule.schedule_date == None,
        ).first()
        if existing:
            # Overwrite/update recurring day
            db.delete(existing)
            db.flush()

    schedule = Schedule(
        barber_id=schedule_in.barber_id,
        schedule_date=schedule_in.schedule_date,
        day_of_week=schedule_in.day_of_week,
        start_time=schedule_in.start_time,
        end_time=schedule_in.end_time,
        is_day_off=schedule_in.is_day_off,
        is_active=schedule_in.is_active,
    )
    db.add(schedule)
    db.flush()

    if schedule_in.breaks and not schedule_in.is_day_off:
        for brk in schedule_in.breaks:
            db_break = ScheduleBreak(
                schedule_id=schedule.id,
                name=brk.name.strip(),
                start_time=brk.start_time,
                end_time=brk.end_time,
            )
            db.add(db_break)

    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(db: Session, schedule: Schedule, schedule_in: ScheduleUpdate) -> Schedule:
    if schedule_in.start_time is not None:
        schedule.start_time = schedule_in.start_time
    if schedule_in.end_time is not None:
        schedule.end_time = schedule_in.end_time
    if schedule_in.is_day_off is not None:
        schedule.is_day_off = schedule_in.is_day_off
    if schedule_in.is_active is not None:
        schedule.is_active = schedule_in.is_active

    if schedule_in.breaks is not None:
        # Validate breaks against effective shift times
        for brk in schedule_in.breaks:
            if brk.start_time < schedule.start_time or brk.end_time > schedule.end_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Break '{brk.name}' ({brk.start_time}-{brk.end_time}) falls outside working hours.",
                )
        # Replace breaks
        db.query(ScheduleBreak).filter(ScheduleBreak.schedule_id == schedule.id).delete()
        for brk in schedule_in.breaks:
            db.add(
                ScheduleBreak(
                    schedule_id=schedule.id,
                    name=brk.name.strip(),
                    start_time=brk.start_time,
                    end_time=brk.end_time,
                )
            )

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    db.delete(schedule)
    db.commit()


# Blocked Periods
def create_blocked_period(db: Session, block_in: BlockedPeriodCreate) -> BlockedPeriod:
    barber = get_barber_by_id(db, block_in.barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {block_in.barber_id} not found.",
        )

    blocked = BlockedPeriod(
        barber_id=block_in.barber_id,
        blocked_date=block_in.blocked_date,
        start_time=block_in.start_time,
        end_time=block_in.end_time,
        reason=block_in.reason.strip() if block_in.reason else "Unavailable",
    )
    db.add(blocked)
    db.commit()
    db.refresh(blocked)
    return blocked


def list_blocked_periods(
    db: Session,
    barber_id: Optional[int] = None,
    target_date: Optional[date] = None,
) -> List[BlockedPeriod]:
    query = db.query(BlockedPeriod)
    if barber_id:
        query = query.filter(BlockedPeriod.barber_id == barber_id)
    if target_date:
        query = query.filter(BlockedPeriod.blocked_date == target_date)
    return query.order_by(BlockedPeriod.blocked_date, BlockedPeriod.start_time).all()


def delete_blocked_period(db: Session, block_id: int) -> None:
    blocked = db.query(BlockedPeriod).filter(BlockedPeriod.id == block_id).first()
    if not blocked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blocked period with ID {block_id} not found.",
        )
    db.delete(blocked)
    db.commit()


def get_effective_daily_schedule(
    db: Session, barber_id: int, target_date: date
) -> DailyScheduleDetail:
    """
    Calculates the exact effective working hours, breaks, and blocked periods
    for a given barber on a specific calendar date.
    Priority:
      1. Specific calendar date override (Schedule with schedule_date == target_date)
      2. Recurring day of week schedule (Schedule with day_of_week == target_date.weekday())
      3. If none found or is_day_off=True -> is_working=False.
    """
    day_of_week = target_date.weekday()

    # 1. Check date override
    schedule = (
        db.query(Schedule)
        .filter(
            Schedule.barber_id == barber_id,
            Schedule.schedule_date == target_date,
            Schedule.is_active == True,
        )
        .first()
    )

    # 2. Check recurring day of week
    if not schedule:
        schedule = (
            db.query(Schedule)
            .filter(
                Schedule.barber_id == barber_id,
                Schedule.day_of_week == day_of_week,
                Schedule.schedule_date == None,
                Schedule.is_active == True,
            )
            .first()
        )

    if not schedule or schedule.is_day_off:
        return DailyScheduleDetail(
            barber_id=barber_id,
            target_date=target_date,
            day_of_week=day_of_week,
            is_working=False,
            breaks=[],
            blocked_periods=[],
        )

    # Fetch configured breaks
    breaks_list = [
        BreakBase(
            name=brk.name,
            start_time=brk.start_time,
            end_time=brk.end_time,
        )
        for brk in schedule.breaks
    ]

    # Fetch ad-hoc blocked periods for this date
    blocked_records = (
        db.query(BlockedPeriod)
        .filter(
            BlockedPeriod.barber_id == barber_id,
            BlockedPeriod.blocked_date == target_date,
        )
        .all()
    )
    blocked_list = [
        BlockedPeriodBase(
            barber_id=b.barber_id,
            blocked_date=b.blocked_date,
            start_time=b.start_time,
            end_time=b.end_time,
            reason=b.reason,
        )
        for b in blocked_records
    ]

    return DailyScheduleDetail(
        barber_id=barber_id,
        target_date=target_date,
        day_of_week=day_of_week,
        is_working=True,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        breaks=breaks_list,
        blocked_periods=blocked_list,
    )
