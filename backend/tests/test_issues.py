import pytest


def columns(client):
    return client.get("/api/projects/APP/columns").json()


def create(client, **body):
    body.setdefault("title", "Something")
    r = client.post("/api/projects/APP/issues", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_issue_keys_are_sequential(team):
    dev = team["dev"]
    keys = [create(dev, title=f"Issue {n}")["key"] for n in range(3)]
    assert keys == ["APP-1", "APP-2", "APP-3"]
    dev.delete("/api/issues/APP-3")
    # Numbers are never reused.
    assert create(dev)["key"] == "APP-4"


def test_create_defaults_and_fields(team):
    dev, ids = team["dev"], team["ids"]
    label = dev.post("/api/projects/APP/labels", json={"name": "api"}).json()
    issue = create(dev, title="Build API", type="story", priority="high",
                   assigneeId=ids["client"], labelIds=[label["id"]], dueDate="2026-12-01")
    assert issue["columnId"] == columns(dev)[0]["id"]
    assert issue["position"] == 0
    assert issue["assignee"]["id"] == ids["client"]
    assert issue["reporter"]["email"] == "dev@team.dev"
    assert [lbl["name"] for lbl in issue["labels"]] == ["api"]
    assert issue["blocked"] is False and issue["done"] is False

    r = dev.post("/api/projects/APP/issues", json={"title": "x", "assigneeId": ids["outsider"]})
    assert r.status_code == 422
    r = dev.post("/api/projects/APP/issues", json={"title": "x", "labelIds": [999]})
    assert r.status_code == 422
    r = dev.post("/api/projects/APP/issues", json={"title": "x", "type": "saga"})
    assert r.status_code == 422


def test_role_permissions_on_issues(team):
    create(team["dev"], title="Task")
    decision = create(team["dev"], title="Pick a vendor", type="decision")
    assert team["viewer"].get("/api/issues/APP-1").status_code == 200
    assert team["viewer"].post("/api/projects/APP/issues", json={"title": "x"}).status_code == 403
    assert team["client"].post("/api/projects/APP/issues", json={"title": "x"}).status_code == 403
    assert team["outsider"].get("/api/issues/APP-1").status_code == 404

    # Clients may only edit decision descriptions and move decisions.
    assert team["client"].patch("/api/issues/APP-1", json={"description": "x"}).status_code == 403
    assert team["client"].patch(f"/api/issues/{decision['key']}",
                                json={"title": "x"}).status_code == 403
    r = team["client"].patch(f"/api/issues/{decision['key']}",
                             json={"description": "Go with vendor B"})
    assert r.status_code == 200
    done = columns(team["dev"])[-1]["id"]
    assert team["client"].post("/api/issues/APP-1/move",
                               json={"columnId": done, "index": 0}).status_code == 403
    assert team["client"].post(f"/api/issues/{decision['key']}/move",
                               json={"columnId": done, "index": 0}).status_code == 200
    assert team["viewer"].post(f"/api/issues/{decision['key']}/move",
                               json={"columnId": done, "index": 0}).status_code == 403
    assert team["client"].delete("/api/issues/APP-1").status_code == 403


def test_update_records_activity(team):
    dev, ids = team["dev"], team["ids"]
    create(dev, title="Old title")
    r = dev.patch("/api/issues/APP-1", json={"title": "New title", "assigneeId": ids["dev"],
                                             "description": "long text"})
    assert r.status_code == 200
    assert r.json()["title"] == "New title"
    r = dev.patch("/api/issues/APP-1", json={"assigneeId": None})
    assert r.json()["assignee"] is None
    history = dev.get("/api/issues/APP-1/activity").json()
    assert [h["action"] for h in history] == ["issue_created", "issue_updated", "issue_updated"]
    first = history[1]["details"]
    assert first["title"] == {"from": "Old title", "to": "New title"}
    assert first["assignee"] == {"from": None, "to": "dev"}
    assert first["description"] == {}
    assert history[1]["actor"]["email"] == "dev@team.dev"


def test_parent_child_and_cycle(team):
    dev = team["dev"]
    epic = create(dev, title="Epic", type="epic")
    child = create(dev, title="Child", parentKey=epic["key"])
    assert child["parentKey"] == epic["key"]
    detail = dev.get(f"/api/issues/{epic['key']}").json()
    assert [c["key"] for c in detail["children"]] == [child["key"]]
    r = dev.patch(f"/api/issues/{epic['key']}", json={"parentKey": child["key"]})
    assert r.status_code == 422
    r = dev.patch(f"/api/issues/{epic['key']}", json={"parentKey": epic["key"]})
    assert r.status_code == 422
    assert dev.post("/api/projects/APP/issues",
                    json={"title": "x", "parentKey": "OTHER-1"}).status_code == 422
    listed = dev.get(f"/api/projects/APP/issues?parent={epic['key']}").json()
    assert [i["key"] for i in listed] == [child["key"]]


def test_move_and_reorder(team):
    dev = team["dev"]
    cols = columns(dev)
    backlog, todo = cols[0]["id"], cols[1]["id"]
    a, b, c = (create(dev, title=t)["key"] for t in "ABC")

    def order(col):
        issues = dev.get(f"/api/projects/APP/issues?columnId={col}").json()
        return [(i["key"], i["position"]) for i in issues]

    assert order(backlog) == [(a, 0), (b, 1), (c, 2)]
    dev.post(f"/api/issues/{c}/move", json={"columnId": backlog, "index": 0})
    assert order(backlog) == [(c, 0), (a, 1), (b, 2)]
    r = dev.post(f"/api/issues/{a}/move", json={"columnId": todo, "index": 99})
    assert r.json()["columnId"] == todo
    assert order(todo) == [(a, 0)]
    assert order(backlog) == [(c, 0), (b, 1)]
    history = dev.get(f"/api/issues/{a}/activity").json()
    assert history[-1]["details"] == {"from": "Backlog", "to": "To Do"}
    assert dev.post(f"/api/issues/{a}/move",
                    json={"columnId": 9999, "index": 0}).status_code == 404


def test_decision_blocks_until_done(team):
    dev, ids = team["dev"], team["ids"]
    decision = create(dev, title="Choose DB", type="decision", assigneeId=ids["client"])
    work = create(dev, title="Build schema")
    r = dev.post(f"/api/issues/{decision['key']}/links",
                 json={"type": "blocks", "targetKey": work["key"]})
    assert r.status_code == 201
    assert r.json()["links"][0]["direction"] == "outward"
    assert dev.post(f"/api/issues/{decision['key']}/links",
                    json={"type": "blocks", "targetKey": work["key"]}).status_code == 409
    assert dev.post(f"/api/issues/{work['key']}/links",
                    json={"type": "blocks", "targetKey": work["key"]}).status_code == 422

    blocked = dev.get(f"/api/issues/{work['key']}").json()
    assert blocked["blocked"] is True
    assert blocked["blockedBy"] == [decision["key"]]
    assert blocked["links"][0]["direction"] == "inward"
    listed = dev.get("/api/projects/APP/issues?blocked=true").json()
    assert [i["key"] for i in listed] == [work["key"]]

    mine = team["client"].get("/api/me/decisions").json()
    assert [i["key"] for i in mine] == [decision["key"]]
    summary = dev.get("/api/projects/APP/summary").json()
    assert summary["blocked"] == 1 and summary["openDecisions"] == 1

    done = columns(dev)[-1]["id"]
    team["client"].post(f"/api/issues/{decision['key']}/move", json={"columnId": done, "index": 0})
    unblocked = dev.get(f"/api/issues/{work['key']}").json()
    assert unblocked["blocked"] is False and unblocked["blockedBy"] == []
    assert team["client"].get("/api/me/decisions").json() == []


def test_manual_blocked_flag_and_unlink(team):
    dev = team["dev"]
    a, b = create(dev, title="A"), create(dev, title="B")
    r = dev.patch(f"/api/issues/{a['key']}", json={"isBlocked": True,
                                                   "blockedReason": "waiting on design"})
    assert r.json()["blocked"] is True
    link = dev.post(f"/api/issues/{a['key']}/links",
                    json={"type": "blocks", "targetKey": b["key"]}).json()["links"][0]
    assert team["client"].delete(f"/api/links/{link['id']}").status_code == 403
    assert dev.delete(f"/api/links/{link['id']}").status_code == 204
    assert dev.get(f"/api/issues/{b['key']}").json()["blocked"] is False


def test_filters(team):
    dev, ids = team["dev"], team["ids"]
    label = dev.post("/api/projects/APP/labels", json={"name": "ui"}).json()
    create(dev, title="Fix login button", type="bug", assigneeId=ids["dev"],
           labelIds=[label["id"]], priority="high")
    create(dev, title="Write docs", type="task")

    def keys(query):
        return [i["key"] for i in dev.get(f"/api/projects/APP/issues?{query}").json()]

    assert keys("q=login") == ["APP-1"]
    assert keys("q=APP-2") == ["APP-2"]
    assert keys("q=2") == ["APP-2"]
    assert keys("type=bug") == ["APP-1"]
    assert keys("type=bug&type=task") == ["APP-1", "APP-2"]
    assert keys("assignee=me") == ["APP-1"]
    assert keys("assignee=none") == ["APP-2"]
    assert keys(f"labelId={label['id']}") == ["APP-1"]
    assert keys("priority=high") == ["APP-1"]


def test_comments(team):
    dev = team["dev"]
    create(dev)
    r = team["client"].post("/api/issues/APP-1/comments", json={"body": "Looks good"})
    assert r.status_code == 201
    comment = r.json()
    assert team["viewer"].post("/api/issues/APP-1/comments",
                               json={"body": "hi"}).status_code == 403
    assert dev.patch(f"/api/comments/{comment['id']}", json={"body": "x"}).status_code == 403
    r = team["client"].patch(f"/api/comments/{comment['id']}", json={"body": "Looks great"})
    assert r.json()["body"] == "Looks great"
    assert len(team["viewer"].get("/api/issues/APP-1/comments").json()) == 1
    assert dev.delete(f"/api/comments/{comment['id']}").status_code == 403
    assert team["owner"].delete(f"/api/comments/{comment['id']}").status_code == 204
    assert team["outsider"].get("/api/issues/APP-1/comments").status_code == 404


def test_delete_issue_keeps_history(team):
    dev = team["dev"]
    a, b = create(dev, title="A"), create(dev, title="B")
    assert dev.delete(f"/api/issues/{a['key']}").status_code == 204
    assert dev.get(f"/api/issues/{a['key']}").status_code == 404
    assert dev.get(f"/api/issues/{b['key']}").json()["position"] == 0
    actions = [(x["action"], x["issueKey"]) for x in dev.get("/api/projects/APP/activity").json()]
    assert ("issue_deleted", a["key"]) in actions


def test_summary(team):
    dev = team["dev"]
    create(dev, title="late", dueDate="2000-01-01")
    create(dev, title="decide", type="decision")
    summary = dev.get("/api/projects/APP/summary").json()
    assert summary["total"] == 2 and summary["open"] == 2
    assert summary["overdue"] == 1
    assert summary["byType"] == {"task": 1, "decision": 1}
    assert summary["byColumn"][0]["count"] == 2
    assert summary["recentActivity"][0]["action"] == "issue_created"


@pytest.mark.parametrize("key", ["APP", "APP-", "APP-x", "-1", "NOPE-1", "APP-999"])
def test_bad_issue_keys(team, key):
    assert team["dev"].get(f"/api/issues/{key}").status_code == 404
