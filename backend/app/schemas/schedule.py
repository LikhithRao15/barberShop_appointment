from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BreakBase(BaseModel):
    name: str = Field("Lunch Break", max_length=100)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time >= self.end_time:
            raise ValueError("Break start_time must be earlier than end_time.")
        return self


class BreakCreate(BreakBase):
    pass


class BreakOut(BreakBase):
    id: int
    schedule_id: int

    model_config = ConfigDict(from_attributes=True)


class BlockedPeriodBase(BaseModel):
    barber_id: int
    blocked_date: date
    start_time: time
    end_time: time
    reason: Optional[str] = Field("Unavailable", max_length=255)

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time >= self.end_time:
            raise ValueError("Blocked period start_time must be earlier than end_time.")
        return self


class BlockedPeriodCreate(BlockedPeriodBase):
    pass


class BlockedPeriodOut(BlockedPeriodBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleBase(BaseModel):
    barber_id: int
    schedule_date: Optional[date] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    is_day_off: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_schedule(self):
        if not self.is_day_off and self.start_time >= self.end_time:
            raise ValueError("Schedule start_time must be earlier than end_time.")
        if self.schedule_date is None and self.day_of_week is None:
            raise ValueError("Either schedule_date (for date override) or day_of_week (for recurring) must be provided.")
        return self


class ScheduleCreate(ScheduleBase):
    breaks: Optional[List[BreakCreate]] = []


class ScheduleUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_day_off: Optional[bool] = None
    is_active: Optional[bool] = None
    breaks: Optional[List[BreakCreate]] = None


class ScheduleOut(ScheduleBase):
    id: int
    breaks: List[BreakOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyScheduleDetail(BaseModel):
    barber_id: int
    target_date: date
    day_of_week: int
    is_working: bool
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    breaks: List[BreakBase] = []
    blocked_periods: List[BlockedPeriodBase] = []
