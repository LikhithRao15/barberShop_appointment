import logging
from datetime import date, time, datetime, timedelta, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.config import settings
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.barber import Barber
from app.models.service import Service
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.schemas.appointment import (
    AppointmentCreate,
    AvailableNowSlotOut,
    ClaimAvailableNowRequest,
)
from app.services.student_service import get_student_by_id, get_student_by_user_id
from app.services.barber_service import get_barber_by_id, get_barber_by_user_id
from app.services.service_catalog_service import get_service_by_id
from app.services.schedule_service import get_effective_daily_schedule
from app.services.availability_service import _time_to_minutes, _minutes_to_time, _intervals_overlap
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


def get_appointment_by_id(db: Session, appointment_id: int) -> Optional[Appointment]:
    return db.query(Appointment).filter(Appointment.id == appointment_id).first()


def list_appointments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    student_id: Optional[int] = None,
    barber_id: Optional[int] = None,
    appointment_date: Optional[date] = None,
    status_filter: Optional[AppointmentStatus] = None,
) -> List[Appointment]:
    query = db.query(Appointment)
    if student_id:
        query = query.filter(Appointment.student_id == student_id)
    if barber_id:
        query = query.filter(Appointment.barber_id == barber_id)
    if appointment_date:
        query = query.filter(Appointment.appointment_date == appointment_date)
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    return query.order_by(Appointment.appointment_date.desc(), Appointment.start_time.asc()).offset(skip).limit(limit).all()


def list_user_appointments(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[AppointmentStatus] = None,
) -> List[Appointment]:
    if current_user.role == UserRole.STUDENT:
        student = get_student_by_user_id(db, current_user.id)
        if not student:
            return []
        return list_appointments(db, skip=skip, limit=limit, student_id=student.id, status_filter=status_filter)
    elif current_user.role == UserRole.BARBER:
        barber = get_barber_by_user_id(db, current_user.id)
        if not barber:
            return []
        return list_appointments(db, skip=skip, limit=limit, barber_id=barber.id, status_filter=status_filter)
    elif current_user.role == UserRole.ADMIN:
        return list_appointments(db, skip=skip, limit=limit, status_filter=status_filter)
    return []


