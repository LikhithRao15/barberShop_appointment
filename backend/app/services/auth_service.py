from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.services.user_service import get_user_by_username_or_email
from app.core.security import verify_password, create_access_token


def authenticate_user(db: Session, login_data: LoginRequest) -> Token:
    """
    Authenticates a user via username/email and password.
    Validates active status and returns a signed JWT access token with user details.
    """
    user = get_user_by_username_or_email(db, login_data.username_or_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account. Please contact an administrator.",
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        username=user.username,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )
