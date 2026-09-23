from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.visit import VisitOut, VisitActionRequest
from app.core.deps import get_current_active_user, require_admin, require_barber
from app.services import visit_service, appointment_service

router = APIRouter(prefix="/visits", tags=["Visits"])


@router.get(
    "/appointment/{appointment_id}",
    response_model=VisitOut,
    summary="Get Visit by Appointment ID",
    description="Retrieves the detailed physical visit record (arrival, start, completion) for an appointment.",
)
def get_visit_by_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    visit = visit_service.get_visit_by_appointment_id(db, appointment_id)
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit record for appointment {appointment_id} not found.",
        )
    return visit


@router.get(
    "/{visit_id}",
    response_model=VisitOut,
    summary="Get Visit by ID",
    description="Retrieves a specific visit record by its primary ID.",
)
def get_visit(
    visit_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    visit = visit_service.get_visit_by_id(db, visit_id)
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit record {visit_id} not found.",
        )
    return visit


@router.get(
    "",
    response_model=List[VisitOut],
    summary="List Visits (Admin Only)",
    description="Retrieves paginated visit records for auditing and metrics.",
)
def list_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return visit_service.list_visits(db, skip=skip, limit=limit)
