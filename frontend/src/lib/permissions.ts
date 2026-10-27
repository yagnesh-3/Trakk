import type { Issue, ProjectRole } from "./types";

// Mirrors the backend rules in app/services/issues.py; the server is the authority.

const RANK: Record<ProjectRole, number> = { viewer: 0, client: 1, developer: 2, owner: 3 };

export const atLeast = (role: ProjectRole, min: ProjectRole) => RANK[role] >= RANK[min];

export const canEditIssues = (role: ProjectRole) => atLeast(role, "developer");

export const canMoveIssue = (role: ProjectRole, issue: Pick<Issue, "type">) =>
  canEditIssues(role) || (role === "client" && issue.type === "decision");

export const canEditDescription = (role: ProjectRole, issue: Pick<Issue, "type">) =>
  canMoveIssue(role, issue);

export const canComment = (role: ProjectRole) => atLeast(role, "client");
