from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.auth import login_limiter
from app.db.base import Base
from app.db.session import get_db, make_engine
from app.main import app
from app.models import User
from app.models.enums import ProjectRole, SystemRole
from app.schemas.user import UserCreate
from app.services import users

PASSWORD = "correct-horse-battery"


@pytest.fixture
def session_factory(tmp_path) -> Iterator[sessionmaker[Session]]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    login_limiter.reset()
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def db(session_factory) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def make_user(db) -> Callable[..., User]:
    def _make(
        email: str,
        role: SystemRole = SystemRole.member,
        must_change: bool = False,
        name: str | None = None,
    ) -> User:
        return users.create_user(
            db,
            UserCreate(email=email, name=name or email.split("@")[0], password=PASSWORD,
                       system_role=role),
            must_change_password=must_change,
        )

    return _make


@pytest.fixture
def login(session_factory) -> Callable[[str], TestClient]:
    """Return a TestClient signed in as the given email (one cookie jar per client)."""

    def _login(email: str, password: str = PASSWORD) -> TestClient:
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return client

    return _login


@pytest.fixture
def anon(session_factory) -> TestClient:
    return TestClient(app)


@pytest.fixture
def team(make_user, login):
    """An admin-created project 'APP' with one member of each role, all signed in."""
    make_user("admin@team.dev", SystemRole.admin)
    make_user("owner@team.dev")
    make_user("dev@team.dev")
    make_user("client@team.dev")
    make_user("viewer@team.dev")
    make_user("outsider@team.dev")
    clients = {
        name: login(f"{name}@team.dev")
        for name in ("admin", "owner", "dev", "client", "viewer", "outsider")
    }
    assert clients["admin"].post(
        "/api/projects", json={"key": "APP", "name": "App"}
    ).status_code == 201
    ids = {u["email"].split("@")[0]: u["id"] for u in clients["admin"].get("/api/users").json()}
    for name, role in (
        ("owner", ProjectRole.owner),
        ("dev", ProjectRole.developer),
        ("client", ProjectRole.client),
        ("viewer", ProjectRole.viewer),
    ):
        r = clients["admin"].put(
            "/api/projects/APP/members", json={"userId": ids[name], "role": role}
        )
        assert r.status_code == 200, r.text
    clients["ids"] = ids
    return clients
