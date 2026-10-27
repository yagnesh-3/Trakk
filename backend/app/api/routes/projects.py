from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import ProjectAccess, get_current_user, project_access, require_admin
from app.db.session import get_db
from app.models import Activity, BoardColumn, Label, ProjectMember, User
from app.models.enums import ProjectRole
from app.schemas.issue import ActivityOut
from app.schemas.project import (
    ColumnCreate,
    ColumnOrder,
    ColumnOut,
    ColumnUpdate,
    LabelCreate,
    LabelOut,
    LabelUpdate,
    MemberOut,
    MemberUpsert,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from app.services import activity, projects, users

router = APIRouter(prefix="/projects", tags=["projects"])

viewer = project_access(ProjectRole.viewer)
owner = project_access(ProjectRole.owner)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    return projects.list_projects(db, user, include_archived)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> ProjectOut:
    return projects.to_out(projects.create_project(db, data, admin), ProjectRole.owner)


@router.get("/{project_key}", response_model=ProjectOut)
def get_project(access: ProjectAccess = Depends(viewer)) -> ProjectOut:
    return projects.to_out(access.project, access.role)


@router.patch("/{project_key}", response_model=ProjectOut)
def update_project(
    data: ProjectUpdate, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> ProjectOut:
    return projects.to_out(projects.update_project(db, access.project, data, access.user),
                           access.role)


@router.get("/{project_key}/activity", response_model=list[ActivityOut])
def project_activity(
    limit: int = 50, access: ProjectAccess = Depends(viewer), db: Session = Depends(get_db)
) -> list[Activity]:
    return activity.list_for_project(db, access.project, min(max(limit, 1), 200))


# --- members -----------------------------------------------------------------


@router.get("/{project_key}/members", response_model=list[MemberOut])
def list_members(
    access: ProjectAccess = Depends(viewer), db: Session = Depends(get_db)
) -> list[ProjectMember]:
    return projects.list_members(db, access.project)


@router.put("/{project_key}/members", response_model=MemberOut)
def upsert_member(
    data: MemberUpsert, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> ProjectMember:
    user_id = data.user_id
    if data.email is not None:
        user = users.get_by_email(db, data.email)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active user with that email")
        user_id = user.id
    assert user_id is not None
    return projects.upsert_member(db, access.project, user_id, data.role, access.user)


@router.delete("/{project_key}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> None:
    projects.remove_member(db, access.project, user_id, access.user)


# --- columns -----------------------------------------------------------------


@router.get("/{project_key}/columns", response_model=list[ColumnOut])
def list_columns(
    access: ProjectAccess = Depends(viewer), db: Session = Depends(get_db)
) -> list[BoardColumn]:
    return projects.list_columns(db, access.project)


@router.post("/{project_key}/columns", response_model=ColumnOut,
             status_code=status.HTTP_201_CREATED)
def create_column(
    data: ColumnCreate, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> BoardColumn:
    return projects.create_column(db, access.project, data)


@router.put("/{project_key}/columns/order", response_model=list[ColumnOut])
def reorder_columns(
    data: ColumnOrder, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> list[BoardColumn]:
    return projects.reorder_columns(db, access.project, data.column_ids)


@router.patch("/{project_key}/columns/{column_id}", response_model=ColumnOut)
def update_column(
    column_id: int,
    data: ColumnUpdate,
    access: ProjectAccess = Depends(owner),
    db: Session = Depends(get_db),
) -> BoardColumn:
    return projects.update_column(db, projects.get_column(db, access.project, column_id), data)


@router.delete("/{project_key}/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column_id: int, access: ProjectAccess = Depends(owner), db: Session = Depends(get_db)
) -> None:
    projects.delete_column(db, access.project, projects.get_column(db, access.project, column_id))


# --- labels ------------------------------------------------------------------

developer = project_access(ProjectRole.developer)


@router.get("/{project_key}/labels", response_model=list[LabelOut])
def list_labels(
    access: ProjectAccess = Depends(viewer), db: Session = Depends(get_db)
) -> list[Label]:
    return projects.list_labels(db, access.project)


@router.post("/{project_key}/labels", response_model=LabelOut,
             status_code=status.HTTP_201_CREATED)
def create_label(
    data: LabelCreate, access: ProjectAccess = Depends(developer), db: Session = Depends(get_db)
) -> Label:
    return projects.create_label(db, access.project, data)


@router.patch("/{project_key}/labels/{label_id}", response_model=LabelOut)
def update_label(
    label_id: int,
    data: LabelUpdate,
    access: ProjectAccess = Depends(developer),
    db: Session = Depends(get_db),
) -> Label:
    return projects.update_label(db, projects.get_label(db, access.project, label_id), data)


@router.delete("/{project_key}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: int, access: ProjectAccess = Depends(developer), db: Session = Depends(get_db)
) -> None:
    db.delete(projects.get_label(db, access.project, label_id))
    db.commit()
