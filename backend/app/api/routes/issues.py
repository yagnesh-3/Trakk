from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ProjectAccess, get_current_user, project_access
from app.db.session import get_db
from app.models import Activity, Comment, User
from app.models.enums import IssueType, Priority, ProjectRole
from app.schemas.issue import (
    ActivityOut,
    CommentCreate,
    CommentOut,
    IssueCreate,
    IssueDetail,
    IssueMove,
    IssueOut,
    IssueUpdate,
    LinkCreate,
    ProjectSummary,
)
from app.services import activity, issues

router = APIRouter(tags=["issues"])


@router.get("/projects/{project_key}/issues", response_model=list[IssueOut])
def list_issues(
    q: str | None = None,
    type: list[IssueType] | None = Query(default=None),
    assignee: str | None = Query(default=None, description="user id, 'me' or 'none'"),
    label_id: int | None = Query(default=None, alias="labelId"),
    priority: Priority | None = None,
    column_id: int | None = Query(default=None, alias="columnId"),
    parent: str | None = Query(default=None, description="parent issue key"),
    blocked: bool | None = None,
    access: ProjectAccess = Depends(project_access(ProjectRole.viewer)),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    return issues.list_issues(
        db, access.project, access.user, q=q, types=type, assignee=assignee, label_id=label_id,
        priority=priority, column_id=column_id, parent_key=parent, blocked=blocked,
    )


@router.post("/projects/{project_key}/issues", response_model=IssueDetail,
             status_code=status.HTTP_201_CREATED)
def create_issue(
    data: IssueCreate,
    access: ProjectAccess = Depends(project_access(ProjectRole.developer)),
    db: Session = Depends(get_db),
) -> IssueDetail:
    return issues.serialize_detail(db, issues.create_issue(db, access, data))


@router.get("/projects/{project_key}/summary", response_model=ProjectSummary)
def project_summary(
    access: ProjectAccess = Depends(project_access(ProjectRole.viewer)),
    db: Session = Depends(get_db),
) -> ProjectSummary:
    return issues.project_summary(db, access.project, date.today())


@router.get("/issues/{key}", response_model=IssueDetail)
def get_issue(
    key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> IssueDetail:
    issue, _ = issues.load_issue(db, key, user)
    return issues.serialize_detail(db, issue)


@router.patch("/issues/{key}", response_model=IssueDetail)
def update_issue(
    key: str,
    data: IssueUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueDetail:
    issue, access = issues.load_issue(db, key, user, ProjectRole.client)
    return issues.serialize_detail(db, issues.update_issue(db, issue, access, data))


@router.post("/issues/{key}/move", response_model=IssueDetail)
def move_issue(
    key: str,
    data: IssueMove,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueDetail:
    issue, access = issues.load_issue(db, key, user, ProjectRole.client)
    return issues.serialize_detail(
        db, issues.move_issue(db, issue, access, data.column_id, data.index)
    )


@router.delete("/issues/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    issue, access = issues.load_issue(db, key, user, ProjectRole.developer)
    issues.delete_issue(db, issue, access)


@router.get("/issues/{key}/activity", response_model=list[ActivityOut])
def issue_activity(
    key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Activity]:
    issue, _ = issues.load_issue(db, key, user)
    return activity.list_for_issue(db, issue)


# --- links -------------------------------------------------------------------


@router.post("/issues/{key}/links", response_model=IssueDetail,
             status_code=status.HTTP_201_CREATED)
def add_link(
    key: str,
    data: LinkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueDetail:
    issue, access = issues.load_issue(db, key, user, ProjectRole.developer)
    issues.add_link(db, issue, access, data.type, data.target_key)
    return issues.serialize_detail(db, issue)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_link(
    link_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    issues.remove_link(db, link_id, user)


# --- comments ----------------------------------------------------------------


@router.get("/issues/{key}/comments", response_model=list[CommentOut])
def list_comments(
    key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Comment]:
    issue, _ = issues.load_issue(db, key, user)
    return issues.list_comments(db, issue)


@router.post("/issues/{key}/comments", response_model=CommentOut,
             status_code=status.HTTP_201_CREATED)
def add_comment(
    key: str,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Comment:
    issue, access = issues.load_issue(db, key, user, ProjectRole.client)
    return issues.add_comment(db, issue, access, data.body)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def edit_comment(
    comment_id: int,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Comment:
    return issues.edit_comment(db, comment_id, user, data.body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    issues.delete_comment(db, comment_id, user)
