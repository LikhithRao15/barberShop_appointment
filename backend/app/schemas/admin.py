from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.user import UserRole
from app.schemas.user import UserOut
from app.schemas.student import StudentCreate, StudentOut
from app.schemas.barber import BarberOut


class UserStatusUpdate(BaseModel):
    is_active: bool


class BarberApprovalUpdate(BaseModel):
    is_available_for_booking: bool


class DashboardStatsOut(BaseModel):
    total_users: int
    total_students: int
    total_barbers: int
    total_services: int
    total_appointments: int
    appointments_by_status: Dict[str, int]
    today_appointments_count: int
    today_completed_visits: int
    today_no_shows: int
    today_cancellations: int


class SystemRulesOut(BaseModel):
    project_name: str
    environment: str
    cancellation_cutoff_minutes: int
    no_show_grace_period_minutes: int
    access_token_expire_minutes: int
    jwt_algorithm: str
    version: str


class StudentBatchImportRequest(BaseModel):
    students: List[StudentCreate]


class StudentBatchImportResult(BaseModel):
    total_requested: int
    successful_count: int
    failed_count: int
    created_students: List[StudentOut]
    errors: List[str]
