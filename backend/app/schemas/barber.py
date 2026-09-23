from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.schemas.user import UserOut


class BarberBase(BaseModel):
    bio: Optional[str] = None
    specialties: Optional[str] = Field(None, max_length=255)
    shop_name: Optional[str] = Field("Campus Barber Shop", max_length=150)
    chair_number: Optional[int] = Field(None, ge=1, le=100)
    is_available_for_booking: bool = True


class BarberCreate(BarberBase):
    user_id: Optional[int] = None
    # If creating a new user together with barber profile:
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)


class BarberUpdate(BaseModel):
    bio: Optional[str] = None
    specialties: Optional[str] = Field(None, max_length=255)
    shop_name: Optional[str] = Field(None, max_length=150)
    chair_number: Optional[int] = Field(None, ge=1, le=100)
    is_available_for_booking: Optional[bool] = None
    # User fields update
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None


class BarberProfileUpdate(BaseModel):
    bio: Optional[str] = None
    specialties: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = None


class BarberOut(BarberBase):
    id: int
    user_id: int
    user: UserOut
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
