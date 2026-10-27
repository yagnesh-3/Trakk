"""Import every model so Base.metadata is complete (Alembic, create_all)."""

from app.models.issue import Activity, Comment, Issue, IssueLink, issue_labels
from app.models.project import BoardColumn, Label, Project, ProjectMember
from app.models.user import ApiToken, User

__all__ = [
    "Activity",
    "ApiToken",
    "BoardColumn",
    "Comment",
    "Issue",
    "IssueLink",
    "Label",
    "Project",
    "ProjectMember",
    "User",
    "issue_labels",
]
