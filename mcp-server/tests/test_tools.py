import asyncio

from fastapi.testclient import TestClient
from mcp import Client

from tracker_mcp.client import TrackerClient
from tracker_mcp.server import build_server

from .conftest import Tools, app


def test_lists_tools_with_annotations(dev):
    async def run():
        async with Client(dev.server) as client:
            return await client.list_tools()

    tools = {t.name: t for t in asyncio.run(run()).tools}
    assert set(tools) == {
        "list_projects", "get_project", "search_issues", "get_issue", "create_issue",
        "update_issue", "move_issue", "add_comment", "link_issues", "my_open_decisions",
    }
    assert tools["get_issue"].annotations.read_only_hint is True
    assert tools["move_issue"].annotations.read_only_hint is False
    assert "status" in tools["move_issue"].input_schema["properties"]


def test_list_and_get_project(dev):
    projects = dev.call("list_projects")
    assert [(p["key"], p["role"]) for p in projects] == [("MOB", "developer"), ("DEMO", "developer")]
    project = dev.call("get_project", project="demo")
    assert [c["name"] for c in project["columns"]] == ["Backlog", "To Do", "In Progress", "In Review", "Done"]
    assert project["columns"][4]["category"] == "done"
    assert {m["email"] for m in project["members"]} >= {"dev@demo.dev", "client@demo.dev"}
    assert project["labels"] == ["backend", "frontend"]
    assert project["open_decisions"] == 1


def test_search_issues(dev):
    result = dev.call("search_issues", project="DEMO", status="in progress")
    assert [i["key"] for i in result["issues"]] == ["DEMO-2"]
    issue = result["issues"][0]
    assert issue["status"] == "In Progress"
    assert issue["assignee"] == "dev@demo.dev"
    assert issue["parent"] == "DEMO-1"
    assert issue["url"] == "http://web.test/p/DEMO?issue=DEMO-2"

    blocked = dev.call("search_issues", project="DEMO", blocked=True)["issues"]
    assert [(i["key"], i["blocked_by"]) for i in blocked] == [("DEMO-6", ["DEMO-5"])]
    assert [i["key"] for i in dev.call("search_issues", project="DEMO", label="backend")["issues"]] == [
        "DEMO-4", "DEMO-3",
    ]
    assert [i["key"] for i in dev.call("search_issues", project="DEMO", assignee="me")["issues"]] == [
        "DEMO-2", "DEMO-3",
    ]
    open_only = dev.call("search_issues", project="DEMO", include_done=False)
    assert "DEMO-3" not in [i["key"] for i in open_only["issues"]]
    limited = dev.call("search_issues", project="DEMO", limit=2)
    assert limited["total"] == 6 and len(limited["issues"]) == 2 and limited["truncated"] is True


def test_get_issue_includes_links_and_comments(dev):
    detail = dev.call("get_issue", key="demo-6")
    assert detail["blocked"] is True
    relations = {(link["relation"], link["key"]) for link in detail["links"]}
    assert relations == {("is blocked by", "DEMO-5"), ("relates to", "DEMO-3")}
    assert detail["comments"] == []
    epic = dev.call("get_issue", key="DEMO-1", include_comments=False)
    assert [c["key"] for c in epic["children"]] == ["DEMO-2", "DEMO-3"]
    assert "comments" not in epic


def test_create_update_move_comment_flow(dev):
    created = dev.call(
        "create_issue",
        project="DEMO",
        title="Add rate limiting",
        description="Protect the login endpoint.",
        type="story",
        priority="high",
        status="To Do",
        assignee="me",
        parent="DEMO-1",
        labels=["backend"],
        due_date="2030-01-31",
    )
    key = created["key"]
    assert key == "DEMO-7"
    assert created["status"] == "To Do"
    assert created["assignee"] == "dev@demo.dev"
    assert created["labels"] == ["backend"]
    assert created["parent"] == "DEMO-1"

    updated = dev.call("update_issue", key=key, priority="highest", labels=["backend", "frontend"],
                       assignee="client@demo.dev")
    assert updated["priority"] == "highest"
    assert updated["labels"] == ["backend", "frontend"]
    assert updated["assignee"] == "client@demo.dev"
    cleared = dev.call("update_issue", key=key, assignee="none", due_date="none", parent="none")
    assert cleared["assignee"] is None and "due_date" not in cleared and "parent" not in cleared

    moved = dev.call("move_issue", key=key, status="in review", position="top")
    assert moved["status"] == "In Review"
    comment = dev.call("add_comment", key=key, body="Implemented in branch feat/rate-limit.")
    assert comment["author"] == "dev@demo.dev"
    detail = dev.call("get_issue", key=key)
    assert detail["comments"][0]["body"] == "Implemented in branch feat/rate-limit."
    assert detail["description"] == "Protect the login endpoint."


def test_decision_flow_unblocks(dev, client_user):
    decisions = client_user.call("my_open_decisions")
    assert [d["key"] for d in decisions] == ["DEMO-5", "MOB-5"]
    client_user.call("add_comment", key="DEMO-5", body="Use Postmark.")
    client_user.call("move_issue", key="DEMO-5", status="Done")
    assert dev.call("get_issue", key="DEMO-6", include_comments=False).get("blocked") is None
    assert [d["key"] for d in client_user.call("my_open_decisions")] == ["MOB-5"]


def test_link_issues(dev):
    detail = dev.call("link_issues", key="DEMO-4", relation="blocked_by", other="DEMO-2")
    assert ("is blocked by", "DEMO-2") in {(x["relation"], x["key"]) for x in detail["links"]}
    assert detail["blocked_by"] == ["DEMO-2"]
    assert "already exists" in dev.error("link_issues", key="DEMO-2", relation="blocks", other="DEMO-4")


def test_helpful_errors(dev, client_user):
    assert "Columns: Backlog, To Do" in dev.error("move_issue", key="DEMO-2", status="Doing")
    assert "is not a member" in dev.error("create_issue", project="DEMO", title="x", assignee="ghost@x.dev")
    assert "Unknown label(s): nope" in dev.error("create_issue", project="DEMO", title="x", labels=["nope"])
    assert "not an issue key" in dev.error("get_issue", key="DEMO")
    assert "Issue not found" in dev.error("get_issue", key="DEMO-999")
    assert "Project not found" in dev.error("get_project", project="NOPE")
    assert "Nothing to update" in dev.error("update_issue", key="DEMO-2")
    # Role rules come from the API: a client cannot create issues or retitle them.
    assert "Insufficient project role" in client_user.error("create_issue", project="DEMO", title="x")
    assert "Insufficient project role" in client_user.error("update_issue", key="DEMO-2", title="x")


def test_bad_token_is_reported():
    tools = Tools(build_server(TrackerClient("http://testserver", "pt_wrong", http=TestClient(app))))
    assert "API token was rejected" in tools.error("list_projects")
