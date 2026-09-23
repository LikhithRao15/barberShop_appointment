import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username.lower()).first()


def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
    cleaned = identifier.strip().lower()
    return db.query(User).filter(
        or_(User.username == cleaned, User.email == cleaned)
    ).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    # Check if username or email already exists
    if get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    if get_user_by_username(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists.",
        )

    db_user = User(
        email=user_in.email.lower(),
        username=user_in.username.lower(),
        full_name=user_in.full_name.strip(),
        phone_number=user_in.phone_number.strip() if user_in.phone_number else None,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    if user_in.email and user_in.email.lower() != user.email:
        existing = get_user_by_email(db, user_in.email)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use by another account.",
            )
        user.email = user_in.email.lower()

    if user_in.username and user_in.username.lower() != user.username:
        existing = get_user_by_username(db, user_in.username)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already in use by another account.",
            )
        user.username = user_in.username.lower()

    if user_in.full_name is not None:
        user.full_name = user_in.full_name.strip()
    if user_in.phone_number is not None:
        user.phone_number = user_in.phone_number.strip() if user_in.phone_number else None
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.role is not None:
        user.role = user_in.role

    db.commit()
    db.refresh(user)
    return user


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
) -> List[User]:
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return query.offset(skip).limit(limit).all()


def seed_initial_admin(db: Session) -> User:
    """Seeds a default system admin if none exists."""
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if not admin:
        logger.info("No admin user found. Creating initial system admin...")
        admin = User(
            email="admin@barberbooking.com",
            username="admin",
            full_name="System Administrator",
            phone_number="555-0100",
            hashed_password=get_password_hash("Admin@123456"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Initial system admin created (username: admin, email: admin@barberbooking.com).")
    else:
        # Normalize email if it had .local
        if admin.email.endswith(".local"):
            admin.email = "admin@barberbooking.com"
            db.commit()
            db.refresh(admin)
    return admin
