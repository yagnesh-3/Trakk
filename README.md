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

## Deploy

Production runs as **one container** ([Dockerfile](Dockerfile)). It builds the web app and the API
serves it, so the browser talks to a single origin: no CORS or cross-site cookie setup. On every
start it runs the migrations, then `ensure-admin`, then the server.

### Render (Blueprint included)

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, pick the repo. [render.yaml](render.yaml) creates the web service
   and a Postgres database, wires `DATABASE_URL`, and generates `JWT_SECRET`.
3. When asked, fill in `ADMIN_EMAIL`, `ADMIN_NAME` and `ADMIN_PASSWORD` (12+ characters).
4. Once deployed, open the service URL and sign in with that email and password. You're asked to set
   a new password straight away. After that, `ADMIN_PASSWORD` is no longer used, and redeploys never
   reset it.
5. Create the real users under **Manage users** and your projects. Don't run `seed-demo` in production.

Plans in the blueprint: web `starter` (the free plan works but sleeps when idle) and Postgres
`basic-256mb` (Render deletes free databases after 30 days). Change them in `render.yaml` or the
dashboard.

### Any other Docker host (Railway, Fly.io, a VPS…)

Build the image and set these environment variables:

| Variable | |
|---|---|
| `DATABASE_URL` | Postgres URL. `postgres://` and `postgresql://` URLs are accepted as given |
| `JWT_SECRET` | 32+ random characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COOKIE_SECURE` | `true` (serve over HTTPS) |
| `ADMIN_EMAIL`, `ADMIN_NAME`, `ADMIN_PASSWORD` | the first admin, created if missing |
| `PORT` | optional, default 8000 |

```bash
docker build -t project-tracker .
docker run -p 8000:8000 --env-file prod.env project-tracker
```

### Locked out?

With shell access to the server (Render: the service's **Shell** tab), create another admin:

```bash
python -m app.cli create-admin --email you@company.com --name "Your Name"
```

### Claude / MCP against production

Create a token in the hosted app (user menu → API tokens), then register the MCP server with
`PT_API_URL` and `PT_WEB_URL` set to the service URL. See [mcp-server/README.md](mcp-server/README.md).
