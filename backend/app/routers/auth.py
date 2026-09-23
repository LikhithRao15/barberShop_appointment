from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserOut
from app.models.user import User
from app.services.auth_service import authenticate_user
from app.core.deps import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="User Login",
    description="Authenticates user by username/email and password, returning JWT access token.",
)
async def login(
    request: Request,
    db: Session = Depends(get_db),
) -> Token:
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            username_or_email = form.get("username") or form.get("username_or_email")
            password = form.get("password")
        except Exception:
            body_bytes = await request.body()
            from urllib.parse import parse_qs
            parsed = parse_qs(body_bytes.decode("utf-8"))
            username_or_email = parsed.get("username", [None])[0] or parsed.get("username_or_email", [None])[0]
            password = parsed.get("password", [None])[0]
    else:
        try:
            body = await request.json()
            username_or_email = body.get("username_or_email") or body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid request body. JSON or form-data expected.",
            )

    if not username_or_email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both username/email and password are required.",
        )

    login_data = LoginRequest(username_or_email=str(username_or_email), password=str(password))
    return authenticate_user(db, login_data)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get Current User Profile",
    description="Retrieves profile information for the currently authenticated active user.",
)
def get_me(
    current_user: User = Depends(get_current_active_user),
) -> User:
    return current_user


@router.post(
    "/logout",
    summary="User Logout",
    description="Stateless JWT logout endpoint. Clients should discard stored access tokens.",
)
def logout(
    current_user: User = Depends(get_current_active_user),
):
    return {
        "message": f"User '{current_user.username}' logged out successfully.",
        "status": "success",
    }
