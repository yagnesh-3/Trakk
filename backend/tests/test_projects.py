def test_create_project_defaults(team):
    admin = team["admin"]
    project = admin.get("/api/projects/APP").json()
    assert project["key"] == "APP"
    assert project["myRole"] == "owner"
    columns = admin.get("/api/projects/APP/columns").json()
    assert [c["name"] for c in columns] == ["Backlog", "To Do", "In Progress", "In Review", "Done"]
    assert columns[-1]["category"] == "done"


def test_project_key_validation_and_uniqueness(team):
    admin = team["admin"]
    assert admin.post("/api/projects", json={"key": "app", "name": "x"}).status_code == 422
    assert admin.post("/api/projects", json={"key": "APP", "name": "x"}).status_code == 409
    assert team["owner"].post("/api/projects", json={"key": "NEW", "name": "x"}).status_code == 403


def test_project_isolation(team):
    outsider = team["outsider"]
    assert outsider.get("/api/projects").json() == []
    assert outsider.get("/api/projects/APP").status_code == 404
    assert outsider.get("/api/projects/APP/issues").status_code == 404
    keys = [p["key"] for p in team["client"].get("/api/projects").json()]
    assert keys == ["APP"]
    assert team["client"].get("/api/projects/APP").json()["myRole"] == "client"


def test_user_list_limited_to_shared_projects(team):
    emails = {u["email"] for u in team["outsider"].get("/api/users").json()}
    assert emails == {"outsider@team.dev"}
    emails = {u["email"] for u in team["viewer"].get("/api/users").json()}
    assert "owner@team.dev" in emails
    assert "outsider@team.dev" not in emails


def test_member_management_requires_owner(team):
    ids = team["ids"]
    r = team["dev"].put("/api/projects/APP/members", json={"userId": ids["outsider"],
                                                           "role": "viewer"})
    assert r.status_code == 403
    r = team["owner"].put("/api/projects/APP/members", json={"userId": ids["outsider"],
                                                             "role": "viewer"})
    assert r.status_code == 200
    assert team["outsider"].get("/api/projects/APP").status_code == 200
    r = team["owner"].delete(f"/api/projects/APP/members/{ids['outsider']}")
    assert r.status_code == 204
    assert team["outsider"].get("/api/projects/APP").status_code == 404


def test_last_owner_protected(team):
    owner, ids = team["owner"], team["ids"]
    admin_id = ids["admin"]
    # The creating admin is also an owner; remove it so "owner" is the last one.
    assert owner.delete(f"/api/projects/APP/members/{admin_id}").status_code == 204
    r = owner.put("/api/projects/APP/members", json={"userId": ids["owner"], "role": "developer"})
    assert r.status_code == 409
    assert owner.delete(f"/api/projects/APP/members/{ids['owner']}").status_code == 409


def test_update_and_archive_project(team):
    owner = team["owner"]
    assert team["dev"].patch("/api/projects/APP", json={"name": "Nope"}).status_code == 403
    r = owner.patch("/api/projects/APP", json={"name": "App v2", "archived": True})
    assert r.json()["name"] == "App v2"
    assert owner.get("/api/projects").json() == []
    assert len(owner.get("/api/projects?include_archived=true").json()) == 1


def test_columns_crud_and_reorder(team):
    owner = team["owner"]
    r = owner.post("/api/projects/APP/columns", json={"name": "QA", "category": "in_progress",
                                                      "wipLimit": 3})
    assert r.status_code == 201
    qa = r.json()
    assert qa["position"] == 5
    ids = [c["id"] for c in owner.get("/api/projects/APP/columns").json()]
    new_order = [ids[-1], *ids[:-1]]
    r = owner.put("/api/projects/APP/columns/order", json={"columnIds": new_order})
    assert [c["id"] for c in r.json()] == new_order
    assert owner.put("/api/projects/APP/columns/order",
                     json={"columnIds": new_order[:-1]}).status_code == 422
    r = owner.patch(f"/api/projects/APP/columns/{qa['id']}", json={"wipLimit": None})
    assert r.json()["wipLimit"] is None

    issue = team["dev"].post("/api/projects/APP/issues",
                             json={"title": "x", "columnId": qa["id"]}).json()
    assert owner.delete(f"/api/projects/APP/columns/{qa['id']}").status_code == 409
    team["dev"].delete(f"/api/issues/{issue['key']}")
    assert owner.delete(f"/api/projects/APP/columns/{qa['id']}").status_code == 204
    assert team["dev"].post("/api/projects/APP/columns", json={"name": "X"}).status_code == 403


def test_labels(team):
    dev = team["dev"]
    r = dev.post("/api/projects/APP/labels", json={"name": "ui", "color": "#ff0000"})
    assert r.status_code == 201
    assert dev.post("/api/projects/APP/labels", json={"name": "ui"}).status_code == 409
    bad = dev.post("/api/projects/APP/labels", json={"name": "y", "color": "red"})
    assert bad.status_code == 422
    assert team["client"].post("/api/projects/APP/labels", json={"name": "z"}).status_code == 403
    label_id = r.json()["id"]
    assert dev.patch(f"/api/projects/APP/labels/{label_id}",
                     json={"name": "frontend"}).json()["name"] == "frontend"
    assert dev.delete(f"/api/projects/APP/labels/{label_id}").status_code == 204


def test_owner_adds_member_by_email(team):
    owner = team["owner"]
    r = owner.put("/api/projects/APP/members",
                  json={"email": "Outsider@Team.dev", "role": "client"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "outsider@team.dev"
    assert team["outsider"].get("/api/projects/APP").json()["myRole"] == "client"
    r = owner.put("/api/projects/APP/members", json={"email": "nobody@team.dev", "role": "viewer"})
    assert r.status_code == 404
    r = owner.put("/api/projects/APP/members",
                  json={"email": "outsider@team.dev", "userId": 1, "role": "viewer"})
    assert r.status_code == 422
    assert owner.put("/api/projects/APP/members", json={"role": "viewer"}).status_code == 422
