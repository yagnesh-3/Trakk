"""Projects, members, columns and labels."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import project_role
from app.models import BoardColumn, Issue, Label, Project, ProjectMember, User
from app.models.enums import DEFAULT_COLUMNS, ProjectRole
from app.schemas.project import (
    ColumnCreate,
    ColumnUpdate,
    LabelCreate,
    LabelUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from app.services import activity


def to_out(project: Project, role: ProjectRole) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        archived=project.archived,
        created_at=project.created_at,
        my_role=role,
    )


def list_projects(db: Session, user: User, include_archived: bool) -> list[ProjectOut]:
    query = select(Project).order_by(Project.name)
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    if user.is_admin:
        return [to_out(p, ProjectRole.owner) for p in db.scalars(query)]
    rows = db.execute(
        query.add_columns(ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
    )
    return [to_out(p, ProjectRole(role)) for p, role in rows]


def create_project(db: Session, data: ProjectCreate, creator: User) -> Project:
    if db.scalar(select(Project).where(Project.key == data.key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Project key already in use")
    project = Project(key=data.key, name=data.name, description=data.description)
    db.add(project)
    db.flush()
    for position, (name, category) in enumerate(DEFAULT_COLUMNS):
        db.add(BoardColumn(project_id=project.id, name=name, position=position, category=category))
    db.add(ProjectMember(project_id=project.id, user_id=creator.id, role=ProjectRole.owner))
    activity.record(db, project=project, actor=creator, action="project_created")
    db.commit()
    return project


def update_project(db: Session, project: Project, data: ProjectUpdate, actor: User) -> Project:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(project, field, value)
    if changes:
        activity.record(db, project=project, actor=actor, action="project_updated",
                        details={"fields": sorted(changes)})
    db.commit()
    return project


# --- members -----------------------------------------------------------------


def list_members(db: Session, project: Project) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project.id)
            .order_by(User.name)
        )
    )


def _owner_count(db: Session, project: Project) -> int:
    return db.scalar(
        select(func.count()).where(
            ProjectMember.project_id == project.id, ProjectMember.role == ProjectRole.owner
        )
    ) or 0


def upsert_member(
    db: Session, project: Project, user_id: int, role: ProjectRole, actor: User
) -> ProjectMember:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
        )
    )
    if member is None:
        member = ProjectMember(project_id=project.id, user_id=user_id, role=role, user=user)
        db.add(member)
    else:
        if (
            member.role == ProjectRole.owner
            and role != ProjectRole.owner
            and _owner_count(db, project) <= 1
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "A project needs at least one owner")
        member.role = role
    activity.record(db, project=project, actor=actor, action="member_set",
                    details={"user": user.name, "role": role})
    db.commit()
    return member


def remove_member(db: Session, project: Project, user_id: int, actor: User) -> None:
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if member.role == ProjectRole.owner and _owner_count(db, project) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "A project needs at least one owner")
    activity.record(db, project=project, actor=actor, action="member_removed",
                    details={"user": member.user.name})
    db.delete(member)
    db.commit()


def ensure_assignable(db: Session, project: Project, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active or project_role(db, project, user) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Assignee must be a member of the project"
        )
    return user


# --- columns -----------------------------------------------------------------


def list_columns(db: Session, project: Project) -> list[BoardColumn]:
    return list(
        db.scalars(
            select(BoardColumn)
            .where(BoardColumn.project_id == project.id)
            .order_by(BoardColumn.position, BoardColumn.id)
        )
    )


def get_column(db: Session, project: Project, column_id: int) -> BoardColumn:
    column = db.get(BoardColumn, column_id)
    if column is None or column.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")
    return column


def create_column(db: Session, project: Project, data: ColumnCreate) -> BoardColumn:
    position = len(list_columns(db, project))
    column = BoardColumn(project_id=project.id, position=position, **data.model_dump())
    db.add(column)
    db.commit()
    return column


def update_column(db: Session, column: BoardColumn, data: ColumnUpdate) -> BoardColumn:
    fields = data.model_dump(exclude_unset=True)
    for field, value in fields.items():
        # wipLimit may be cleared with null; other fields ignore null.
        if value is not None or field == "wip_limit":
            setattr(column, field, value)
    db.commit()
    return column


def delete_column(db: Session, project: Project, column: BoardColumn) -> None:
    if db.scalar(select(func.count()).where(Issue.column_id == column.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Move the column's issues out first")
    if len(list_columns(db, project)) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "A board needs at least one column")
    db.delete(column)
    db.flush()
    for position, col in enumerate(list_columns(db, project)):
        col.position = position
    db.commit()


def reorder_columns(db: Session, project: Project, column_ids: list[int]) -> list[BoardColumn]:
    columns = {c.id: c for c in list_columns(db, project)}
    if sorted(column_ids) != sorted(columns):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "columnIds must list every column exactly once"
        )
    for position, column_id in enumerate(column_ids):
        columns[column_id].position = position
    db.commit()
    return list_columns(db, project)


# --- labels ------------------------------------------------------------------


def list_labels(db: Session, project: Project) -> list[Label]:
    return list(
        db.scalars(select(Label).where(Label.project_id == project.id).order_by(Label.name))
    )


def get_label(db: Session, project: Project, label_id: int) -> Label:
    label = db.get(Label, label_id)
    if label is None or label.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Label not found")
    return label


def _commit_label(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Label name already exists") from exc


def create_label(db: Session, project: Project, data: LabelCreate) -> Label:
    label = Label(project_id=project.id, **data.model_dump())
    db.add(label)
    _commit_label(db)
    return label


def update_label(db: Session, label: Label, data: LabelUpdate) -> Label:
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(label, field, value)
    _commit_label(db)
    return label
