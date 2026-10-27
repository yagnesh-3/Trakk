import type {
  Activity,
  BoardColumn,
  Comment,
  Issue,
  IssueDetail,
  IssueType,
  IssueUpdate,
  ApiToken,
  ApiTokenCreated,
  ColumnCategory,
  Label,
  LinkType,
  Member,
  Priority,
  Project,
  ProjectRole,
  ProjectSummary,
  SystemRole,
  User,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{loc, msg}, ...]
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = first.loc?.slice(1).join(".");
    return field ? `${field}: ${first.msg}` : (first.msg ?? fallback);
  }
  return fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}/api${path}`, {
    method,
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(data, response.statusText));
  }
  return data as T;
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
const del = (path: string) => request<void>("DELETE", path);

const enc = encodeURIComponent;

export const api = {
  // auth
  me: () => get<User>("/auth/me"),
  login: (email: string, password: string) => post<User>("/auth/login", { email, password }),
  logout: () => post<void>("/auth/logout"),
  changePassword: (currentPassword: string, newPassword: string) =>
    post<User>("/auth/change-password", { currentPassword, newPassword }),

  // users (create/update are admin-only)
  users: () => get<User[]>("/users"),
  createUser: (data: { email: string; name: string; password: string; systemRole: SystemRole }) =>
    post<User>("/users", data),
  updateUser: (
    id: number,
    data: { name?: string; systemRole?: SystemRole; isActive?: boolean; password?: string },
  ) => patch<User>(`/users/${id}`, data),
  myDecisions: () => get<Issue[]>("/me/decisions"),

  // API tokens
  tokens: () => get<ApiToken[]>("/tokens"),
  createToken: (name: string) => post<ApiTokenCreated>("/tokens", { name }),
  deleteToken: (id: number) => del(`/tokens/${id}`),

  // projects
  projects: () => get<Project[]>("/projects"),
  project: (key: string) => get<Project>(`/projects/${enc(key)}`),
  createProject: (data: { key: string; name: string; description?: string }) =>
    post<Project>("/projects", data),
  updateProject: (key: string, data: { name?: string; description?: string; archived?: boolean }) =>
    patch<Project>(`/projects/${enc(key)}`, data),
  summary: (key: string) => get<ProjectSummary>(`/projects/${enc(key)}/summary`),
  projectActivity: (key: string, limit = 50) =>
    get<Activity[]>(`/projects/${enc(key)}/activity?limit=${limit}`),

  members: (key: string) => get<Member[]>(`/projects/${enc(key)}/members`),
  setMember: (key: string, member: { userId?: number; email?: string; role: ProjectRole }) =>
    put<Member>(`/projects/${enc(key)}/members`, member),
  removeMember: (key: string, userId: number) => del(`/projects/${enc(key)}/members/${userId}`),

  columns: (key: string) => get<BoardColumn[]>(`/projects/${enc(key)}/columns`),
  createColumn: (key: string, data: { name: string; category: ColumnCategory; wipLimit?: number | null }) =>
    post<BoardColumn>(`/projects/${enc(key)}/columns`, data),
  updateColumn: (
    key: string,
    id: number,
    data: { name?: string; category?: ColumnCategory; wipLimit?: number | null },
  ) => patch<BoardColumn>(`/projects/${enc(key)}/columns/${id}`, data),
  deleteColumn: (key: string, id: number) => del(`/projects/${enc(key)}/columns/${id}`),
  reorderColumns: (key: string, columnIds: number[]) =>
    put<BoardColumn[]>(`/projects/${enc(key)}/columns/order`, { columnIds }),

  labels: (key: string) => get<Label[]>(`/projects/${enc(key)}/labels`),
  createLabel: (key: string, name: string, color: string) =>
    post<Label>(`/projects/${enc(key)}/labels`, { name, color }),
  updateLabel: (key: string, id: number, data: { name?: string; color?: string }) =>
    patch<Label>(`/projects/${enc(key)}/labels/${id}`, data),
  deleteLabel: (key: string, id: number) => del(`/projects/${enc(key)}/labels/${id}`),

  // issues
  issues: (key: string) => get<Issue[]>(`/projects/${enc(key)}/issues`),
  createIssue: (
    key: string,
    data: { title: string; type?: IssueType; priority?: Priority; columnId?: number },
  ) => post<IssueDetail>(`/projects/${enc(key)}/issues`, data),
  issue: (key: string) => get<IssueDetail>(`/issues/${enc(key)}`),
  updateIssue: (key: string, data: IssueUpdate) => patch<IssueDetail>(`/issues/${enc(key)}`, data),
  moveIssue: (key: string, columnId: number, index: number) =>
    post<IssueDetail>(`/issues/${enc(key)}/move`, { columnId, index }),
  deleteIssue: (key: string) => del(`/issues/${enc(key)}`),
  issueActivity: (key: string) => get<Activity[]>(`/issues/${enc(key)}/activity`),

  // links
  addLink: (key: string, type: LinkType, targetKey: string) =>
    post<IssueDetail>(`/issues/${enc(key)}/links`, { type, targetKey }),
  removeLink: (id: number) => del(`/links/${id}`),

  // comments
  comments: (key: string) => get<Comment[]>(`/issues/${enc(key)}/comments`),
  addComment: (key: string, body: string) => post<Comment>(`/issues/${enc(key)}/comments`, { body }),
  editComment: (id: number, body: string) => patch<Comment>(`/comments/${id}`, { body }),
  deleteComment: (id: number) => del(`/comments/${id}`),
};