def book_appointment(
    db: Session,
    appointment_in: AppointmentCreate,
    student_id: int,
) -> Appointment:
    """
    Transactional booking operation enforcing double-booking prevention.
    """
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )
    if not student.user or not student.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student account is inactive and cannot book appointments.",
        )

    barber = get_barber_by_id(db, appointment_in.barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {appointment_in.barber_id} not found.",
        )
    if not barber.is_available_for_booking or not barber.user or not barber.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barber is currently unavailable for bookings.",
        )

    service = get_service_by_id(db, appointment_in.service_id)
    if not service or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active service with ID {appointment_in.service_id} not found.",
        )

    duration = service.duration_minutes
    start_m = _time_to_minutes(appointment_in.start_time)
    end_m = start_m + duration
    calculated_end_time = _minutes_to_time(end_m)

    schedule = get_effective_daily_schedule(
        db, barber_id=appointment_in.barber_id, target_date=appointment_in.appointment_date
    )
    if not schedule.is_working or not schedule.start_time or not schedule.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barber is not working on the selected date.",
        )

    shift_start_m = _time_to_minutes(schedule.start_time)
    shift_end_m = _time_to_minutes(schedule.end_time)

    if start_m < shift_start_m or end_m > shift_end_m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Requested slot {appointment_in.start_time}-{calculated_end_time} falls outside "
                f"barber working hours ({schedule.start_time}-{schedule.end_time})."
            ),
        )

    for brk in schedule.breaks:
        b_start = _time_to_minutes(brk.start_time)
        b_end = _time_to_minutes(brk.end_time)
        if _intervals_overlap(start_m, end_m, b_start, b_end):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested slot overlaps with barber's configured break '{brk.name}' ({brk.start_time}-{brk.end_time}).",
            )

    for bp in schedule.blocked_periods:
        bl_start = _time_to_minutes(bp.start_time)
        bl_end = _time_to_minutes(bp.end_time)
        if _intervals_overlap(start_m, end_m, bl_start, bl_end):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested slot falls in a blocked period ({bp.start_time}-{bp.end_time}: {bp.reason}).",
            )

    # Pessimistic lock on conflicting active appointments
    overlapping_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.barber_id == appointment_in.barber_id,
            Appointment.appointment_date == appointment_in.appointment_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
            ]),
            Appointment.start_time < calculated_end_time,
            Appointment.end_time > appointment_in.start_time,
        )
        .with_for_update()
        .first()
    )

    if overlapping_appointment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected appointment slot is no longer available. Please choose another time.",
        )

    # Student overlapping active booking check
    student_overlapping = (
        db.query(Appointment)
        .filter(
            Appointment.student_id == student_id,
            Appointment.appointment_date == appointment_in.appointment_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
            ]),
            Appointment.start_time < calculated_end_time,
            Appointment.end_time > appointment_in.start_time,
        )
        .first()
    )
    if student_overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active booking overlapping with this time slot.",
        )

    new_appointment = Appointment(
        student_id=student_id,
        barber_id=appointment_in.barber_id,
        service_id=appointment_in.service_id,
        appointment_date=appointment_in.appointment_date,
        start_time=appointment_in.start_time,
        end_time=calculated_end_time,
        status=AppointmentStatus.BOOKED,
        notes=appointment_in.notes.strip() if appointment_in.notes else None,
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    # Trigger booking confirmation notifications
    try:
        # Notify student
        if student.user:
            create_notification(
                db=db,
                user_id=student.user.id,
                appointment_id=new_appointment.id,
                notification_type=NotificationType.BOOKING_CONFIRMATION,
                title="Appointment Confirmed",
                message=(
                    f"Your appointment with {barber.user.full_name if barber.user else 'Barber'} "
                    f"for {service.name} is confirmed for {new_appointment.appointment_date} "
                    f"at {new_appointment.start_time}."
                ),
            )
        # Notify barber
        if barber.user:
            create_notification(
                db=db,
                user_id=barber.user.id,
                appointment_id=new_appointment.id,
                notification_type=NotificationType.BOOKING_CONFIRMATION,
                title="New Booking Received",
                message=(
                    f"New appointment booked by {student.user.full_name if student.user else 'Student'} "
                    f"for {service.name} on {new_appointment.appointment_date} at {new_appointment.start_time}."
                ),
            )
    except Exception as e:
        logger.error(f"Error creating booking notifications: {e}")

    return new_appointment


def cancel_appointment(
    db: Session,
    appointment_id: int,
    current_user: User,
    reason: Optional[str] = None,
    admin_override: bool = False,
) -> Appointment:
    """
    Cancels an appointment adhering to configurable cancellation policies.
    Fixed Appointment Principle: Only releases this slot. All other appointments remain unchanged!
    """
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.IN_SERVICE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel an appointment that is already {appointment.status.value}.",
        )

    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is already cancelled.",
        )

    # Permission and Cancellation Window Validation
    if current_user.role == UserRole.STUDENT:
        student = get_student_by_user_id(db, current_user.id)
        if not student or appointment.student_id != student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel another student's appointment.",
            )

        appointment_dt = datetime.combine(appointment.appointment_date, appointment.start_time)
        now_dt = datetime.now()
        cutoff_dt = appointment_dt - timedelta(minutes=settings.CANCELLATION_MINUTES_BEFORE)

        if now_dt > cutoff_dt and not admin_override:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Late cancellation rejected. Appointments must be cancelled at least "
                    f"{settings.CANCELLATION_MINUTES_BEFORE} minutes in advance."
                ),
            )
    elif current_user.role == UserRole.BARBER:
        barber = get_barber_by_user_id(db, current_user.id)
        if not barber or appointment.barber_id != barber.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel another barber's appointment.",
            )

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = reason.strip() if reason else "Cancelled by user"
    appointment.cancelled_at = datetime.now(timezone.utc)
    appointment.is_available_now_slot = True  # Slot is released

    db.commit()
    db.refresh(appointment)

    # Trigger cancellation notifications
    try:
        if appointment.student and appointment.student.user:
            create_notification(
                db=db,
                user_id=appointment.student.user.id,
                appointment_id=appointment.id,
                notification_type=NotificationType.CANCELLATION,
                title="Appointment Cancelled",
                message=f"Your appointment on {appointment.appointment_date} at {appointment.start_time} has been cancelled.",
            )
        if appointment.barber and appointment.barber.user:
            create_notification(
                db=db,
                user_id=appointment.barber.user.id,
                appointment_id=appointment.id,
                notification_type=NotificationType.CANCELLATION,
                title="Appointment Cancelled",
                message=f"Appointment on {appointment.appointment_date} at {appointment.start_time} was cancelled. Slot released.",
            )
    except Exception as e:
        logger.error(f"Error creating cancellation notifications: {e}")

    return appointment


