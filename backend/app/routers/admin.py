from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserOut, UserCreate
from app.schemas.barber import BarberOut
from app.schemas.admin import (
    DashboardStatsOut,
    SystemRulesOut,
    UserStatusUpdate,
    BarberApprovalUpdate,
    StudentBatchImportRequest,
    StudentBatchImportResult,
)
from app.core.deps import require_admin
from app.services import admin_service, user_service, barber_service, student_service

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


@router.get(
    "/dashboard/stats",
    response_model=DashboardStatsOut,
    summary="Get Operational Metrics & Stats",
    description="Returns aggregate counts, status breakdowns, and daily visit counts.",
)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
):
    return admin_service.get_dashboard_stats(db)


@router.get(
    "/system/rules",
    response_model=SystemRulesOut,
    summary="Get System & Scheduling Rules",
    description="Inspects active cancellation policies, grace periods, and JWT configurations.",
)
def get_system_rules():
    return admin_service.get_system_rules()


@router.get(
    "/users",
    response_model=List[UserOut],
    summary="List Users",
    description="Retrieves all system users with optional role and active status filters.",
)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    return user_service.list_users(db, skip=skip, limit=limit, role=role, is_active=is_active)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Account",
    description="Creates a new account with specified role.",
)
def create_user_account(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    return user_service.create_user(db, user_in)


@router.put(
    "/users/{user_id}/status",
    response_model=UserOut,
    summary="Activate / Deactivate User Account",
    description="Toggles the active status of an account. Inactive users cannot log in.",
)
def update_user_status(
    user_id: int,
    status_in: UserStatusUpdate,
    db: Session = Depends(get_db),
):
    return admin_service.set_user_active_status(db, user_id=user_id, is_active=status_in.is_active)


@router.post(
    "/students/import",
    response_model=StudentBatchImportResult,
    summary="Batch Import Student Accounts",
    description="Batches the registration of multiple student accounts in one operation.",
)
def import_students(
    import_req: StudentBatchImportRequest,
    db: Session = Depends(get_db),
):
    return admin_service.batch_import_students(db, import_req)


@router.put(
    "/barbers/{barber_id}/approve",
    response_model=BarberOut,
    summary="Approve / Toggle Barber Availability",
    description="Administrator approval to activate or pause booking availability for a barber.",
)
def approve_barber(
    barber_id: int,
    approval_in: BarberApprovalUpdate,
    db: Session = Depends(get_db),
):
    return admin_service.set_barber_approval(
        db, barber_id=barber_id, is_available_for_booking=approval_in.is_available_for_booking
    )
