from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.cli import DEMO_PASSWORD, seed_demo
from app.db.base import Base
from app.main import app
from app.models import ApiToken, Issue


def test_api_token_lifecycle(team, db):
    dev = team["dev"]
    r = dev.post("/api/tokens", json={"name": "claude"})
    assert r.status_code == 201
    created = r.json()
    raw = created["token"]
    assert raw.startswith("pt_") and created["prefix"] == raw[:10]
    # Only the hash is stored.
    assert db.scalar(select(ApiToken.token_hash)) != raw
    assert "token" not in dev.get("/api/tokens").json()[0]

    bot = TestClient(app, headers={"Authorization": f"Bearer {raw}"})
    assert bot.get("/api/auth/me").json()["email"] == "dev@team.dev"
    r = bot.post("/api/projects/APP/issues", json={"title": "Made by Claude"})
    assert r.status_code == 201
    assert r.json()["reporter"]["email"] == "dev@team.dev"
    # A token cannot mint further tokens.
    assert bot.post("/api/tokens", json={"name": "x"}).status_code == 403
    assert dev.get("/api/tokens").json()[0]["lastUsedAt"] is not None

    assert dev.delete(f"/api/tokens/{created['id']}").status_code == 204
    assert bot.get("/api/auth/me").status_code == 401
    assert TestClient(app, headers={"Authorization": "Bearer pt_bogus"}).get(
        "/api/auth/me").status_code == 401


def test_token_of_other_user_cannot_be_deleted(team):
    token = team["dev"].post("/api/tokens", json={"name": "a"}).json()
    assert team["owner"].delete(f"/api/tokens/{token['id']}").status_code == 404


def test_seed_demo_is_idempotent(db, login):
    seed_demo(db)
    seed_demo(db)
    assert db.query(Issue).count() == 12
    client = login("client@demo.dev", DEMO_PASSWORD)
    keys = [i["key"] for i in client.get("/api/me/decisions").json()]
    assert keys == ["DEMO-5", "MOB-5"]
    blocked = client.get("/api/issues/DEMO-6").json()
    assert blocked["blockedBy"] == ["DEMO-5"]


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []
    command.downgrade(config, "base")
