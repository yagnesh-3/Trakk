import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import type { Project } from "../lib/types";

const ROLE_LABEL = { owner: "Owner", developer: "Developer", client: "Client", viewer: "Viewer" };

export default function ProjectsPage() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .projects()
      .then(setProjects)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <main className="page">
      <div className="page-header">
        <h1>Projects</h1>
        {user?.systemRole === "admin" && !creating && (
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            New project
          </button>
        )}
      </div>
      {creating && <NewProjectForm onCancel={() => setCreating(false)} />}
      {error && <div className="form-error">{error}</div>}
      {projects === null && !error && <p className="muted">Loading…</p>}
      {projects?.length === 0 && (
        <div className="empty-state">
          <p>You're not a member of any project yet.</p>
          {user?.systemRole !== "admin" && (
            <p className="muted">Ask an admin or a project owner to add you.</p>
          )}
        </div>
      )}
      <div className="project-grid">
        {projects?.map((p) => (
          <Link key={p.id} to={`/p/${p.key}`} className="project-card">
            <div className="project-card-head">
              <span className="project-key">{p.key}</span>
              <span className="role-badge">{ROLE_LABEL[p.myRole]}</span>
            </div>
            <h2>{p.name}</h2>
            {p.description && <p className="muted clamp-2">{p.description}</p>}
          </Link>
        ))}
      </div>
    </main>
  );
}

function NewProjectForm({ onCancel }: { onCancel: () => void }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [keyTouched, setKeyTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function suggestKey(value: string) {
    const words = value.toUpperCase().replace(/[^A-Z0-9 ]/g, "").trim().split(/\s+/);
    const fromInitials = words.map((w) => w[0] ?? "").join("");
    return (fromInitials.length >= 2 ? fromInitials : (words[0] ?? "")).slice(0, 6);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject({ key, name, description });
      navigate(`/p/${project.key}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project");
      setBusy(false);
    }
  }

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <label className="field">
        <span>Name</span>
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!keyTouched) setKey(suggestKey(e.target.value));
          }}
          required
          autoFocus
        />
      </label>
      <label className="field">
        <span>Key</span>
        <input
          value={key}
          onChange={(e) => {
            setKeyTouched(true);
            setKey(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 10));
          }}
          pattern="[A-Z][A-Z0-9]{1,9}"
          title="2–10 capital letters or digits, starting with a letter"
          required
        />
        <small className="muted">Issue keys will look like {key || "KEY"}-1</small>
      </label>
      <label className="field span-2">
        <span>Description</span>
        <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      {error && <div className="form-error span-2">{error}</div>}
      <div className="form-actions span-2">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={busy}>
          Create project
        </button>
      </div>
    </form>
  );
}
