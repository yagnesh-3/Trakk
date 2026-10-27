// Mirrors the API's camelCase schemas (backend/app/schemas).

export type SystemRole = "admin" | "member";
export type ProjectRole = "viewer" | "client" | "developer" | "owner";
export type ColumnCategory = "todo" | "in_progress" | "done";
export type IssueType = "epic" | "story" | "task" | "bug" | "decision";
export type Priority = "lowest" | "low" | "medium" | "high" | "highest";
export type LinkType = "blocks" | "relates";

export const ISSUE_TYPES: IssueType[] = ["epic", "story", "task", "bug", "decision"];
export const PRIORITIES: Priority[] = ["highest", "high", "medium", "low", "lowest"];

export interface UserRef {
  id: number;
  name: string;
  email: string;
}

export interface User extends UserRef {
  systemRole: SystemRole;
  isActive: boolean;
  mustChangePassword: boolean;
  createdAt: string;
}

export interface Project {
  id: number;
  key: string;
  name: string;
  description: string;
  archived: boolean;
  createdAt: string;
  myRole: ProjectRole;
}

export interface Member {
  user: UserRef;
  role: ProjectRole;
}

export interface BoardColumn {
  id: number;
  name: string;
  position: number;
  category: ColumnCategory;
  wipLimit: number | null;
}

export interface Label {
  id: number;
  name: string;
  color: string;
}

export interface IssueRef {
  key: string;
  title: string;
  type: IssueType;
  columnId: number;
  done: boolean;
}

export interface Issue {
  id: number;
  key: string;
  number: number;
  projectKey: string;
  title: string;
  description: string;
  type: IssueType;
  priority: Priority;
  columnId: number;
  position: number;
  assignee: UserRef | null;
  reporter: UserRef | null;
  parentKey: string | null;
  dueDate: string | null;
  isBlocked: boolean;
  blockedReason: string;
  blockedBy: string[];
  blocked: boolean;
  done: boolean;
  labels: Label[];
  createdAt: string;
  updatedAt: string;
}

export interface IssueLink {
  id: number;
  type: LinkType;
  direction: "outward" | "inward";
  issue: IssueRef;
}

export interface IssueDetail extends Issue {
  links: IssueLink[];
  children: IssueRef[];
}

export interface IssueUpdate {
  title?: string;
  description?: string;
  type?: IssueType;
  priority?: Priority;
  assigneeId?: number | null;
  parentKey?: string | null;
  dueDate?: string | null;
  isBlocked?: boolean;
  blockedReason?: string;
  labelIds?: number[];
}

export interface Comment {
  id: number;
  author: UserRef | null;
  body: string;
  createdAt: string;
  updatedAt: string;
}

export interface Activity {
  id: number;
  issueKey: string;
  actor: UserRef | null;
  action: string;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface ColumnCount {
  columnId: number;
  name: string;
  count: number;
}

export interface ProjectSummary {
  total: number;
  open: number;
  blocked: number;
  overdue: number;
  openDecisions: number;
  byColumn: ColumnCount[];
  byType: Partial<Record<IssueType, number>>;
  recentActivity: Activity[];
}

export interface ApiToken {
  id: number;
  name: string;
  prefix: string;
  createdAt: string;
  lastUsedAt: string | null;
}

export interface ApiTokenCreated extends ApiToken {
  token: string;
}
