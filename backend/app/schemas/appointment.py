from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.models.appointment import AppointmentStatus
from app.schemas.student import StudentOut
from app.schemas.barber import BarberOut
from app.schemas.service import ServiceOut


class TimeSlot(BaseModel):
    start_time: time
    end_time: time
    is_available: bool = True
    duration_minutes: int
    is_available_now_slot: bool = False


class AvailabilityResponse(BaseModel):
    barber_id: int
    barber_name: str
    service_id: int
    service_name: str
    duration_minutes: int
    target_date: date
    is_working_day: bool
    working_start_time: Optional[time] = None
    working_end_time: Optional[time] = None
    available_slots: List[TimeSlot] = []


class AppointmentCreate(BaseModel):
    barber_id: int
    service_id: int
    appointment_date: date
    start_time: time
    notes: Optional[str] = Field(None, max_length=500)


class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255, description="Reason for appointment cancellation")


class AppointmentNoShowRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=255)


class AvailableNowSlotOut(BaseModel):
    released_appointment_id: int
    barber_id: int
    barber_name: str
    shop_name: Optional[str] = None
    chair_number: Optional[int] = None
    service_id: int
    service_name: str
    duration_minutes: int
    appointment_date: date
    start_time: time
    end_time: time
    release_reason: str

    model_config = ConfigDict(from_attributes=True)


class ClaimAvailableNowRequest(BaseModel):
    service_id: int
    notes: Optional[str] = None


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    reason: Optional[str] = Field(None, max_length=255)


class AppointmentOut(BaseModel):
    id: int
    student_id: int
    barber_id: int
    service_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: AppointmentStatus
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    no_show_at: Optional[datetime] = None
    is_available_now_slot: bool = False
    created_at: datetime
    updated_at: datetime

    student: Optional[StudentOut] = None
    barber: Optional[BarberOut] = None
    service: Optional[ServiceOut] = None

    model_config = ConfigDict(from_attributes=True)
