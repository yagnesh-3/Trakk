# Project Tracker — MCP server

Lets Claude Code (or any MCP client) read and update tracker issues with your API token. It talks
to the tracker's REST API, so everything it does follows your project roles and is recorded in
issue history under your name.

## Tools

| Tool | What it does |
|---|---|
| `list_projects` | Projects you can see, with your role |
| `get_project` | Columns (statuses) in order, members, labels, open/blocked/overdue counts |
| `search_issues` | Filter by text, status, type, assignee (`me`/`none`/email), label, blocked |
| `get_issue` | Description, links, child issues, comments |
| `create_issue` | Title, description, type, priority, status, assignee, parent, labels, due date |
| `update_issue` | Change fields; `"none"` clears assignee / parent / due date |
| `move_issue` | Move to a column by name, at the top or bottom |
| `add_comment` | Comment on an issue |
| `link_issues` | `blocks`, `blocked_by` or `relates` |
| `my_open_decisions` | Open decision issues assigned to you |

Statuses, people and labels are given by name or email; the server looks up the ids. Mistakes come
back as readable errors that list the valid options (e.g. the project's column names).

## Install

```bash
cd mcp-server
python -m venv .venv
.venv/Scripts/pip install -e .          # macOS/Linux: .venv/bin/pip
```

## Configure

| Variable | Default | |
|---|---|---|
| `PT_API_TOKEN` | — | **Required.** Create one in the tracker: user menu → API tokens |
| `PT_API_URL` | `http://localhost:8100` | Tracker API origin |
| `PT_WEB_URL` | `http://localhost:5180` | Used to add issue links to results; set empty to omit |

## Add to Claude Code

Available in every project (user scope). The token is stored in your user config, not in a repository:

```bash
claude mcp add project-tracker --scope user -e PT_API_TOKEN=pt_your_token -e PT_API_URL=http://localhost:8100 -- C:/Users/yagnesh/Desktop/projectTracker/mcp-server/.venv/Scripts/project-tracker-mcp.exe
```

To share the setup with a repository instead, commit a `.mcp.json` that reads the token from each
developer's environment. Never commit the token itself:

```json
{
  "mcpServers": {
    "project-tracker": {
      "command": "C:/Users/yagnesh/Desktop/projectTracker/mcp-server/.venv/Scripts/project-tracker-mcp.exe",
      "env": { "PT_API_TOKEN": "${PT_API_TOKEN}", "PT_API_URL": "http://localhost:8100" }
    }
  }
}
```

Check it with `claude mcp list`, or `/mcp` inside Claude Code.

A suggested convention for repositories that use it: mention the issue key in commit messages
(`APP-12: add rate limiting`), and when finishing work move the issue to **In Review** with a
comment that names the branch or PR.

## Tests

```bash
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

The tests connect a real MCP client to the server in-process and run every tool against the real
backend (SQLite, demo seed data). That's why `requirements-dev.txt` includes the backend's
requirements.
