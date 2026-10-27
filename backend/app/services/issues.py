"""Issues: create/update/move, links, comments, serialization and project summary."""

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.deps import ProjectAccess, resolve_project_access
from app.models import BoardColumn, Comment, Issue, IssueLink, Label, Project, User
from app.models.enums import ColumnCategory, IssueType, LinkType, ProjectRole
from app.schemas.issue import (
    ActivityOut,
    ColumnCount,
    IssueCreate,
    IssueDetail,
    IssueOut,
    IssueRef,
    IssueUpdate,
    LinkOut,
    ProjectSummary,
)
from app.schemas.project import LabelOut
from app.schemas.user import UserRef
from app.services import activity, projects

# Fields a client may change, and only on decision issues.
CLIENT_EDITABLE_FIELDS = {"description"}


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")


def parse_key(key: str) -> tuple[str, int]:
    project_key, sep, number = key.upper().rpartition("-")
    if not sep or not project_key or not number.isdigit():
        raise _not_found()
    return project_key, int(number)


def find_issue(db: Session, project: Project, number: int) -> Issue | None:
    return db.scalar(select(Issue).where(Issue.project_id == project.id, Issue.number == number))


def load_issue(
    db: Session, key: str, user: User, min_role: ProjectRole = ProjectRole.viewer
) -> tuple[Issue, ProjectAccess]:
    project_key, number = parse_key(key)
    project = db.scalar(select(Project).where(Project.key == project_key))
    access = resolve_project_access(db, project, user, ProjectRole.viewer)
    issue = find_issue(db, access.project, number)
    if issue is None:
        raise _not_found()
    if not access.has(min_role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")
    return issue, access


def _issue_in_project(db: Session, project: Project, key: str, what: str) -> Issue:
    project_key, number = parse_key(key)
    issue = find_issue(db, project, number) if project_key == project.key else None
    if issue is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"{what} must be an issue in this project"
        )
    return issue


