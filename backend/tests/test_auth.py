from app.models.enums import SystemRole
from tests.conftest import PASSWORD


def test_health(anon):
    assert anon.get("/health").json() == {"status": "ok"}


def test_login_me_logout(make_user, login):
    make_user("Alice@Example.com", name="Alice")
    client = login("alice@example.com")
    me = client.get("/api/auth/me").json()
    assert me["email"] == "alice@example.com"
    assert me["systemRole"] == "member"
    assert "passwordHash" not in me
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_bad_credentials(make_user, anon):
    make_user("bob@example.com")
    r = anon.post("/api/auth/login", json={"email": "bob@example.com", "password": "nope"})
    assert r.status_code == 401
    r = anon.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert r.status_code == 401


def test_login_rate_limited(make_user, anon):
    make_user("carol@example.com")
    for _ in range(10):
        anon.post("/api/auth/login", json={"email": "carol@example.com", "password": "x"})
    r = anon.post("/api/auth/login", json={"email": "carol@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_unauthenticated_rejected(anon):
    assert anon.get("/api/projects").status_code == 401


def test_forced_password_change(make_user, login):
    make_user("new@example.com", must_change=True)
    client = login("new@example.com")
    assert client.get("/api/auth/me").json()["mustChangePassword"] is True
    assert client.get("/api/projects").status_code == 403
    r = client.post("/api/auth/change-password",
                    json={"currentPassword": "wrong-password", "newPassword": "brand-new-pass"})
    assert r.status_code == 400
    r = client.post("/api/auth/change-password",
                    json={"currentPassword": PASSWORD, "newPassword": "brand-new-pass"})
    assert r.status_code == 200
    assert r.json()["mustChangePassword"] is False
    # The re-issued cookie keeps this browser signed in.
    assert client.get("/api/projects").status_code == 200


def test_password_change_invalidates_other_sessions(make_user, login):
    make_user("dave@example.com")
    first = login("dave@example.com")
    second = login("dave@example.com")
    first.post("/api/auth/change-password",
               json={"currentPassword": PASSWORD, "newPassword": "another-password"})
    assert first.get("/api/auth/me").status_code == 200
    assert second.get("/api/auth/me").status_code == 401


def test_cross_origin_write_rejected(make_user, login):
    make_user("erin@example.com", SystemRole.admin)
    client = login("erin@example.com")
    r = client.post("/api/projects", json={"key": "EVIL", "name": "x"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/projects", json={"key": "GOOD", "name": "x"},
                    headers={"Origin": "http://localhost:5180"})
    assert r.status_code == 201


def test_admin_user_management(make_user, login):
    make_user("root@example.com", SystemRole.admin)
    make_user("member@example.com")
    admin = login("root@example.com")
    member = login("member@example.com")

    assert member.post("/api/users", json={"email": "x@example.com", "name": "X",
                                           "password": "long-enough-pw"}).status_code == 403
    r = admin.post("/api/users", json={"email": "Frank@Example.com", "name": "Frank",
                                       "password": "long-enough-pw"})
    assert r.status_code == 201
    frank = r.json()
    assert frank["email"] == "frank@example.com"
    assert frank["mustChangePassword"] is True
    assert admin.post("/api/users", json={"email": "frank@example.com", "name": "F",
                                          "password": "long-enough-pw"}).status_code == 409

    r = admin.patch(f"/api/users/{frank['id']}", json={"isActive": False})
    assert r.json()["isActive"] is False
    r = admin.post("/api/auth/login", json={"email": "frank@example.com",
                                            "password": "long-enough-pw"})
    assert r.status_code == 401

    root_id = admin.get("/api/auth/me").json()["id"]
    r = admin.patch(f"/api/users/{root_id}", json={"systemRole": "member"})
    assert r.status_code == 409


def test_timestamps_are_utc_aware(make_user, login):
    make_user("tz@example.com")
    created = login("tz@example.com").get("/api/auth/me").json()["createdAt"]
    assert created.endswith(("Z", "+00:00"))
