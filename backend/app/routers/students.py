from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.student import StudentOut, StudentCreate, StudentUpdate, StudentProfileUpdate
from app.core.deps import get_current_active_user, require_admin, require_student
from app.services import student_service

router = APIRouter(prefix="/students", tags=["Students"])


@router.get(
    "/me",
    response_model=StudentOut,
    summary="Get Current Student Profile",
    description="Returns the profile of the currently logged-in student.",
)
def get_my_student_profile(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student = student_service.get_student_by_user_id(db, current_user.id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for this account.",
        )
    return student


@router.put(
    "/me",
    response_model=StudentOut,
    summary="Update Current Student Profile",
    description="Allows students to update their own contact and academic profile details.",
)
def update_my_student_profile(
    profile_in: StudentProfileUpdate,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student = student_service.get_student_by_user_id(db, current_user.id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for this account.",
        )
    return student_service.update_student_profile(db, student, profile_in)


@router.get(
    "",
    response_model=List[StudentOut],
    summary="List All Students (Admin Only)",
    description="Retrieves a paginated list of all enrolled students in the system.",
)
def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    department: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return student_service.list_students(db, skip=skip, limit=limit, department=department)


@router.get(
    "/{student_id}",
    response_model=StudentOut,
    summary="Get Student Details (Admin Only)",
    description="Retrieves a single student's profile by their system ID.",
)
def get_student(
    student_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    student = student_service.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )
    return student


@router.post(
    "",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create/Register Student (Admin Only)",
    description="Admin-only endpoint to onboard a new student account.",
)
def create_student(
    student_in: StudentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return student_service.create_student(db, student_in)


@router.put(
    "/{student_id}",
    response_model=StudentOut,
    summary="Update Student Profile (Admin Only)",
    description="Admin-only endpoint to modify any student's record and active status.",
)
def update_student(
    student_id: int,
    student_in: StudentUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    student = student_service.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )
    return student_service.update_student(db, student, student_in)
