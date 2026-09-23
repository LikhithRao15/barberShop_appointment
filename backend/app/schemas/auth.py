from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator
from app.models.user import UserRole
from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    username_or_email: Optional[str] = Field(None, description="Username or email address")
    username: Optional[str] = Field(None, description="Alternative field name for username or email")
    password: str = Field(..., min_length=1, description="Account password")

    @model_validator(mode="before")
    @classmethod
    def validate_identifier(cls, data: Any) -> Any:
        if isinstance(data, dict):
            identifier = data.get("username_or_email") or data.get("username")
            if not identifier:
                raise ValueError("username or username_or_email is required")
            data["username_or_email"] = identifier
        return data


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[UserRole] = None
    username: Optional[str] = None
    exp: Optional[int] = None