def _labels(db: Session, project: Project, label_ids: list[int]) -> list[Label]:
    if not label_ids:
        return []
    labels = list(
        db.scalars(select(Label).where(Label.project_id == project.id, Label.id.in_(label_ids)))
    )
    if len(labels) != len(set(label_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown label")
    return labels


def _check_parent(issue: Issue | None, parent: Issue) -> None:
    node: Issue | None = parent
    while node is not None:
        if issue is not None and node.id == issue.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "An issue cannot be its own ancestor"
            )
        node = node.parent


# --- serialization -------------------------------------------------------------


def _user_ref(user: User | None) -> UserRef | None:
    return UserRef.model_validate(user) if user else None


def _is_done(issue: Issue) -> bool:
    return issue.column.category == ColumnCategory.done


def _ref(issue: Issue) -> IssueRef:
    return IssueRef(
        key=issue.key, title=issue.title, type=IssueType(issue.type),
        column_id=issue.column_id, done=_is_done(issue),
    )


def open_blockers(db: Session, issue_ids: list[int]) -> dict[int, list[str]]:
    """Map issue id -> keys of not-done issues that block it."""
    if not issue_ids:
        return {}
    blocker = aliased(Issue)
    rows = db.execute(
        select(IssueLink.to_issue_id, blocker)
        .join(blocker, blocker.id == IssueLink.from_issue_id)
        .join(BoardColumn, BoardColumn.id == blocker.column_id)
        .where(
            IssueLink.type == LinkType.blocks,
            IssueLink.to_issue_id.in_(issue_ids),
            BoardColumn.category != ColumnCategory.done,
        )
    )
    result: dict[int, list[str]] = defaultdict(list)
    for to_id, blocking in rows:
        result[to_id].append(blocking.key)
    return result


def _out_fields(issue: Issue, blocked_by: list[str]) -> dict[str, Any]:
    return {
        "id": issue.id,
        "key": issue.key,
        "number": issue.number,
        "project_key": issue.project.key,
        "title": issue.title,
        "description": issue.description,
        "type": issue.type,
        "priority": issue.priority,
        "column_id": issue.column_id,
        "position": issue.position,
        "assignee": _user_ref(issue.assignee),
        "reporter": _user_ref(issue.reporter),
        "parent_key": issue.parent.key if issue.parent else None,
        "due_date": issue.due_date,
        "is_blocked": issue.is_blocked,
        "blocked_reason": issue.blocked_reason,
        "blocked_by": sorted(blocked_by),
        "blocked": issue.is_blocked or bool(blocked_by),
        "done": _is_done(issue),
        "labels": [LabelOut.model_validate(label) for label in issue.labels],
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
    }


def serialize(db: Session, issues: list[Issue]) -> list[IssueOut]:
    blockers = open_blockers(db, [i.id for i in issues])
    return [IssueOut(**_out_fields(i, blockers.get(i.id, []))) for i in issues]


def serialize_detail(db: Session, issue: Issue) -> IssueDetail:
    blockers = open_blockers(db, [issue.id])
    links = db.scalars(
        select(IssueLink)
        .where((IssueLink.from_issue_id == issue.id) | (IssueLink.to_issue_id == issue.id))
        .order_by(IssueLink.id)
    )
    link_out = [
        LinkOut(
            id=link.id,
            type=LinkType(link.type),
            direction="outward" if link.from_issue_id == issue.id else "inward",
            issue=_ref(link.to_issue if link.from_issue_id == issue.id else link.from_issue),
        )
        for link in links
    ]
    children = db.scalars(select(Issue).where(Issue.parent_id == issue.id).order_by(Issue.number))
    return IssueDetail(
        **_out_fields(issue, blockers.get(issue.id, [])),
        links=link_out,
        children=[_ref(child) for child in children],
    )


# --- queries -----------------------------------------------------------------


def list_issues(
    db: Session,
    project: Project,
    user: User,
    *,
    q: str | None = None,
    types: list[IssueType] | None = None,
    assignee: str | None = None,
    label_id: int | None = None,
    priority: str | None = None,
    column_id: int | None = None,
    parent_key: str | None = None,
    blocked: bool | None = None,
) -> list[IssueOut]:
    query = (
        select(Issue)
        .join(BoardColumn, BoardColumn.id == Issue.column_id)
        .where(Issue.project_id == project.id)
        .order_by(BoardColumn.position, Issue.position, Issue.id)
    )
    if q:
        term = q.strip()
        number = term.upper().removeprefix(f"{project.key}-")
        cond = Issue.title.ilike(f"%{term}%")
        if number.isdigit():
            cond = cond | (Issue.number == int(number))
        query = query.where(cond)
    if types:
        query = query.where(Issue.type.in_(types))
    if assignee == "none":
        query = query.where(Issue.assignee_id.is_(None))
    elif assignee == "me":
        query = query.where(Issue.assignee_id == user.id)
    elif assignee and assignee.isdigit():
        query = query.where(Issue.assignee_id == int(assignee))
    if label_id is not None:
        query = query.where(Issue.labels.any(Label.id == label_id))
    if priority:
        query = query.where(Issue.priority == priority)
    if column_id is not None:
        query = query.where(Issue.column_id == column_id)
    if parent_key:
        _, number = parse_key(parent_key)
        parent = find_issue(db, project, number)
        query = query.where(Issue.parent_id == (parent.id if parent else -1))
    result = serialize(db, list(db.scalars(query).unique()))
    if blocked is not None:
        result = [i for i in result if i.blocked == blocked]
    return result


def list_my_decisions(db: Session, user: User) -> list[IssueOut]:
    """Open decision issues assigned to the user, in projects they can still see."""
    issues = db.scalars(
        select(Issue)
        .join(BoardColumn, BoardColumn.id == Issue.column_id)
        .join(Project, Project.id == Issue.project_id)
        .where(
            Issue.type == IssueType.decision,
            Issue.assignee_id == user.id,
            BoardColumn.category != ColumnCategory.done,
            Project.archived.is_(False),
        )
        .order_by(Issue.due_date.is_(None), Issue.due_date, Issue.created_at)
    ).unique()
    visible = [
        i for i in issues if user.is_admin or projects.project_role(db, i.project, user)
    ]
    return serialize(db, visible)


# --- mutations ---------------------------------------------------------------


def create_issue(db: Session, access: ProjectAccess, data: IssueCreate) -> Issue:
    project = access.project
    if data.column_id is not None:
        column = projects.get_column(db, project, data.column_id)
    else:
        column = projects.list_columns(db, project)[0]
    assignee = (
        projects.ensure_assignable(db, project, data.assignee_id) if data.assignee_id else None
    )
    parent = _issue_in_project(db, project, data.parent_key, "Parent") if data.parent_key else None
    labels = _labels(db, project, data.label_ids)

    # Atomic counter bump so concurrent creates never share a number.
    number = db.execute(
        update(Project)
        .where(Project.id == project.id)
        .values(issue_counter=Project.issue_counter + 1)
        .returning(Project.issue_counter)
    ).scalar_one()
    project.issue_counter = number
    position = len(list(db.scalars(select(Issue.id).where(Issue.column_id == column.id))))

    issue = Issue(
        project=project,
        number=number,
        title=data.title,
        description=data.description,
        type=data.type,
        priority=data.priority,
        column=column,
        position=position,
        assignee=assignee,
        reporter=access.user,
        parent=parent,
        due_date=data.due_date,
        labels=labels,
    )
    db.add(issue)
    db.flush()
    activity.record(db, project=project, actor=access.user, action="issue_created", issue=issue,
                    details={"title": issue.title, "type": issue.type})
    db.commit()
    return issue


def _display(value: Any) -> Any:
    if isinstance(value, User):
        return value.name
    if isinstance(value, Issue):
        return value.key
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [label.name for label in value]
    return value


def update_issue(db: Session, issue: Issue, access: ProjectAccess, data: IssueUpdate) -> Issue:
    fields = data.model_fields_set
    if not access.has(ProjectRole.developer):
        allowed = (
            access.role == ProjectRole.client
            and issue.type == IssueType.decision
            and fields <= CLIENT_EDITABLE_FIELDS
        )
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")

    project = access.project
    new_values: dict[str, Any] = {}
    for field in fields:
        value = getattr(data, field)
        if field == "assignee_id":
            new_values["assignee"] = (
                projects.ensure_assignable(db, project, value) if value is not None else None
            )
        elif field == "parent_key":
            parent = _issue_in_project(db, project, value, "Parent") if value else None
            if parent is not None:
                _check_parent(issue, parent)
            new_values["parent"] = parent
        elif field == "label_ids":
            new_values["labels"] = _labels(db, project, value or [])
        elif field == "due_date":
            new_values["due_date"] = value
        elif value is not None:
            # Other fields are not nullable; null means "leave unchanged".
            new_values[field] = value

    changes: dict[str, dict[str, Any]] = {}
    for attr, value in new_values.items():
        old = getattr(issue, attr)
        if attr == "labels":
            if {lbl.id for lbl in old} == {lbl.id for lbl in value}:
                continue
            old = list(old)
        elif old == value:
            continue
        changes[attr] = {"from": _display(old), "to": _display(value)}
        setattr(issue, attr, value)

    if changes:
        # Long text diffs would bloat the log; record only that they changed.
        for text_field in ("description", "blocked_reason"):
            if text_field in changes:
                changes[text_field] = {}
        activity.record(db, project=project, actor=access.user, action="issue_updated",
                        issue=issue, details=changes)
    db.commit()
    db.refresh(issue)
    return issue


def _renumber(db: Session, column_id: int, ordered: list[Issue] | None = None) -> None:
    items = ordered if ordered is not None else list(
        db.scalars(
            select(Issue).where(Issue.column_id == column_id).order_by(Issue.position, Issue.id)
        )
    )
    for position, item in enumerate(items):
        item.position = position


def move_issue(
    db: Session, issue: Issue, access: ProjectAccess, column_id: int, index: int
) -> Issue:
    if not access.has(ProjectRole.developer) and not (
        access.role == ProjectRole.client and issue.type == IssueType.decision
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")
    target = projects.get_column(db, access.project, column_id)
    source = issue.column

    siblings = list(
        db.scalars(
            select(Issue)
            .where(Issue.column_id == target.id, Issue.id != issue.id)
            .order_by(Issue.position, Issue.id)
        )
    )
    siblings.insert(min(index, len(siblings)), issue)
    issue.column = target
    _renumber(db, target.id, siblings)
    db.flush()
    if source.id != target.id:
        _renumber(db, source.id)
        activity.record(db, project=access.project, actor=access.user, action="issue_moved",
                        issue=issue, details={"from": source.name, "to": target.name})
    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue: Issue, access: ProjectAccess) -> None:
    column_id = issue.column_id
    activity.record(db, project=access.project, actor=access.user, action="issue_deleted",
                    issue=issue, details={"title": issue.title})
    db.flush()
    db.delete(issue)
    db.flush()
    _renumber(db, column_id)
    db.commit()


# --- links -------------------------------------------------------------------


def add_link(
    db: Session, issue: Issue, access: ProjectAccess, link_type: LinkType, target_key: str
) -> IssueLink:
    target = _issue_in_project(db, access.project, target_key, "Linked issue")
    if target.id == issue.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot link an issue to itself")
    link = IssueLink(from_issue=issue, to_issue=target, type=link_type)
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Link already exists") from exc
    activity.record(db, project=access.project, actor=access.user, action="link_added",
                    issue=issue, details={"type": link_type, "target": target.key})
    db.commit()
    return link


def remove_link(db: Session, link_id: int, user: User) -> None:
    link = db.get(IssueLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    _, access = load_issue(db, link.from_issue.key, user, ProjectRole.developer)
    activity.record(db, project=access.project, actor=user, action="link_removed",
                    issue=link.from_issue, details={"type": link.type, "target": link.to_issue.key})
    db.delete(link)
    db.commit()


# --- comments ----------------------------------------------------------------


def list_comments(db: Session, issue: Issue) -> list[Comment]:
    return list(
        db.scalars(
            select(Comment).where(Comment.issue_id == issue.id).order_by(Comment.created_at,
                                                                         Comment.id)
        )
    )


def add_comment(db: Session, issue: Issue, access: ProjectAccess, body: str) -> Comment:
    comment = Comment(issue_id=issue.id, author=access.user, body=body)
    db.add(comment)
    activity.record(db, project=access.project, actor=access.user, action="comment_added",
                    issue=issue)
    db.commit()
    return comment


def _load_comment(db: Session, comment_id: int, user: User) -> tuple[Comment, ProjectAccess]:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    issue = db.get(Issue, comment.issue_id)
    assert issue is not None
    _, access = load_issue(db, issue.key, user, ProjectRole.client)
    return comment, access


def edit_comment(db: Session, comment_id: int, user: User, body: str) -> Comment:
    comment, _ = _load_comment(db, comment_id, user)
    if comment.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can edit a comment")
    comment.body = body
    db.commit()
    return comment


def delete_comment(db: Session, comment_id: int, user: User) -> None:
    comment, access = _load_comment(db, comment_id, user)
    if comment.author_id != user.id and not access.has(ProjectRole.owner):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author or an owner can delete")
    db.delete(comment)
    db.commit()


# --- summary -----------------------------------------------------------------


def project_summary(db: Session, project: Project, today: date) -> ProjectSummary:
    columns = projects.list_columns(db, project)
    issues = list(db.scalars(select(Issue).where(Issue.project_id == project.id)))
    blockers = open_blockers(db, [i.id for i in issues])
    per_column = Counter(i.column_id for i in issues)
    open_issues = [i for i in issues if not _is_done(i)]
    return ProjectSummary(
        total=len(issues),
        open=len(open_issues),
        blocked=sum(1 for i in open_issues if i.is_blocked or blockers.get(i.id)),
        overdue=sum(1 for i in open_issues if i.due_date and i.due_date < today),
        open_decisions=sum(1 for i in open_issues if i.type == IssueType.decision),
        by_column=[ColumnCount(column_id=c.id, name=c.name, count=per_column[c.id])
                   for c in columns],
        by_type=dict(Counter(i.type for i in open_issues)),
        recent_activity=[ActivityOut.model_validate(a)
                         for a in activity.list_for_project(db, project, 20)],
    )
