"""MCP tools over the Project Tracker API.

Tools accept human-friendly values (column names, emails, label names) and resolve
them to the API's ids, so the model never has to look ids up itself.
"""

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from tracker_mcp.client import TrackerClient, TrackerError

IssueType = Literal["epic", "story", "task", "bug", "decision"]
Priority = Literal["highest", "high", "medium", "low", "lowest"]
LinkKind = Literal["blocks", "blocked_by", "relates"]

# Sentinel the model passes to clear an optional field (None means "leave unchanged").
CLEAR = "none"

INSTRUCTIONS = """\
Project Tracker: a kanban issue tracker. Projects have a short KEY (e.g. APP) and issues
are KEY-<number> (e.g. APP-12). Each project's board has named columns (statuses); call
get_project to see its columns, members and labels before creating or moving issues.
"decision" issues are questions for a client; while open they block the issues they are
linked to with "blocks". When you finish work on an issue, move it to the next column
(e.g. "In Review") and add a comment saying what changed and where (branch, PR, files).
Everything you do is recorded in the issue history under the token owner's name."""

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)


class Tracker:
    """Name resolution and response shaping shared by the tools."""

    def __init__(self, client: TrackerClient, web_url: str | None) -> None:
        self.client = client
        self.web_url = web_url.rstrip("/") if web_url else None

    def call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except TrackerError as exc:
            raise ToolError(str(exc)) from exc

    # --- lookups ---------------------------------------------------------------

    def columns(self, project: str) -> list[dict[str, Any]]:
        return self.call(self.client.get, f"/projects/{project.upper()}/columns")

    def column_id(self, project: str, status: str) -> int:
        columns = self.columns(project)
        for column in columns:
            if column["name"].casefold() == status.strip().casefold():
                return column["id"]
        names = ", ".join(c["name"] for c in columns)
        raise ToolError(f'No column "{status}" in {project.upper()}. Columns: {names}')

    def user_id(self, project: str, who: str) -> int | None:
        """Resolve 'me', 'none' or an email/name of a project member."""
        value = who.strip()
        if value.casefold() == CLEAR:
            return None
        if value.casefold() == "me":
            return self.call(self.client.get, "/auth/me")["id"]
        members = self.call(self.client.get, f"/projects/{project.upper()}/members")
        for member in members:
            user = member["user"]
            if value.casefold() in (user["email"].casefold(), user["name"].casefold()):
                return user["id"]
        people = ", ".join(f'{m["user"]["name"]} <{m["user"]["email"]}>' for m in members)
        raise ToolError(f'"{who}" is not a member of {project.upper()}. Members: {people}')

    def label_ids(self, project: str, names: list[str]) -> list[int]:
        labels = self.call(self.client.get, f"/projects/{project.upper()}/labels")
        by_name = {label["name"].casefold(): label["id"] for label in labels}
        missing = [n for n in names if n.strip().casefold() not in by_name]
        if missing:
            known = ", ".join(label["name"] for label in labels) or "none"
            raise ToolError(f"Unknown label(s): {', '.join(missing)}. Labels: {known}")
        return [by_name[n.strip().casefold()] for n in names]

    # --- shaping ---------------------------------------------------------------

    def url(self, key: str) -> str | None:
        if not self.web_url:
            return None
        return f"{self.web_url}/p/{key.rsplit('-', 1)[0]}?issue={key}"

    def compact(self, issue: dict[str, Any], status_names: dict[int, str]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "key": issue["key"],
            "title": issue["title"],
            "type": issue["type"],
            "status": status_names.get(issue["columnId"], str(issue["columnId"])),
            "done": issue["done"],
            "priority": issue["priority"],
            "assignee": issue["assignee"]["email"] if issue["assignee"] else None,
        }
        if issue["blocked"]:
            out["blocked"] = True
            out["blocked_by"] = issue["blockedBy"]
            if issue["isBlocked"] and issue["blockedReason"]:
                out["blocked_reason"] = issue["blockedReason"]
        if issue["labels"]:
            out["labels"] = [label["name"] for label in issue["labels"]]
        if issue["parentKey"]:
            out["parent"] = issue["parentKey"]
        if issue["dueDate"]:
            out["due_date"] = issue["dueDate"]
        if url := self.url(issue["key"]):
            out["url"] = url
        return out

    def status_names(self, project: str) -> dict[int, str]:
        return {c["id"]: c["name"] for c in self.columns(project)}

    def detail(self, issue: dict[str, Any], comments: list[dict[str, Any]] | None) -> dict[str, Any]:
        out = self.compact(issue, self.status_names(issue["projectKey"]))
        out["description"] = issue["description"]
        out["reporter"] = issue["reporter"]["email"] if issue["reporter"] else None
        out["created_at"] = issue["createdAt"]
        out["updated_at"] = issue["updatedAt"]
        phrases = {("blocks", "outward"): "blocks", ("blocks", "inward"): "is blocked by",
                   ("relates", "outward"): "relates to", ("relates", "inward"): "relates to"}
        out["links"] = [
            {
                "relation": phrases[(link["type"], link["direction"])],
                "key": link["issue"]["key"],
                "title": link["issue"]["title"],
                "done": link["issue"]["done"],
            }
            for link in issue.get("links", [])
        ]
        out["children"] = [
            {"key": c["key"], "title": c["title"], "done": c["done"]} for c in issue.get("children", [])
        ]
        if comments is not None:
            out["comments"] = [
                {
                    "author": c["author"]["email"] if c["author"] else None,
                    "at": c["createdAt"],
                    "body": c["body"],
                }
                for c in comments
            ]
        return out

    def project_of(self, key: str) -> str:
        project, sep, number = key.strip().upper().rpartition("-")
        if not sep or not number.isdigit():
            raise ToolError(f'"{key}" is not an issue key; expected something like APP-12')
        return project


