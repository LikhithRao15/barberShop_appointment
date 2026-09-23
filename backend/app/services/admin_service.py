import logging
from datetime import date
from typing import Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.barber import Barber
from app.models.service import Service
from app.models.appointment import Appointment, AppointmentStatus
from app.models.visit import Visit
from app.schemas.admin import (
    DashboardStatsOut,
    SystemRulesOut,
    StudentBatchImportRequest,
    StudentBatchImportResult,
)
from app.schemas.student import StudentOut
from app.services.user_service import get_user_by_id
from app.services.barber_service import get_barber_by_id
from app.services.student_service import create_student

logger = logging.getLogger(__name__)


def get_dashboard_stats(db: Session) -> DashboardStatsOut:
    """Aggregates real-time system monitoring and performance metrics."""
    total_users = db.query(User).count()
    total_students = db.query(Student).count()
    total_barbers = db.query(Barber).count()
    total_services = db.query(Service).count()
    total_appointments = db.query(Appointment).count()

    # Breakdown by appointment status
    status_counts = (
        db.query(Appointment.status, func.count(Appointment.id))
        .group_by(Appointment.status)
        .all()
    )
    status_map: Dict[str, int] = {s.value: 0 for s in AppointmentStatus}
    for st, count in status_counts:
        status_map[st.value] = count

    today = date.today()
    today_appts = db.query(Appointment).filter(Appointment.appointment_date == today).all()
    today_count = len(today_appts)
    today_completed = sum(1 for a in today_appts if a.status == AppointmentStatus.COMPLETED)
    today_no_shows = sum(1 for a in today_appts if a.status == AppointmentStatus.NO_SHOW)
    today_cancellations = sum(1 for a in today_appts if a.status == AppointmentStatus.CANCELLED)

    return DashboardStatsOut(
        total_users=total_users,
        total_students=total_students,
        total_barbers=total_barbers,
        total_services=total_services,
        total_appointments=total_appointments,
        appointments_by_status=status_map,
        today_appointments_count=today_count,
        today_completed_visits=today_completed,
        today_no_shows=today_no_shows,
        today_cancellations=today_cancellations,
    )


def get_system_rules() -> SystemRulesOut:
    """Returns active operational and business rule parameters."""
    return SystemRulesOut(
        project_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        cancellation_cutoff_minutes=settings.CANCELLATION_MINUTES_BEFORE,
        no_show_grace_period_minutes=settings.NO_SHOW_GRACE_PERIOD_MINUTES,
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        jwt_algorithm=settings.JWT_ALGORITHM,
        version=settings.VERSION,
    )


def set_user_active_status(db: Session, user_id: int, is_active: bool) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def set_barber_approval(db: Session, barber_id: int, is_available_for_booking: bool) -> Barber:
    barber = get_barber_by_id(db, barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {barber_id} not found.",
        )
    barber.is_available_for_booking = is_available_for_booking
    db.commit()
    db.refresh(barber)
    return barber


def batch_import_students(db: Session, import_req: StudentBatchImportRequest) -> StudentBatchImportResult:
    """Batches the onboarding of multiple student accounts."""
    created = []
    errors = []

    for idx, stu_in in enumerate(import_req.students):
        try:
            student = create_student(db, stu_in)
            created.append(student)
        except Exception as e:
            msg = getattr(e, "detail", str(e))
            errors.append(f"Student #{idx + 1} ({stu_in.student_id_number} / {stu_in.username}): {msg}")

    return StudentBatchImportResult(
        total_requested=len(import_req.students),
        successful_count=len(created),
        failed_count=len(errors),
        created_students=created,
        errors=errors,
    )
