from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_cookie_auth
from app.db.session import get_db
from app.models import ApiToken, User
from app.schemas.issue import IssueOut
from app.schemas.user import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import issues, users

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[User]:
    return users.list_visible_users(db, user)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> User:
    return users.create_user(db, data)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return users.update_user(db, target, data, admin)


@router.get("/me/decisions", response_model=list[IssueOut])
def my_decisions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[IssueOut]:
    return issues.list_my_decisions(db, user)


@router.get("/tokens", response_model=list[ApiTokenOut])
def list_tokens(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ApiToken]:
    return users.list_tokens(db, user)


@router.post("/tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(
    data: ApiTokenCreate, user: User = Depends(require_cookie_auth), db: Session = Depends(get_db)
) -> ApiTokenCreated:
    return users.create_token(db, user, data.name)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_token(
    token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    users.delete_token(db, user, token_id)
