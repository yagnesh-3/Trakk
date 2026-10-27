"""Run the MCP tools against the real backend app in-process (SQLite, demo seed data)."""

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.api.routes.auth import login_limiter  # noqa: E402
from app.cli import seed_demo  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import users  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from mcp import Client  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from tracker_mcp.client import TrackerClient  # noqa: E402
from tracker_mcp.server import build_server  # noqa: E402


@pytest.fixture
def db_factory(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'mcp.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    login_limiter.reset()
    with factory() as db:
        seed_demo(db)
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


def make_token(factory, email: str) -> str:
    with factory() as db:
        user = users.get_by_email(db, email)
        assert user is not None
        return users.create_token(db, user, "test").token


class Tools:
    """Calls MCP tools through a real MCP client connected in-process."""

    def __init__(self, server) -> None:
        self.server = server

    def call(self, name: str, **arguments: Any) -> Any:
        result = self.raw(name, **arguments)
        assert not result.is_error, result.content
        data = result.structured_content
        # Non-object return values are wrapped as {"result": ...}.
        if isinstance(data, dict) and set(data) == {"result"}:
            return data["result"]
        return data

    def error(self, name: str, **arguments: Any) -> str:
        result = self.raw(name, **arguments)
        assert result.is_error, result.structured_content
        return " ".join(getattr(c, "text", "") for c in result.content)

    def raw(self, name: str, **arguments: Any):
        async def run():
            async with Client(self.server) as client:
                return await client.call_tool(name, arguments)

        return asyncio.run(run())


def tools_for(factory, email: str) -> Tools:
    token = make_token(factory, email)
    client = TrackerClient("http://testserver", token, http=TestClient(app))
    return Tools(build_server(client, web_url="http://web.test"))


@pytest.fixture
def dev(db_factory) -> Tools:
    return tools_for(db_factory, "dev@demo.dev")


@pytest.fixture
def client_user(db_factory) -> Tools:
    return tools_for(db_factory, "client@demo.dev")
