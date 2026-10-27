# Project Tracker

A lightweight, multi-project kanban issue tracker: boards, issues, client decisions that block
work, comments, history, and an API Claude can use.

- `backend/`: FastAPI + SQLAlchemy + Alembic. See [backend/README.md](backend/README.md).
- `frontend/`: React + TypeScript + Vite, with drag-and-drop via dnd-kit.
- `mcp-server/`: MCP server so Claude Code can list, create, move and comment on issues with an
  API token. See [mcp-server/README.md](mcp-server/README.md).

## Run locally

The tracker uses ports **8100** (API) and **5180** (web), so it doesn't clash with other projects
on 8000/5173.

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
cp .env.example .env
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.cli seed-demo     # demo users: admin/dev/client/viewer@demo.dev, password demo-password-123
.venv/Scripts/uvicorn app.main:app --reload --port 8100
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                                    # http://localhost:5180
```

In development, Vite proxies `/api` to the API, so the session cookie stays same-origin. When the
frontend is hosted separately, set `VITE_API_URL` (frontend) and `FRONTEND_ORIGIN`,
`COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` (backend).