def mark_appointment_no_show(
    db: Session,
    appointment_id: int,
    current_user: User,
    notes: Optional[str] = None,
    ignore_grace_period: bool = False,
) -> Appointment:
    """
    Marks an appointment as NO_SHOW after the grace period has elapsed.
    """
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    if appointment.status != AppointmentStatus.BOOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark appointment as NO_SHOW from status {appointment.status.value}.",
        )

    if current_user.role == UserRole.BARBER:
        barber = get_barber_by_user_id(db, current_user.id)
        if not barber or appointment.barber_id != barber.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only mark no-show for appointments assigned to you.",
            )

    appointment_start_dt = datetime.combine(appointment.appointment_date, appointment.start_time)
    now_dt = datetime.now()
    grace_cutoff_dt = appointment_start_dt + timedelta(minutes=settings.NO_SHOW_GRACE_PERIOD_MINUTES)

    if now_dt < grace_cutoff_dt and not ignore_grace_period and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Grace period of {settings.NO_SHOW_GRACE_PERIOD_MINUTES} minutes has not elapsed yet. "
                f"Eligible after {grace_cutoff_dt.strftime('%H:%M:%S')}."
            ),
        )

    appointment.status = AppointmentStatus.NO_SHOW
    appointment.no_show_at = datetime.now(timezone.utc)
    appointment.cancellation_reason = f"No Show: {notes.strip()}" if notes else "Student did not arrive within grace period"
    appointment.is_available_now_slot = True

    db.commit()
    db.refresh(appointment)

    # Trigger no-show notification
    try:
        if appointment.student and appointment.student.user:
            create_notification(
                db=db,
                user_id=appointment.student.user.id,
                appointment_id=appointment.id,
                notification_type=NotificationType.NO_SHOW,
                title="Appointment Marked as No-Show",
                message=f"Your appointment on {appointment.appointment_date} at {appointment.start_time} was marked as No-Show.",
            )
    except Exception as e:
        logger.error(f"Error creating no-show notification: {e}")

    return appointment


def list_available_now_slots(
    db: Session,
    target_date: Optional[date] = None,
    barber_id: Optional[int] = None,
) -> List[AvailableNowSlotOut]:
    if target_date is None:
        target_date = date.today()

    query = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date == target_date,
            Appointment.is_available_now_slot == True,
            Appointment.status.in_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
        )
    )
    if barber_id:
        query = query.filter(Appointment.barber_id == barber_id)

    released_appointments = query.order_by(Appointment.start_time.asc()).all()
    results: List[AvailableNowSlotOut] = []

    for appt in released_appointments:
        conflicting = (
            db.query(Appointment)
            .filter(
                Appointment.barber_id == appt.barber_id,
                Appointment.appointment_date == appt.appointment_date,
                Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                Appointment.start_time < appt.end_time,
                Appointment.end_time > appt.start_time,
            )
            .first()
        )
        if not conflicting:
            results.append(
                AvailableNowSlotOut(
                    released_appointment_id=appt.id,
                    barber_id=appt.barber_id,
                    barber_name=appt.barber.user.full_name if appt.barber and appt.barber.user else f"Barber {appt.barber_id}",
                    shop_name=appt.barber.shop_name if appt.barber else None,
                    chair_number=appt.barber.chair_number if appt.barber else None,
                    service_id=appt.service_id,
                    service_name=appt.service.name if appt.service else "Service",
                    duration_minutes=appt.service.duration_minutes if appt.service else 30,
                    appointment_date=appt.appointment_date,
                    start_time=appt.start_time,
                    end_time=appt.end_time,
                    release_reason=appt.cancellation_reason or "Slot Released",
                )
            )

    return results


def claim_available_now_slot(
    db: Session,
    released_appointment_id: int,
    student_id: int,
    service_id: int,
    notes: Optional[str] = None,
) -> Appointment:
    released_appt = get_appointment_by_id(db, released_appointment_id)
    if not released_appt or not released_appt.is_available_now_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Available Now slot is no longer available.",
        )

    appointment_in = AppointmentCreate(
        barber_id=released_appt.barber_id,
        service_id=service_id,
        appointment_date=released_appt.appointment_date,
        start_time=released_appt.start_time,
        notes=notes,
    )

    new_booking = book_appointment(db, appointment_in, student_id=student_id)
    released_appt.is_available_now_slot = False
    db.commit()
    return new_booking
