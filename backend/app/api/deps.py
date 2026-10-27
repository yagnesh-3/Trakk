"""Authentication and project-access dependencies shared by the routes."""

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_session_token, hash_api_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models import ApiToken, Project, ProjectMember, User
from app.models.enums import ROLE_RANK, ProjectRole

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def _user_from_token(db: Session, raw: str) -> User:
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw)))
    if token is None:
        raise _unauthorized()
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    now = utcnow()
    # Throttle the write; minute precision is plenty for "last used".
    if token.last_used_at is None or now - token.last_used_at > timedelta(minutes=1):
        token.last_used_at = now
        db.commit()
    return user


def _user_from_cookie(request: Request, db: Session) -> User:
    settings = get_settings()
    raw = request.cookies.get(settings.cookie_name)
    decoded = decode_session_token(raw) if raw else None
    if decoded is None:
        raise _unauthorized()
    user_id, session_version = decoded
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.session_version != session_version:
        raise _unauthorized()
    # Cookie auth is browser auth: reject cross-site writes (CSRF defence).
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")
    return user


def get_authenticated_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Any signed-in user, including one who still has to change their password."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        request.state.auth_method = "token"
        return _user_from_token(db, auth[7:].strip())
    request.state.auth_method = "cookie"
    return _user_from_cookie(request, db)


def get_current_user(user: User = Depends(get_authenticated_user)) -> User:
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password change required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_cookie_auth(request: Request, user: User = Depends(get_current_user)) -> User:
    """For actions an API token must not perform on its own (e.g. minting tokens)."""
    if getattr(request.state, "auth_method", None) != "cookie":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with a session to do this")
    return user


@dataclass
class ProjectAccess:
    project: Project
    user: User
    role: ProjectRole

    def has(self, role: ProjectRole) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


def project_role(db: Session, project: Project, user: User) -> ProjectRole | None:
    if user.is_admin:
        return ProjectRole.owner
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
        )
    )
    return ProjectRole(member.role) if member else None


def resolve_project_access(
    db: Session, project: Project | None, user: User, min_role: ProjectRole
) -> ProjectAccess:
    # Non-members get 404 so project keys don't leak.
    role = project_role(db, project, user) if project else None
    if project is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    access = ProjectAccess(project, user, role)
    if not access.has(min_role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")
    return access


def project_access(min_role: ProjectRole = ProjectRole.viewer):
    """Dependency factory for routes with a `{project_key}` path parameter."""

    def dependency(
        project_key: str,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> ProjectAccess:
        project = db.scalar(select(Project).where(Project.key == project_key.upper()))
        return resolve_project_access(db, project, user, min_role)

    return dependency
