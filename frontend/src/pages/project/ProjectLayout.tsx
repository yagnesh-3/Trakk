import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useOutletContext, useParams, useSearchParams } from "react-router-dom";
import IssueDrawer from "../../components/IssueDrawer";
import { api, ApiError } from "../../lib/api";
import type { BoardColumn, Issue, Label, Member, Project } from "../../lib/types";

export interface ProjectData {
  project: Project;
  columns: BoardColumn[];
  issues: Issue[];
  members: Member[];
  labels: Label[];
}

export interface ProjectContext {
  data: ProjectData;
  update: (patch: Partial<ProjectData>) => void;
  reloadIssues: () => Promise<void>;
  reloadAll: () => Promise<void>;
  openIssue: (key: string) => void;
  notify: (message: string) => void;
}

export function useProject(): ProjectContext {
  return useOutletContext<ProjectContext>();
}

async function loadProject(key: string): Promise<ProjectData> {
  const [project, columns, issues, members, labels] = await Promise.all([
    api.project(key),
    api.columns(key),
    api.issues(key),
    api.members(key),
    api.labels(key),
  ]);
  return { project, columns, issues, members, labels };
}

export default function ProjectLayout() {
  const { projectKey = "" } = useParams();
  const key = projectKey.toUpperCase();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<ProjectData | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const reloadAll = useCallback(async () => {
    setData(await loadProject(key));
  }, [key]);

  const reloadIssues = useCallback(async () => {
    const issues = await api.issues(key);
    setData((prev) => (prev ? { ...prev, issues } : prev));
  }, [key]);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    loadProject(key)
      .then((loaded) => !cancelled && setData(loaded))
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 404
            ? "This project doesn't exist or you don't have access to it."
            : err instanceof Error
              ? err.message
              : "Could not load the project",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(""), 4000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const openIssue = useCallback(
    (issueKey: string) =>
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("issue", issueKey);
        return next;
      }),
    [setSearchParams],
  );
  const closeIssue = useCallback(
    () =>
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete("issue");
        return next;
      }),
    [setSearchParams],
  );
  const update = useCallback(
    (patch: Partial<ProjectData>) => setData((prev) => (prev ? { ...prev, ...patch } : prev)),
    [],
  );

  if (error) {
    return (
      <main className="page">
        <div className="empty-state">
          <p>{error}</p>
          <Link to="/" className="btn">
            Back to projects
          </Link>
        </div>
      </main>
    );
  }
  if (!data) return <div className="page-loading">Loading project…</div>;

  const openKey = searchParams.get("issue");
  const base = `/p/${data.project.key}`;
  const tabs = [
    { to: base, label: "Board", end: true },
    { to: `${base}/list`, label: "List" },
    { to: `${base}/dashboard`, label: "Dashboard" },
    ...(data.project.myRole === "owner" ? [{ to: `${base}/settings`, label: "Settings" }] : []),
  ];
  const context: ProjectContext = {
    data,
    update,
    reloadIssues,
    reloadAll,
    openIssue,
    notify: setToast,
  };

  return (
    <main className="project-page">
      <div className="project-header">
        <div className="breadcrumb">
          <Link to="/">Projects</Link> / {data.project.key}
          {data.project.archived && <span className="role-badge">Archived</span>}
        </div>
        <h1>{data.project.name}</h1>
        <nav className="project-tabs" aria-label="Project views">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <Outlet context={context} />
      {openKey && (
        <IssueDrawer
          key={openKey}
          issueKey={openKey}
          data={data}
          onClose={closeIssue}
          onOpen={openIssue}
          onChanged={() => void reloadIssues()}
          onLabelsChanged={(labels) => update({ labels })}
        />
      )}
      {toast && (
        <div className="toast" role="alert">
          {toast}
        </div>
      )}
    </main>
  );
}
