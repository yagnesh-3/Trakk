"""Users, passwords and API tokens."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import generate_api_token, hash_api_token, hash_password, verify_password
from app.models import ApiToken, ProjectMember, User
from app.models.enums import SystemRole
from app.schemas.user import ApiTokenCreated, UserCreate, UserUpdate


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if user is None:
        # Hash anyway so response time doesn't reveal which emails exist.
        verify_password(password, hash_password("timing-equaliser"))
        return None
    if not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, data: UserCreate, *, must_change_password: bool = True) -> User:
    if get_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(
        email=normalize_email(data.email),
        name=data.name.strip(),
        password_hash=hash_password(data.password),
        system_role=data.system_role,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.commit()
    return user


def list_visible_users(db: Session, viewer: User) -> list[User]:
    """Admins see everyone; others see people who share a project with them."""
    query = select(User).order_by(User.name)
    if not viewer.is_admin:
        my_projects = select(ProjectMember.project_id).where(ProjectMember.user_id == viewer.id)
        shared = select(ProjectMember.user_id).where(ProjectMember.project_id.in_(my_projects))
        query = query.where(User.id.in_(shared) | (User.id == viewer.id))
    return list(db.scalars(query))


def _active_admins(db: Session) -> int:
    return db.scalar(
        select(func.count()).where(User.system_role == SystemRole.admin, User.is_active.is_(True))
    ) or 0


def update_user(db: Session, user: User, data: UserUpdate, actor: User) -> User:
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    losing_admin = user.is_admin and (
        fields.get("system_role") == SystemRole.member or fields.get("is_active") is False
    )
    if losing_admin and _active_admins(db) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "At least one active admin is required")
    if user.id == actor.id and losing_admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot remove your own admin access")
    if "name" in fields:
        user.name = fields["name"].strip()
    if "system_role" in fields:
        user.system_role = fields["system_role"]
    if "is_active" in fields:
        user.is_active = fields["is_active"]
        if not user.is_active:
            user.session_version += 1
    if "password" in fields:
        user.password_hash = hash_password(fields["password"])
        user.must_change_password = True
        user.session_version += 1
    db.commit()
    return user


def change_password(db: Session, user: User, current: str, new: str) -> User:
    if not verify_password(current, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if current == new:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a different password")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.session_version += 1
    db.commit()
    return user


def list_tokens(db: Session, user: User) -> list[ApiToken]:
    return list(
        db.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id))
    )


def create_token(db: Session, user: User, name: str) -> ApiTokenCreated:
    raw = generate_api_token()
    token = ApiToken(
        user_id=user.id, name=name.strip(), token_hash=hash_api_token(raw), prefix=raw[:10]
    )
    db.add(token)
    db.commit()
    return ApiTokenCreated(
        id=token.id, name=token.name, prefix=token.prefix, created_at=token.created_at,
        last_used_at=None, token=raw,
    )


def delete_token(db: Session, user: User, token_id: int) -> None:
    token = db.get(ApiToken, token_id)
    if token is None or token.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    db.delete(token)
    db.commit()
