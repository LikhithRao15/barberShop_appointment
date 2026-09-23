from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.appointment import (
    AppointmentOut,
    AppointmentCreate,
    AppointmentCancelRequest,
    AppointmentNoShowRequest,
    AvailableNowSlotOut,
    ClaimAvailableNowRequest,
    AvailabilityResponse,
)
from app.schemas.visit import VisitActionRequest
from app.core.deps import get_current_active_user, require_admin, require_student, require_barber
from app.services import (
    appointment_service,
    availability_service,
    student_service,
    barber_service,
    visit_service,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
    summary="Check Barber Available Slots",
    description="Calculates continuous available booking slots for a barber, service, and date.",
)
def get_availability(
    barber_id: int = Query(..., description="ID of the barber"),
    service_id: int = Query(..., description="ID of the service to be booked"),
    target_date: date = Query(..., description="Date for appointment (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return availability_service.calculate_barber_availability(
        db,
        barber_id=barber_id,
        service_id=service_id,
        target_date=target_date,
    )


@router.get(
    "/available-now",
    response_model=List[AvailableNowSlotOut],
    summary="List 'Available Now' Released Slots",
    description="Lists slots released due to cancellations or no-shows that can be claimed immediately.",
)
def get_available_now_slots(
    target_date: Optional[date] = Query(None, description="Date to check for released slots (defaults to today)"),
    barber_id: Optional[int] = Query(None, description="Filter by barber ID"),
    db: Session = Depends(get_db),
):
    return appointment_service.list_available_now_slots(
        db=db,
        target_date=target_date,
        barber_id=barber_id,
    )


@router.post(
    "/available-now/{released_appointment_id}/claim",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Claim 'Available Now' Slot",
    description="Claims an earlier released slot while keeping all other appointments strictly fixed.",
)
def claim_available_now(
    released_appointment_id: int,
    claim_in: ClaimAvailableNowRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.STUDENT and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and administrators can claim released slots.",
        )

    student = student_service.get_student_by_user_id(db, current_user.id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for this account.",
        )

    return appointment_service.claim_available_now_slot(
        db=db,
        released_appointment_id=released_appointment_id,
        student_id=student.id,
        service_id=claim_in.service_id,
        notes=claim_in.notes,
    )


@router.post(
    "",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book an Appointment",
    description="Atomically books a confirmed appointment slot. Enforces double-booking prevention.",
)
def create_appointment(
    appointment_in: AppointmentCreate,
    student_id: Optional[int] = Query(None, description="Optional target student ID for admin booking"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    target_student_id: int

    if current_user.role == UserRole.STUDENT:
        student = student_service.get_student_by_user_id(db, current_user.id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for the authenticated user.",
            )
        target_student_id = student.id
    elif current_user.role == UserRole.ADMIN:
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin booking must specify a target student_id.",
            )
        target_student_id = student_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and admins can book appointments.",
        )

    return appointment_service.book_appointment(
        db=db,
        appointment_in=appointment_in,
        student_id=target_student_id,
    )


# Barber Appointment Action Endpoints
@router.post(
    "/{appointment_id}/arrive",
    response_model=AppointmentOut,
    summary="Record Physical Arrival (Barber Action)",
    description="Records student arrival at the shop: transitions BOOKED -> ARRIVED.",
)
def record_arrival_endpoint(
    appointment_id: int,
    action_in: Optional[VisitActionRequest] = None,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    notes = action_in.notes if action_in else None
    visit_service.record_student_arrival(db, appointment_id, current_user, notes=notes)
    return appointment_service.get_appointment_by_id(db, appointment_id)


@router.post(
    "/{appointment_id}/start",
    response_model=AppointmentOut,
    summary="Start Service in Chair (Barber Action)",
    description="Records start of haircut: transitions ARRIVED -> IN_SERVICE.",
)
def start_service_endpoint(
    appointment_id: int,
    action_in: Optional[VisitActionRequest] = None,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    notes = action_in.notes if action_in else None
    visit_service.start_service(db, appointment_id, current_user, notes=notes)
    return appointment_service.get_appointment_by_id(db, appointment_id)


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentOut,
    summary="Complete Service (Barber Action)",
    description="Records haircut completion and elapsed duration: transitions IN_SERVICE -> COMPLETED.",
)
def complete_service_endpoint(
    appointment_id: int,
    action_in: Optional[VisitActionRequest] = None,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    notes = action_in.notes if action_in else None
    visit_service.complete_service(db, appointment_id, current_user, notes=notes)
    return appointment_service.get_appointment_by_id(db, appointment_id)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentOut,
    summary="Cancel Appointment",
    description="Cancels an appointment within the allowed policy window, releasing only this appointment's slot.",
)
def cancel_appointment_endpoint(
    appointment_id: int,
    cancel_in: Optional[AppointmentCancelRequest] = None,
    admin_override: bool = Query(False, description="Admin override late cancellation restriction"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    reason = cancel_in.reason if cancel_in else None
    return appointment_service.cancel_appointment(
        db=db,
        appointment_id=appointment_id,
        current_user=current_user,
        reason=reason,
        admin_override=admin_override and current_user.role == UserRole.ADMIN,
    )


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentOut,
    summary="Mark Appointment as No-Show (Barber / Admin Action)",
    description="Marks a student appointment as NO_SHOW after the grace period has passed, releasing the slot.",
)
def mark_no_show_endpoint(
    appointment_id: int,
    no_show_in: Optional[AppointmentNoShowRequest] = None,
    ignore_grace_period: bool = Query(False, description="Admin or testing bypass for grace period"),
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    notes = no_show_in.notes if no_show_in else None
    return appointment_service.mark_appointment_no_show(
        db=db,
        appointment_id=appointment_id,
        current_user=current_user,
        notes=notes,
        ignore_grace_period=ignore_grace_period,
    )


@router.get(
    "/my",
    response_model=List[AppointmentOut],
    summary="Get My Appointments",
    description="Retrieves active and past appointments for the currently logged-in student or barber.",
)
def get_my_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status_filter: Optional[AppointmentStatus] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return appointment_service.list_user_appointments(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentOut,
    summary="Get Appointment Details",
    description="Retrieves a specific appointment by ID with role-based access validation.",
)
def get_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    appointment = appointment_service.get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )

    if current_user.role == UserRole.STUDENT:
        student = student_service.get_student_by_user_id(db, current_user.id)
        if not student or appointment.student_id != student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view another student's appointment.",
            )
    elif current_user.role == UserRole.BARBER:
        barber = barber_service.get_barber_by_user_id(db, current_user.id)
        if not barber or appointment.barber_id != barber.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view another barber's appointment.",
            )

    return appointment


@router.get(
    "",
    response_model=List[AppointmentOut],
    summary="List All Appointments (Admin Only)",
    description="Administrative search and monitoring of appointments.",
)
def list_all_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    student_id: Optional[int] = None,
    barber_id: Optional[int] = None,
    appointment_date: Optional[date] = None,
    status_filter: Optional[AppointmentStatus] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return appointment_service.list_appointments(
        db=db,
        skip=skip,
        limit=limit,
        student_id=student_id,
        barber_id=barber_id,
        appointment_date=appointment_date,
        status_filter=status_filter,
    )
