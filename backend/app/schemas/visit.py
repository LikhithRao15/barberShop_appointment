from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class VisitBase(BaseModel):
    appointment_id: int
    arrival_time: Optional[datetime] = None
    service_start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = None
    visit_notes: Optional[str] = Field(None, max_length=500)


class VisitCreate(VisitBase):
    pass


class VisitUpdate(BaseModel):
    arrival_time: Optional[datetime] = None
    service_start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = None
    visit_notes: Optional[str] = Field(None, max_length=500)


class VisitActionRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes on visit progress")


class VisitOut(VisitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
