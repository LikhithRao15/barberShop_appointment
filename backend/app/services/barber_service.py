import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.barber import Barber
from app.schemas.barber import BarberCreate, BarberUpdate, BarberProfileUpdate
from app.schemas.user import UserCreate
from app.services.user_service import create_user, get_user_by_id

logger = logging.getLogger(__name__)


def get_barber_by_id(db: Session, barber_id: int) -> Optional[Barber]:
    return db.query(Barber).filter(Barber.id == barber_id).first()


def get_barber_by_user_id(db: Session, user_id: int) -> Optional[Barber]:
    return db.query(Barber).filter(Barber.user_id == user_id).first()


def list_barbers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    available_only: bool = False,
) -> List[Barber]:
    query = db.query(Barber).join(User, Barber.user_id == User.id)
    if available_only:
        query = query.filter(
            Barber.is_available_for_booking == True,
            User.is_active == True,
        )
    return query.offset(skip).limit(limit).all()


def create_barber(db: Session, barber_in: BarberCreate) -> Barber:
    user: Optional[User] = None

    if barber_in.user_id:
        user = get_user_by_id(db, barber_in.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {barber_in.user_id} not found.",
            )
        if user.role != UserRole.BARBER:
            user.role = UserRole.BARBER
        existing_profile = get_barber_by_user_id(db, user.id)
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an associated barber profile.",
            )
    else:
        # Create user account for barber
        if not (barber_in.email and barber_in.username and barber_in.full_name and barber_in.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User credentials (email, username, full_name, password) are required when user_id is not specified.",
            )
        user_create = UserCreate(
            email=barber_in.email,
            username=barber_in.username,
            full_name=barber_in.full_name,
            phone_number=barber_in.phone_number,
            password=barber_in.password,
            role=UserRole.BARBER,
            is_active=True,
        )
        user = create_user(db, user_create)

    barber = Barber(
        user_id=user.id,
        bio=barber_in.bio.strip() if barber_in.bio else None,
        specialties=barber_in.specialties.strip() if barber_in.specialties else None,
        shop_name=barber_in.shop_name.strip() if barber_in.shop_name else "Campus Barber Shop",
        chair_number=barber_in.chair_number,
        is_available_for_booking=barber_in.is_available_for_booking,
    )
    db.add(barber)
    db.commit()
    db.refresh(barber)
    return barber


def update_barber(db: Session, barber: Barber, barber_in: BarberUpdate) -> Barber:
    if barber_in.bio is not None:
        barber.bio = barber_in.bio.strip() if barber_in.bio else None
    if barber_in.specialties is not None:
        barber.specialties = barber_in.specialties.strip() if barber_in.specialties else None
    if barber_in.shop_name is not None:
        barber.shop_name = barber_in.shop_name.strip() if barber_in.shop_name else None
    if barber_in.chair_number is not None:
        barber.chair_number = barber_in.chair_number
    if barber_in.is_available_for_booking is not None:
        barber.is_available_for_booking = barber_in.is_available_for_booking

    # Update associated user fields
    if barber.user:
        if barber_in.full_name is not None:
            barber.user.full_name = barber_in.full_name.strip()
        if barber_in.phone_number is not None:
            barber.user.phone_number = barber_in.phone_number.strip() if barber_in.phone_number else None
        if barber_in.is_active is not None:
            barber.user.is_active = barber_in.is_active

    db.commit()
    db.refresh(barber)
    return barber


def update_barber_profile(
    db: Session, barber: Barber, profile_in: BarberProfileUpdate
) -> Barber:
    """Allowed self-service updates by the barber."""
    if profile_in.bio is not None:
        barber.bio = profile_in.bio.strip() if profile_in.bio else None
    if profile_in.specialties is not None:
        barber.specialties = profile_in.specialties.strip() if profile_in.specialties else None
    if barber.user and profile_in.phone_number is not None:
        barber.user.phone_number = profile_in.phone_number.strip() if profile_in.phone_number else None

    db.commit()
    db.refresh(barber)
    return barber
