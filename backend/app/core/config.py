"""Application settings, read from environment variables (and a local .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-in-production"


class Settings(BaseSettings):
    # Resolved from the backend folder so the API works from any working directory.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'tracker.db').as_posix()}"

    jwt_secret: str = DEV_JWT_SECRET
    session_hours: int = 12
    cookie_name: str = "pt_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # Comma-separated list of browser origins allowed to call the API.
    frontend_origin: str = "http://localhost:5180"

    login_attempts: int = 10
    login_window_seconds: int = 300

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong value in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