def build_server(client: TrackerClient, web_url: str | None = None) -> MCPServer:
    t = Tracker(client, web_url)
    server = MCPServer(name="project-tracker", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def list_projects() -> list[dict[str, Any]]:
        """List the projects the token's user can see, with their role in each."""
        projects = t.call(t.client.get, "/projects")
        return [
            {"key": p["key"], "name": p["name"], "role": p["myRole"], "description": p["description"]}
            for p in projects
        ]

    @server.tool(annotations=READ_ONLY)
    def get_project(project: str) -> dict[str, Any]:
        """Show a project's board columns (statuses) in order, its members and labels.

        Args:
            project: Project key, e.g. "APP".
        """
        key = project.strip().upper()
        info = t.call(t.client.get, f"/projects/{key}")
        members = t.call(t.client.get, f"/projects/{key}/members")
        labels = t.call(t.client.get, f"/projects/{key}/labels")
        summary = t.call(t.client.get, f"/projects/{key}/summary")
        counts = {c["columnId"]: c["count"] for c in summary["byColumn"]}
        return {
            "key": info["key"],
            "name": info["name"],
            "description": info["description"],
            "your_role": info["myRole"],
            "columns": [
                {
                    "name": c["name"],
                    "category": c["category"],
                    "issues": counts.get(c["id"], 0),
                    **({"wip_limit": c["wipLimit"]} if c["wipLimit"] else {}),
                }
                for c in t.columns(key)
            ],
            "members": [
                {"name": m["user"]["name"], "email": m["user"]["email"], "role": m["role"]}
                for m in members
            ],
            "labels": [label["name"] for label in labels],
            "open_issues": summary["open"],
            "blocked": summary["blocked"],
            "overdue": summary["overdue"],
            "open_decisions": summary["openDecisions"],
        }

    @server.tool(annotations=READ_ONLY)
    def search_issues(
        project: str,
        query: str | None = None,
        status: str | None = None,
        type: IssueType | None = None,
        assignee: str | None = None,
        label: str | None = None,
        blocked: bool | None = None,
        include_done: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find issues in a project, in board order.

        Args:
            project: Project key, e.g. "APP".
            query: Text in the title, or an issue number/key.
            status: Column name, e.g. "In Progress".
            type: Issue type.
            assignee: "me", "none", or a member's email or name.
            label: Label name.
            blocked: true for only blocked issues, false for only unblocked ones.
            include_done: false to hide issues in done columns.
            limit: Maximum issues to return (1-200).
        """
        key = project.strip().upper()
        params: list[tuple[str, Any]] = []
        if query:
            params.append(("q", query))
        if status:
            params.append(("columnId", t.column_id(key, status)))
        if type:
            params.append(("type", type))
        if assignee:
            who = assignee.strip().casefold()
            if who in ("me", CLEAR):
                params.append(("assignee", who))
            else:
                params.append(("assignee", t.user_id(key, assignee)))
        if label:
            params.append(("labelId", t.label_ids(key, [label])[0]))
        if blocked is not None:
            params.append(("blocked", str(blocked).lower()))
        issues = t.call(t.client.request, "GET", f"/projects/{key}/issues", params=params)
        if not include_done:
            issues = [i for i in issues if not i["done"]]
        names = t.status_names(key)
        limit = max(1, min(limit, 200))
        return {
            "total": len(issues),
            "issues": [t.compact(i, names) for i in issues[:limit]],
            **({"truncated": True} if len(issues) > limit else {}),
        }

    @server.tool(annotations=READ_ONLY)
    def get_issue(key: str, include_comments: bool = True) -> dict[str, Any]:
        """Get one issue with its description, links, child issues and comments.

        Args:
            key: Issue key, e.g. "APP-12".
            include_comments: Also return the comment thread.
        """
        t.project_of(key)
        issue = t.call(t.client.get, f"/issues/{key.strip().upper()}")
        comments = (
            t.call(t.client.get, f"/issues/{issue['key']}/comments") if include_comments else None
        )
        return t.detail(issue, comments)

    @server.tool(annotations=WRITE)
    def create_issue(
        project: str,
        title: str,
        description: str = "",
        type: IssueType = "task",
        priority: Priority = "medium",
        status: str | None = None,
        assignee: str | None = None,
        parent: str | None = None,
        labels: list[str] | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create an issue. Needs the developer or owner role in the project.

        Args:
            project: Project key, e.g. "APP".
            title: Short summary.
            description: Details, plain text or markdown.
            type: epic, story, task, bug or decision.
            priority: highest, high, medium, low or lowest.
            status: Column name to create it in; defaults to the first column.
            assignee: "me" or a member's email or name.
            parent: Key of the parent issue (usually an epic), e.g. "APP-3".
            labels: Existing label names.
            due_date: YYYY-MM-DD.
        """
        key = project.strip().upper()
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "type": type,
            "priority": priority,
        }
        if status:
            body["columnId"] = t.column_id(key, status)
        if assignee:
            body["assigneeId"] = t.user_id(key, assignee)
        if parent:
            body["parentKey"] = parent.strip().upper()
        if labels:
            body["labelIds"] = t.label_ids(key, labels)
        if due_date:
            body["dueDate"] = due_date
        issue = t.call(t.client.post, f"/projects/{key}/issues", body)
        return t.compact(issue, t.status_names(key))

    @server.tool(annotations=WRITE)
    def update_issue(
        key: str,
        title: str | None = None,
        description: str | None = None,
        type: IssueType | None = None,
        priority: Priority | None = None,
        assignee: str | None = None,
        parent: str | None = None,
        labels: list[str] | None = None,
        due_date: str | None = None,
        blocked: bool | None = None,
        blocked_reason: str | None = None,
    ) -> dict[str, Any]:
        """Change fields of an issue. Omitted fields stay as they are.

        To change status use move_issue. Clients may only edit the description of
        decision issues.

        Args:
            key: Issue key, e.g. "APP-12".
            title: New title.
            description: New description (replaces the old one).
            type: New type.
            priority: New priority.
            assignee: "me", a member's email or name, or "none" to unassign.
            parent: Parent issue key, or "none" to detach.
            labels: The full new set of label names ([] removes all).
            due_date: YYYY-MM-DD, or "none" to clear.
            blocked: Set or clear the manual blocked flag.
            blocked_reason: Why it is blocked.
        """
        project = t.project_of(key)
        body: dict[str, Any] = {}
        for field, value in (
            ("title", title),
            ("description", description),
            ("type", type),
            ("priority", priority),
            ("isBlocked", blocked),
            ("blockedReason", blocked_reason),
        ):
            if value is not None:
                body[field] = value
        if assignee is not None:
            body["assigneeId"] = t.user_id(project, assignee)
        if parent is not None:
            body["parentKey"] = None if parent.strip().casefold() == CLEAR else parent.strip().upper()
        if labels is not None:
            body["labelIds"] = t.label_ids(project, labels)
        if due_date is not None:
            body["dueDate"] = None if due_date.strip().casefold() == CLEAR else due_date
        if not body:
            raise ToolError("Nothing to update: pass at least one field")
        issue = t.call(t.client.patch, f"/issues/{key.strip().upper()}", body)
        return t.compact(issue, t.status_names(project))

    @server.tool(annotations=WRITE)
    def move_issue(
        key: str, status: str, position: Literal["top", "bottom"] = "bottom"
    ) -> dict[str, Any]:
        """Move an issue to another board column (change its status).

        Moving an issue into a done column unblocks the issues it blocks.

        Args:
            key: Issue key, e.g. "APP-12".
            status: Target column name, e.g. "In Review" or "Done".
            position: Put it at the top or bottom of that column.
        """
        project = t.project_of(key)
        column_id = t.column_id(project, status)
        index = 0 if position == "top" else 1_000_000
        issue = t.call(
            t.client.post, f"/issues/{key.strip().upper()}/move", {"columnId": column_id, "index": index}
        )
        return t.compact(issue, t.status_names(project))

    @server.tool(annotations=WRITE)
    def add_comment(key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue (e.g. what was done, links to a PR or commit).

        Args:
            key: Issue key, e.g. "APP-12".
            body: Comment text, plain text or markdown.
        """
        t.project_of(key)
        comment = t.call(t.client.post, f"/issues/{key.strip().upper()}/comments", {"body": body})
        return {
            "key": key.strip().upper(),
            "comment_id": comment["id"],
            "author": comment["author"]["email"] if comment["author"] else None,
            "at": comment["createdAt"],
            **({"url": u} if (u := t.url(key.strip().upper())) else {}),
        }

    @server.tool(annotations=WRITE)
    def link_issues(key: str, relation: LinkKind, other: str) -> dict[str, Any]:
        """Link two issues in the same project.

        Args:
            key: Issue key, e.g. "APP-12".
            relation: "blocks" (key blocks other), "blocked_by" (other blocks key) or "relates".
            other: The other issue key.
        """
        t.project_of(key)
        t.project_of(other)
        a, b = key.strip().upper(), other.strip().upper()
        if relation == "blocked_by":
            t.call(t.client.post, f"/issues/{b}/links", {"type": "blocks", "targetKey": a})
        else:
            t.call(t.client.post, f"/issues/{a}/links", {"type": relation, "targetKey": b})
        return t.detail(t.call(t.client.get, f"/issues/{a}"), None)

    @server.tool(annotations=READ_ONLY)
    def my_open_decisions() -> list[dict[str, Any]]:
        """Open decision issues assigned to the token's user, across all projects."""
        issues = t.call(t.client.get, "/me/decisions")
        names: dict[str, dict[int, str]] = {}
        out = []
        for issue in issues:
            project = issue["projectKey"]
            if project not in names:
                names[project] = t.status_names(project)
            out.append(t.compact(issue, names[project]))
        return out

    return server
