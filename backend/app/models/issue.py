from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow
from app.models.enums import Priority
from app.models.project import BoardColumn, Label, Project
from app.models.user import User

issue_labels = Table(
    "issue_labels",
    Base.metadata,
    Column("issue_id", ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        Index("ix_issues_column_position", "column_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20), default=Priority.medium)
    column_id: Mapped[int] = mapped_column(ForeignKey("board_columns.id", ondelete="RESTRICT"))
    # Order within the column, 0 at the top.
    position: Mapped[int] = mapped_column(Integer, default=0)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reporter_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Manual blocked flag; open "blocks" links make an issue blocked as well.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow
    )

    project: Mapped[Project] = relationship(lazy="joined")
    column: Mapped[BoardColumn] = relationship(lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
    reporter: Mapped[User | None] = relationship(foreign_keys=[reporter_id], lazy="joined")
    parent: Mapped[Optional["Issue"]] = relationship(remote_side=[id], lazy="joined")
    labels: Mapped[list[Label]] = relationship(
        secondary=issue_labels, lazy="selectin", order_by=Label.name
    )

    @property
    def key(self) -> str:
        return f"{self.project.key}-{self.number}"


class IssueLink(Base):
    """A directed link: `from_issue` <type> `to_issue` (e.g. AEG-1 blocks AEG-7)."""

    __tablename__ = "issue_links"
    __table_args__ = (UniqueConstraint("from_issue_id", "to_issue_id", "type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    from_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True
    )
    to_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    from_issue: Mapped[Issue] = relationship(foreign_keys=[from_issue_id], lazy="joined")
    to_issue: Mapped[Issue] = relationship(foreign_keys=[to_issue_id], lazy="joined")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow
    )

    author: Mapped[User | None] = relationship(lazy="joined")


class Activity(Base):
    """Append-only history of changes. Rows are never updated or deleted by the app."""

    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # Kept as SET NULL + issue_key so history survives issue deletion.
    issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    issue_key: Mapped[str] = mapped_column(String(24), default="")
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, index=True
    )

    actor: Mapped[User | None] = relationship(lazy="joined")
