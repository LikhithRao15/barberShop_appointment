import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate, StudentProfileUpdate
from app.schemas.user import UserCreate
from app.services.user_service import create_user, get_user_by_id

logger = logging.getLogger(__name__)


def get_student_by_id(db: Session, student_id: int) -> Optional[Student]:
    return db.query(Student).filter(Student.id == student_id).first()


def get_student_by_user_id(db: Session, user_id: int) -> Optional[Student]:
    return db.query(Student).filter(Student.user_id == user_id).first()


def get_student_by_student_number(db: Session, student_id_number: str) -> Optional[Student]:
    return db.query(Student).filter(
        Student.student_id_number == student_id_number.strip()
    ).first()


def list_students(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    department: Optional[str] = None,
) -> List[Student]:
    query = db.query(Student)
    if department:
        query = query.filter(Student.department == department)
    return query.offset(skip).limit(limit).all()


def create_student(db: Session, student_in: StudentCreate) -> Student:
    # Check if student_id_number already exists
    if get_student_by_student_number(db, student_in.student_id_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A student with ID number '{student_in.student_id_number}' already exists.",
        )

    user: Optional[User] = None

    if student_in.user_id:
        user = get_user_by_id(db, student_in.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {student_in.user_id} not found.",
            )
        if user.role != UserRole.STUDENT:
            user.role = UserRole.STUDENT
        existing_profile = get_student_by_user_id(db, user.id)
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an associated student profile.",
            )
    else:
        # Create a new user first
        if not (student_in.email and student_in.username and student_in.full_name and student_in.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User credentials (email, username, full_name, password) are required when user_id is not specified.",
            )
        user_create = UserCreate(
            email=student_in.email,
            username=student_in.username,
            full_name=student_in.full_name,
            phone_number=student_in.phone_number,
            password=student_in.password,
            role=UserRole.STUDENT,
            is_active=True,
        )
        user = create_user(db, user_create)

    student = Student(
        user_id=user.id,
        student_id_number=student_in.student_id_number.strip(),
        department=student_in.department.strip() if student_in.department else None,
        year_of_study=student_in.year_of_study,
        hostel_or_room=student_in.hostel_or_room.strip() if student_in.hostel_or_room else None,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student: Student, student_in: StudentUpdate) -> Student:
    if student_in.student_id_number and student_in.student_id_number.strip() != student.student_id_number:
        existing = get_student_by_student_number(db, student_in.student_id_number)
        if existing and existing.id != student.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student ID number '{student_in.student_id_number}' is already assigned to another student.",
            )
        student.student_id_number = student_in.student_id_number.strip()

    if student_in.department is not None:
        student.department = student_in.department.strip() if student_in.department else None
    if student_in.year_of_study is not None:
        student.year_of_study = student_in.year_of_study
    if student_in.hostel_or_room is not None:
        student.hostel_or_room = student_in.hostel_or_room.strip() if student_in.hostel_or_room else None

    # Update associated user fields if provided
    if student.user:
        if student_in.full_name is not None:
            student.user.full_name = student_in.full_name.strip()
        if student_in.phone_number is not None:
            student.user.phone_number = student_in.phone_number.strip() if student_in.phone_number else None
        if student_in.is_active is not None:
            student.user.is_active = student_in.is_active

    db.commit()
    db.refresh(student)
    return student


def update_student_profile(
    db: Session, student: Student, profile_in: StudentProfileUpdate
) -> Student:
    """Allowed self-service updates by the student themselves."""
    if profile_in.department is not None:
        student.department = profile_in.department.strip() if profile_in.department else None
    if profile_in.year_of_study is not None:
        student.year_of_study = profile_in.year_of_study
    if profile_in.hostel_or_room is not None:
        student.hostel_or_room = profile_in.hostel_or_room.strip() if profile_in.hostel_or_room else None

    if student.user:
        if profile_in.full_name is not None:
            student.user.full_name = profile_in.full_name.strip()
        if profile_in.phone_number is not None:
            student.user.phone_number = profile_in.phone_number.strip() if profile_in.phone_number else None

    db.commit()
    db.refresh(student)
    return student
