import pytest
from fastapi.testclient import TestClient

from app.cli import ensure_admin
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services import users

from .conftest import PASSWORD


@pytest.fixture
def admin_env(monkeypatch):
    def _set(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def test_ensure_admin_creates_once_and_never_overwrites(db, admin_env, login):
    admin_env(ADMIN_EMAIL="Boss@Company.com", ADMIN_NAME="Boss",
              ADMIN_PASSWORD="initial-password-1")
    assert ensure_admin(db).startswith("Created admin boss@company.com")
    user = users.get_by_email(db, "boss@company.com")
    assert user.system_role == "admin" and user.must_change_password

    client = login("boss@company.com", "initial-password-1")
    assert client.get("/api/projects").status_code == 403  # must change password first
    r = client.post("/api/auth/change-password",
                    json={"currentPassword": "initial-password-1", "newPassword": PASSWORD})
    assert r.status_code == 200

    # A redeploy keeps the password the admin chose.
    assert "already exists" in ensure_admin(db)
    login("boss@company.com", PASSWORD)


def test_ensure_admin_needs_config(db, admin_env):
    admin_env(ADMIN_EMAIL="")
    assert "not set" in ensure_admin(db)
    admin_env(ADMIN_EMAIL="boss@company.com", ADMIN_PASSWORD="short")
    with pytest.raises(ValueError):
        ensure_admin(db)


@pytest.mark.parametrize("url", ["postgres://u:p@h/db", "postgresql://u:p@h/db"])
def test_database_url_uses_psycopg3(url):
    assert Settings(database_url=url).database_url == "postgresql+psycopg://u:p@h/db"


def test_serves_built_frontend(tmp_path, admin_env):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    admin_env(STATIC_DIR=str(tmp_path))
    client = TestClient(create_app())

    r = client.get("/assets/app-123.js")
    assert r.text == "console.log(1)" and "immutable" in r.headers["cache-control"]
    assert client.get("/p/DEMO/list").text == "<div id=root></div>"  # client-side route
    assert client.get("/../secret").text == "<div id=root></div>"
    assert client.get("/api/nope").status_code == 404
    assert client.get("/health").json() == {"status": "ok"}


def test_same_origin_writes_allowed(team):
    owner = team["owner"]
    owner.headers["origin"] = "https://tracker.example.com"
    assert owner.post("/api/projects/APP/issues", json={"title": "x"}).status_code == 403
    owner.headers["host"] = "tracker.example.com"
    assert owner.post("/api/projects/APP/issues", json={"title": "x"}).status_code == 201
