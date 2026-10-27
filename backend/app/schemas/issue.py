from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.models.enums import IssueType, LinkType, Priority
from app.schemas import CamelModel
from app.schemas.project import LabelOut
from app.schemas.user import UserRef


class IssueRef(CamelModel):
    key: str
    title: str
    type: IssueType
    column_id: int
    done: bool


class IssueOut(CamelModel):
    id: int
    key: str
    number: int
    project_key: str
    title: str
    description: str
    type: IssueType
    priority: Priority
    column_id: int
    position: int
    assignee: UserRef | None
    reporter: UserRef | None
    parent_key: str | None
    due_date: date | None
    is_blocked: bool
    blocked_reason: str
    # Keys of open issues that block this one through a "blocks" link.
    blocked_by: list[str]
    # Effective state: manual flag or any open blocker.
    blocked: bool
    done: bool
    labels: list[LabelOut]
    created_at: datetime
    updated_at: datetime


class LinkOut(CamelModel):
    id: int
    type: LinkType
    # "outward": this issue <type> other; "inward": other <type> this issue.
    direction: Literal["outward", "inward"]
    issue: IssueRef


class IssueDetail(IssueOut):
    links: list[LinkOut]
    children: list[IssueRef]


class IssueCreate(CamelModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=50_000)
    type: IssueType = IssueType.task
    priority: Priority = Priority.medium
    column_id: int | None = None
    assignee_id: int | None = None
    parent_key: str | None = None
    due_date: date | None = None
    label_ids: list[int] = Field(default_factory=list)


class IssueUpdate(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    type: IssueType | None = None
    priority: Priority | None = None
    assignee_id: int | None = None
    parent_key: str | None = None
    due_date: date | None = None
    is_blocked: bool | None = None
    blocked_reason: str | None = Field(default=None, max_length=5_000)
    label_ids: list[int] | None = None


class IssueMove(CamelModel):
    column_id: int
    # Target index within the column; past the end appends.
    index: int = Field(ge=0)


class LinkCreate(CamelModel):
    type: LinkType
    # This issue <type> target (e.g. this issue blocks target).
    target_key: str


class CommentOut(CamelModel):
    id: int
    author: UserRef | None
    body: str
    created_at: datetime
    updated_at: datetime


class CommentCreate(CamelModel):
    body: str = Field(min_length=1, max_length=20_000)


class ActivityOut(CamelModel):
    id: int
    issue_key: str
    actor: UserRef | None
    action: str
    details: dict[str, Any]
    created_at: datetime


class ColumnCount(CamelModel):
    column_id: int
    name: str
    count: int


class ProjectSummary(CamelModel):
    total: int
    open: int
    blocked: int
    overdue: int
    open_decisions: int
    by_column: list[ColumnCount]
    by_type: dict[str, int]
    recent_activity: list[ActivityOut]
