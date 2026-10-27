"""Enumerations stored as plain strings in the database."""

from enum import StrEnum


class SystemRole(StrEnum):
    admin = "admin"
    member = "member"


class ProjectRole(StrEnum):
    viewer = "viewer"
    client = "client"
    developer = "developer"
    owner = "owner"


# Higher rank includes every permission of the lower ranks.
ROLE_RANK = {
    ProjectRole.viewer: 0,
    ProjectRole.client: 1,
    ProjectRole.developer: 2,
    ProjectRole.owner: 3,
}


class ColumnCategory(StrEnum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class IssueType(StrEnum):
    epic = "epic"
    story = "story"
    task = "task"
    bug = "bug"
    decision = "decision"


class Priority(StrEnum):
    lowest = "lowest"
    low = "low"
    medium = "medium"
    high = "high"
    highest = "highest"


class LinkType(StrEnum):
    blocks = "blocks"
    relates = "relates"


DEFAULT_COLUMNS: list[tuple[str, ColumnCategory]] = [
    ("Backlog", ColumnCategory.todo),
    ("To Do", ColumnCategory.todo),
    ("In Progress", ColumnCategory.in_progress),
    ("In Review", ColumnCategory.in_progress),
    ("Done", ColumnCategory.done),
]
