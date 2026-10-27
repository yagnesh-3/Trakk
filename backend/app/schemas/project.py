from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.models.enums import ColumnCategory, ProjectRole
from app.schemas import CamelModel
from app.schemas.user import UserRef

PROJECT_KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,9}$"
COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class ProjectCreate(CamelModel):
    key: str = Field(pattern=PROJECT_KEY_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10_000)


class ProjectUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)
    archived: bool | None = None


class ProjectOut(CamelModel):
    id: int
    key: str
    name: str
    description: str
    archived: bool
    created_at: datetime
    # The caller's effective role (admins act as owner).
    my_role: ProjectRole


class MemberOut(CamelModel):
    user: UserRef
    role: ProjectRole


class MemberUpsert(CamelModel):
    # Either a user id, or the email of an existing user (owners can't list everyone).
    user_id: int | None = None
    email: EmailStr | None = None
    role: ProjectRole

    @model_validator(mode="after")
    def _one_identifier(self) -> "MemberUpsert":
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Provide exactly one of userId or email")
        return self


class ColumnOut(CamelModel):
    id: int
    name: str
    position: int
    category: ColumnCategory
    wip_limit: int | None


class ColumnCreate(CamelModel):
    name: str = Field(min_length=1, max_length=60)
    category: ColumnCategory = ColumnCategory.todo
    wip_limit: int | None = Field(default=None, ge=1)


class ColumnUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    category: ColumnCategory | None = None
    wip_limit: int | None = Field(default=None, ge=1)


class ColumnOrder(CamelModel):
    column_ids: list[int]


class LabelOut(CamelModel):
    id: int
    name: str
    color: str


class LabelCreate(CamelModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#6b7280", pattern=COLOR_PATTERN)


class LabelUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)
