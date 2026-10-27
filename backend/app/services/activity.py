"""Append-only activity log."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Issue, Project, User


def record(
    db: Session,
    *,
    project: Project,
    actor: User | None,
    action: str,
    issue: Issue | None = None,
    details: dict[str, Any] | None = None,
) -> Activity:
    entry = Activity(
        project_id=project.id,
        issue_id=issue.id if issue else None,
        issue_key=issue.key if issue else "",
        actor=actor,
        action=action,
        details=details or {},
    )
    db.add(entry)
    return entry


def list_for_project(db: Session, project: Project, limit: int = 50) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.project_id == project.id)
            .order_by(Activity.created_at.desc(), Activity.id.desc())
            .limit(limit)
        )
    )


def list_for_issue(db: Session, issue: Issue) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.issue_id == issue.id)
            .order_by(Activity.created_at, Activity.id)
        )
    )
