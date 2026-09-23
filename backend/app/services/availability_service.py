import logging
from datetime import date, time, datetime, timedelta
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.barber import Barber
from app.models.service import Service
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.appointment import TimeSlot, AvailabilityResponse
from app.services.barber_service import get_barber_by_id
from app.services.service_catalog_service import get_service_by_id
from app.services.schedule_service import get_effective_daily_schedule

logger = logging.getLogger(__name__)


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    return time(hour=m // 60, minute=m % 60)


def _intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Returns True if [start_a, end_a) and [start_b, end_b) overlap in time."""
    return max(start_a, start_b) < min(end_a, end_b)


def calculate_barber_availability(
    db: Session,
    barber_id: int,
    service_id: int,
    target_date: date,
    slot_step_minutes: int = 15,
) -> AvailabilityResponse:
    """
    Deterministically computes continuous available appointment slots for a given
    barber, service duration, and target date.
    """
    barber = get_barber_by_id(db, barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {barber_id} not found.",
        )
    if not barber.is_available_for_booking or not barber.user or not barber.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Barber '{barber.user.full_name if barber.user else barber_id}' is currently not accepting bookings.",
        )

    service = get_service_by_id(db, service_id)
    if not service or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active service with ID {service_id} not found.",
        )

    duration = service.duration_minutes
    daily_schedule = get_effective_daily_schedule(db, barber_id=barber_id, target_date=target_date)

    if not daily_schedule.is_working or not daily_schedule.start_time or not daily_schedule.end_time:
        return AvailabilityResponse(
            barber_id=barber.id,
            barber_name=barber.user.full_name if barber.user else f"Barber {barber.id}",
            service_id=service.id,
            service_name=service.name,
            duration_minutes=duration,
            target_date=target_date,
            is_working_day=False,
            available_slots=[],
        )

    shift_start_m = _time_to_minutes(daily_schedule.start_time)
    shift_end_m = _time_to_minutes(daily_schedule.end_time)

    # Convert breaks to minute intervals
    break_intervals: List[Tuple[int, int]] = [
        (_time_to_minutes(b.start_time), _time_to_minutes(b.end_time))
        for b in daily_schedule.breaks
    ]

    # Convert blocked periods to minute intervals
    blocked_intervals: List[Tuple[int, int]] = [
        (_time_to_minutes(bp.start_time), _time_to_minutes(bp.end_time))
        for bp in daily_schedule.blocked_periods
    ]

    # Query active appointments for this barber on target_date
    active_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.barber_id == barber_id,
            Appointment.appointment_date == target_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
            ]),
        )
        .all()
    )

    booked_intervals: List[Tuple[int, int]] = [
        (_time_to_minutes(a.start_time), _time_to_minutes(a.end_time))
        for a in active_appointments
    ]

    available_slots: List[TimeSlot] = []

    # Slide window by slot_step_minutes from shift_start_m up to (shift_end_m - duration)
    current_start_m = shift_start_m
    while current_start_m + duration <= shift_end_m:
        current_end_m = current_start_m + duration

        # Check collision with breaks
        collides_break = any(
            _intervals_overlap(current_start_m, current_end_m, b_start, b_end)
            for b_start, b_end in break_intervals
        )

        # Check collision with blocked periods
        collides_blocked = any(
            _intervals_overlap(current_start_m, current_end_m, bl_start, bl_end)
            for bl_start, bl_end in blocked_intervals
        )

        # Check collision with existing active bookings
        collides_booking = any(
            _intervals_overlap(current_start_m, current_end_m, bk_start, bk_end)
            for bk_start, bk_end in booked_intervals
        )

        if not collides_break and not collides_blocked and not collides_booking:
            available_slots.append(
                TimeSlot(
                    start_time=_minutes_to_time(current_start_m),
                    end_time=_minutes_to_time(current_end_m),
                    is_available=True,
                    duration_minutes=duration,
                )
            )

        current_start_m += slot_step_minutes

    return AvailabilityResponse(
        barber_id=barber.id,
        barber_name=barber.user.full_name if barber.user else f"Barber {barber.id}",
        service_id=service.id,
        service_name=service.name,
        duration_minutes=duration,
        target_date=target_date,
        is_working_day=True,
        working_start_time=daily_schedule.start_time,
        working_end_time=daily_schedule.end_time,
        available_slots=available_slots,
    )
