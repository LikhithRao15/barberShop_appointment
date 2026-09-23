from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.schemas.user import UserOut


class StudentBase(BaseModel):
    student_id_number: str = Field(..., min_length=2, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    hostel_or_room: Optional[str] = Field(None, max_length=100)


class StudentCreate(StudentBase):
    user_id: Optional[int] = None
    # If creating a new user together with student profile:
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)


class StudentUpdate(BaseModel):
    student_id_number: Optional[str] = Field(None, min_length=2, max_length=50)
    department: Optional[str] = None
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    hostel_or_room: Optional[str] = None
    # User fields update
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None


class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = None
    department: Optional[str] = None
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    hostel_or_room: Optional[str] = None


class StudentOut(StudentBase):
    id: int
    user_id: int
    user: UserOut
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
