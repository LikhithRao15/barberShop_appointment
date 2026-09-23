import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.models.visit import Visit
from app.models.notification import NotificationType
from app.services.appointment_service import get_appointment_by_id
from app.services.barber_service import get_barber_by_user_id
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


def get_visit_by_id(db: Session, visit_id: int) -> Optional[Visit]:
    return db.query(Visit).filter(Visit.id == visit_id).first()


def get_visit_by_appointment_id(db: Session, appointment_id: int) -> Optional[Visit]:
    return db.query(Visit).filter(Visit.appointment_id == appointment_id).first()


def list_visits(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Visit]:
    return db.query(Visit).order_by(Visit.created_at.desc()).offset(skip).limit(limit).all()


def _get_or_create_visit(db: Session, appointment_id: int) -> Visit:
    visit = get_visit_by_appointment_id(db, appointment_id)
    if not visit:
        visit = Visit(appointment_id=appointment_id)
        db.add(visit)
        db.flush()
    return visit


def _validate_barber_or_admin_permission(appointment: Appointment, current_user: User, db: Session):
    if current_user.role == UserRole.BARBER:
        barber = get_barber_by_user_id(db, current_user.id)
        if not barber or appointment.barber_id != barber.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage this appointment's visit tracking.",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only assigned barbers or administrators can update visit status.",
        )


def record_student_arrival(
    db: Session,
    appointment_id: int,
    current_user: User,
    notes: Optional[str] = None,
) -> Visit:
    """
    Transition: BOOKED -> ARRIVED
    Records physical arrival timestamp.
    """
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    _validate_barber_or_admin_permission(appointment, current_user, db)

    if appointment.status != AppointmentStatus.BOOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark arrival for appointment in '{appointment.status.value}' status. Must be 'BOOKED'.",
        )

    now = datetime.now(timezone.utc)
    visit = _get_or_create_visit(db, appointment_id)
    visit.arrival_time = now
    if notes:
        visit.visit_notes = notes.strip()

    appointment.status = AppointmentStatus.ARRIVED
    db.commit()
    db.refresh(visit)
    db.refresh(appointment)
    return visit


def start_service(
    db: Session,
    appointment_id: int,
    current_user: User,
    notes: Optional[str] = None,
) -> Visit:
    """
    Transition: ARRIVED -> IN_SERVICE
    Records service start time in chair.
    """
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    _validate_barber_or_admin_permission(appointment, current_user, db)

    if appointment.status != AppointmentStatus.ARRIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start service for appointment in '{appointment.status.value}' status. Must be 'ARRIVED'.",
        )

    now = datetime.now(timezone.utc)
    visit = _get_or_create_visit(db, appointment_id)
    visit.service_start_time = now
    if notes:
        visit.visit_notes = f"{visit.visit_notes}\n{notes.strip()}" if visit.visit_notes else notes.strip()

    appointment.status = AppointmentStatus.IN_SERVICE
    db.commit()
    db.refresh(visit)
    db.refresh(appointment)
    return visit


def complete_service(
    db: Session,
    appointment_id: int,
    current_user: User,
    notes: Optional[str] = None,
) -> Visit:
    """
    Transition: IN_SERVICE -> COMPLETED
    Records completion time and triggers completion notification.
    """
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    _validate_barber_or_admin_permission(appointment, current_user, db)

    if appointment.status != AppointmentStatus.IN_SERVICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete service for appointment in '{appointment.status.value}' status. Must be 'IN_SERVICE'.",
        )

    now = datetime.now(timezone.utc)
    visit = _get_or_create_visit(db, appointment_id)
    visit.completion_time = now

    if visit.service_start_time:
        start_time = visit.service_start_time
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        elapsed = (now - start_time).total_seconds() / 60.0
        visit.actual_duration_minutes = max(1, int(round(elapsed)))

    if notes:
        visit.visit_notes = f"{visit.visit_notes}\n{notes.strip()}" if visit.visit_notes else notes.strip()

    appointment.status = AppointmentStatus.COMPLETED
    db.commit()
    db.refresh(visit)
    db.refresh(appointment)

    # Trigger completion notification to student
    try:
        if appointment.student and appointment.student.user:
            create_notification(
                db=db,
                user_id=appointment.student.user.id,
                appointment_id=appointment.id,
                notification_type=NotificationType.SERVICE_COMPLETED,
                title="Service Completed",
                message=f"Your visit on {appointment.appointment_date} with {appointment.barber.user.full_name if appointment.barber and appointment.barber.user else 'Barber'} is complete. Thank you!",
            )
    except Exception as e:
        logger.error(f"Error creating service completed notification: {e}")

    return visit
