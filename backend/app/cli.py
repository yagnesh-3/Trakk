"""Command-line tasks.

    python -m app.cli create-admin --email you@company.com --name "Your Name"
    python -m app.cli seed-demo
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ProjectAccess, resolve_project_access
from app.db.session import SessionLocal
from app.models import Issue, Project, User
from app.models.enums import IssueType, LinkType, Priority, ProjectRole, SystemRole
from app.schemas.issue import IssueCreate
from app.schemas.project import LabelCreate, ProjectCreate
from app.schemas.user import PASSWORD_MIN, UserCreate
from app.services import issues, projects, users

DEMO_PASSWORD = "demo-password-123"


def create_admin(db: Session, email: str, name: str, password: str) -> User:
    return users.create_user(
        db,
        UserCreate(email=email, name=name, password=password, system_role=SystemRole.admin),
        must_change_password=False,
    )


def _demo_user(db: Session, email: str, name: str, role: SystemRole) -> User:
    existing = users.get_by_email(db, email)
    if existing:
        return existing
    return users.create_user(
        db, UserCreate(email=email, name=name, password=DEMO_PASSWORD, system_role=role),
        must_change_password=False,
    )


def seed_demo(db: Session) -> None:
    """Idempotent sample data: two projects, four users, a few linked issues."""
    admin = _demo_user(db, "admin@demo.dev", "Demo Admin", SystemRole.admin)
    dev = _demo_user(db, "dev@demo.dev", "Dana Developer", SystemRole.member)
    client = _demo_user(db, "client@demo.dev", "Casey Client", SystemRole.member)
    viewer = _demo_user(db, "viewer@demo.dev", "Vic Viewer", SystemRole.member)

    for key, name in (("DEMO", "Demo Website"), ("MOB", "Demo Mobile App")):
        if db.scalar(select(Project).where(Project.key == key)):
            continue
        project = projects.create_project(
            db, ProjectCreate(key=key, name=name, description=f"Sample project {name}."), admin
        )
        projects.upsert_member(db, project, dev.id, ProjectRole.developer, admin)
        projects.upsert_member(db, project, client.id, ProjectRole.client, admin)
        projects.upsert_member(db, project, viewer.id, ProjectRole.viewer, admin)
        frontend = projects.create_label(db, project, LabelCreate(name="frontend", color="#2563eb"))
        backend = projects.create_label(db, project, LabelCreate(name="backend", color="#16a34a"))
        cols = projects.list_columns(db, project)
        access = resolve_project_access(db, project, admin, ProjectRole.owner)

        def add(title: str, access: ProjectAccess = access, **kw: object) -> Issue:
            return issues.create_issue(db, access, IssueCreate(title=title, **kw))  # type: ignore[arg-type]

        epic = add("User accounts", type=IssueType.epic, priority=Priority.high)
        add("Login page", type=IssueType.story, parent_key=epic.key, assignee_id=dev.id,
            column_id=cols[2].id, label_ids=[frontend.id])
        api = add("Auth API", type=IssueType.task, parent_key=epic.key, assignee_id=dev.id,
                  column_id=cols[4].id, label_ids=[backend.id])
        add("Password reset email bounces", type=IssueType.bug, priority=Priority.highest,
            column_id=cols[1].id, label_ids=[backend.id])
        decision = add("Which email provider should we use?", type=IssueType.decision,
                       assignee_id=client.id, column_id=cols[1].id,
                       description="Options: SES, Postmark, SendGrid.")
        blocked = add("Send welcome emails", type=IssueType.story, column_id=cols[0].id)
        issues.add_link(db, decision, access, LinkType.blocks, blocked.key)
        issues.add_link(db, api, access, LinkType.relates, blocked.key)
    print(f"Demo data ready. Users: admin/dev/client/viewer@demo.dev, password {DEMO_PASSWORD}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="create an admin user")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password", help="prompted for when omitted")
    sub.add_parser("seed-demo", help="add sample users, projects and issues")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "create-admin":
            password = args.password or getpass.getpass("Password: ")
            if len(password) < PASSWORD_MIN:
                print(f"Password must be at least {PASSWORD_MIN} characters", file=sys.stderr)
                return 1
            user = create_admin(db, args.email, args.name, password)
            print(f"Created admin {user.email}")
        elif args.command == "seed-demo":
            seed_demo(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
