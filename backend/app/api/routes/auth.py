from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_authenticated_user
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import create_session_token
from app.db.session import get_db
from app.models import User
from app.schemas.user import ChangePasswordRequest, LoginRequest, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
login_limiter = RateLimiter(_settings.login_attempts, _settings.login_window_seconds)


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.cookie_name,
        create_session_token(user.id, user.session_version),
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(
    data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    client_ip = request.client.host if request.client else "unknown"
    if not login_limiter.hit(f"{client_ip}:{data.email.lower()}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try later")
    user = users.authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.cookie_name, path="/", secure=settings.cookie_secure, httponly=True,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_authenticated_user)) -> User:
    return user


@router.post("/change-password", response_model=UserOut)
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    user = users.change_password(db, user, data.current_password, data.new_password)
    # Other sessions are invalidated; keep this browser signed in.
    if getattr(request.state, "auth_method", None) == "cookie":
        _set_session_cookie(response, user)
    return user
