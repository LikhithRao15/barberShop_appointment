from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.barber import BarberOut, BarberCreate, BarberUpdate, BarberProfileUpdate
from app.core.deps import get_current_active_user, require_admin, require_barber
from app.services import barber_service

router = APIRouter(prefix="/barbers", tags=["Barbers"])


@router.get(
    "",
    response_model=List[BarberOut],
    summary="List Barbers",
    description="Lists active barbers available for bookings.",
)
def list_barbers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    available_only: bool = True,
    db: Session = Depends(get_db),
):
    return barber_service.list_barbers(db, skip=skip, limit=limit, available_only=available_only)


@router.get(
    "/me",
    response_model=BarberOut,
    summary="Get Current Barber Profile",
    description="Returns the profile of the currently logged-in barber.",
)
def get_my_barber_profile(
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    barber = barber_service.get_barber_by_user_id(db, current_user.id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barber profile not found for this account.",
        )
    return barber


@router.put(
    "/me",
    response_model=BarberOut,
    summary="Update Current Barber Profile",
    description="Allows barbers to update their bio, specialties, and contact info.",
)
def update_my_barber_profile(
    profile_in: BarberProfileUpdate,
    current_user: User = Depends(require_barber),
    db: Session = Depends(get_db),
):
    barber = barber_service.get_barber_by_user_id(db, current_user.id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barber profile not found for this account.",
        )
    return barber_service.update_barber_profile(db, barber, profile_in)


@router.get(
    "/{barber_id}",
    response_model=BarberOut,
    summary="Get Barber by ID",
    description="Retrieves a specific barber's profile details.",
)
def get_barber(
    barber_id: int,
    db: Session = Depends(get_db),
):
    barber = barber_service.get_barber_by_id(db, barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {barber_id} not found.",
        )
    return barber


@router.post(
    "",
    response_model=BarberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Barber (Admin Only)",
    description="Admin endpoint to register and configure a new barber account.",
)
def create_barber(
    barber_in: BarberCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return barber_service.create_barber(db, barber_in)


@router.put(
    "/{barber_id}",
    response_model=BarberOut,
    summary="Update Barber (Admin Only)",
    description="Admin endpoint to modify barber station assignment and status.",
)
def update_barber(
    barber_id: int,
    barber_in: BarberUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    barber = barber_service.get_barber_by_id(db, barber_id)
    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Barber with ID {barber_id} not found.",
        )
    return barber_service.update_barber(db, barber, barber_in)
