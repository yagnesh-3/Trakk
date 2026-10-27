from datetime import datetime

from pydantic import EmailStr, Field

from app.models.enums import SystemRole
from app.schemas import CamelModel

PASSWORD_MIN = 10


class UserRef(CamelModel):
    """Minimal user info embedded in other resources."""

    id: int
    name: str
    email: str


class UserOut(UserRef):
    system_role: SystemRole
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserCreate(CamelModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=PASSWORD_MIN, max_length=200)
    system_role: SystemRole = SystemRole.member


class UserUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_role: SystemRole | None = None
    is_active: bool | None = None
    # Admin password reset: the user must change it again on next login.
    password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=200)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(CamelModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=200)


class ApiTokenCreate(CamelModel):
    name: str = Field(min_length=1, max_length=100)


class ApiTokenOut(CamelModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class ApiTokenCreated(ApiTokenOut):
    # Shown once at creation; only a hash is stored.
    token: str
