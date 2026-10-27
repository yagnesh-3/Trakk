# Project Tracker — API

FastAPI backend for a multi-project kanban issue tracker (projects, boards, issues, decisions,
comments, activity history, API tokens).

## Run locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.cli create-admin --email you@company.com --name "Your Name"
.venv/Scripts/python -m app.cli seed-demo              # optional sample data
.venv/Scripts/uvicorn app.main:app --reload --port 8100
```

API docs: http://localhost:8100/docs (disabled in production).

## Tests and lint

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
```

## Layout

- `app/core` (settings, password/JWT/token security, rate limiter)
- `app/db` (engine, session, base)
- `app/models` (SQLAlchemy models)
- `app/schemas` (camelCase request/response models)
- `app/services` (business rules)
- `app/api` (routes and auth/permission dependencies)
- `migrations/` (Alembic)
- `tests/`

After changing models, run `alembic revision --autogenerate -m "..."`. The test
`test_migrations_match_models` fails if the migrations and the models drift apart.

## Access model

- **System roles:** `admin` (manages users, creates projects, owner everywhere) and `member`.
- **Project roles** (each includes the ones below it):
  - `owner`: members, columns, project settings.
  - `developer`: create/edit/move/delete issues, labels, links.
  - `client`: comment; on **decision** issues, can also edit the description and move the issue.
  - `viewer`: read-only.
- Owners add members with `PUT /api/projects/{key}/members` using `userId` or the `email` of an existing
  user (non-admins cannot list every user).
- Non-members get `404` for a project and its issues.
- Admin-created users must change their password on first login.

## Auth

- **Browser:** `POST /api/auth/login` sets an HttpOnly session cookie. Cross-origin writes are rejected
  unless the origin is listed in `FRONTEND_ORIGIN`.
- **Scripts / Claude:** create a token from a signed-in session (`POST /api/tokens`), then send
  `Authorization: Bearer pt_…`. A token acts as its user. Tokens cannot create other tokens.

## Key concepts

- Issue keys are `<PROJECT>-<n>`, e.g. `APP-12`. Numbers are never reused.
- Moving: `POST /api/issues/{key}/move {columnId, index}` re-numbers positions in the affected columns.
- An issue is `blocked` when its manual flag is set **or** any issue that `blocks` it is not in a
  `done` column. `blockedBy` lists those blockers.
- `GET /api/me/decisions`: open decision issues assigned to the caller.
- `GET /api/projects/{key}/summary`: counts, blocked/overdue/decisions, recent activity.
- Every change is written to the append-only `activity` table.
