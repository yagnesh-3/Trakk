import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { Avatar } from "../../components/Avatar";
import { LabelChip } from "../../components/IssueBadges";
import { api } from "../../lib/api";
import type { BoardColumn, ColumnCategory, Label, ProjectRole, User } from "../../lib/types";
import { useProject } from "./ProjectLayout";

const ROLES: { value: ProjectRole; label: string; hint: string }[] = [
  { value: "owner", label: "Owner", hint: "Everything, including members and columns" },
  { value: "developer", label: "Developer", hint: "Create, edit and move issues" },
  { value: "client", label: "Client", hint: "Read, comment, and answer decisions" },
  { value: "viewer", label: "Viewer", hint: "Read only" },
];

const CATEGORIES: { value: ColumnCategory; label: string }[] = [
  { value: "todo", label: "To do" },
  { value: "in_progress", label: "In progress" },
  { value: "done", label: "Done" },
];

/** Runs an API action and reports a failure through the project toast. */
function useRunner() {
  const { notify } = useProject();
  return async (action: () => Promise<unknown>) => {
    try {
      await action();
      return true;
    } catch (err) {
      notify(err instanceof Error ? err.message : "Something went wrong");
      return false;
    }
  };
}

export default function SettingsView() {
  const { data } = useProject();
  if (data.project.myRole !== "owner") return <Navigate to={`/p/${data.project.key}`} replace />;
  return (
    <div className="settings">
      <GeneralSection />
      <MembersSection />
      <ColumnsSection />
      <LabelsSection />
    </div>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="panel settings-section">
      <header>
        <h2>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </header>
      {children}
    </section>
  );
}

function GeneralSection() {
  const { data, update } = useProject();
  const run = useRunner();
  const { project } = data;
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const dirty = name.trim() !== project.name || description !== project.description;

  async function save(event: FormEvent) {
    event.preventDefault();
    await run(async () =>
      update({ project: await api.updateProject(project.key, { name: name.trim(), description }) }),
    );
  }

  async function toggleArchive() {
    const verb = project.archived ? "Restore" : "Archive";
    if (!window.confirm(`${verb} ${project.key}?${project.archived ? "" : " It will be hidden from project lists."}`)) return;
    await run(async () =>
      update({ project: await api.updateProject(project.key, { archived: !project.archived }) }),
    );
  }

  return (
    <Section title="General">
      <form className="form-grid" onSubmit={save}>
        <label className="field">
          <span>Name</span>
          <input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="field">
          <span>Key</span>
          <input value={project.key} disabled />
          <small className="muted">Keys can't change: issue keys depend on them.</small>
        </label>
        <label className="field span-2">
          <span>Description</span>
          <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <div className="form-actions span-2 space-between">
          <button type="button" className="btn btn-ghost danger" onClick={() => void toggleArchive()}>
            {project.archived ? "Restore project" : "Archive project"}
          </button>
          <button className="btn btn-primary" disabled={!dirty || !name.trim()}>
            Save changes
          </button>
        </div>
      </form>
    </Section>
  );
}

function MembersSection() {
  const { data, update, reloadAll } = useProject();
  const { user: me } = useAuth();
  const run = useRunner();
  const [known, setKnown] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ProjectRole>("developer");
  const key = data.project.key;

  useEffect(() => {
    api.users().then(setKnown).catch(() => setKnown([]));
  }, []);

  const refreshMembers = async () => update({ members: await api.members(key) });

  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(() => api.setMember(key, { email: email.trim(), role }));
    if (ok) {
      setEmail("");
      await refreshMembers();
    }
  }

  async function changeRole(userId: number, next: ProjectRole) {
    if (await run(() => api.setMember(key, { userId, role: next }))) {
      // Demoting yourself changes what this page may show.
      if (userId === me?.id) await reloadAll();
      else await refreshMembers();
    }
  }

  async function remove(userId: number, name: string) {
    if (!window.confirm(`Remove ${name} from ${key}?`)) return;
    if (await run(() => api.removeMember(key, userId))) {
      if (userId === me?.id) await reloadAll();
      else await refreshMembers();
    }
  }

  const memberIds = new Set(data.members.map((m) => m.user.id));
  const suggestions = known.filter((u) => u.isActive && !memberIds.has(u.id));

  return (
    <Section title="Members" description="People who can see this project, and what they can do.">
      <table className="table">
        <thead>
          <tr>
            <th>Person</th>
            <th>Role</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {data.members.map((m) => (
            <tr key={m.user.id}>
              <td>
                <div className="person">
                  <Avatar user={m.user} size={28} />
                  <div>
                    <div>
                      {m.user.name}
                      {m.user.id === me?.id && <span className="muted"> (you)</span>}
                    </div>
                    <div className="muted small">{m.user.email}</div>
                  </div>
                </div>
              </td>
              <td>
                <select
                  value={m.role}
                  aria-label={`Role for ${m.user.name}`}
                  onChange={(e) => void changeRole(m.user.id, e.target.value as ProjectRole)}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </td>
              <td className="cell-actions">
                <button className="btn btn-ghost btn-sm danger" onClick={() => void remove(m.user.id, m.user.name)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="inline-form" onSubmit={add}>
        <input
          type="email"
          placeholder="Email of an existing user"
          value={email}
          list="member-suggestions"
          onChange={(e) => setEmail(e.target.value)}
          required
          aria-label="Email"
        />
        <datalist id="member-suggestions">
          {suggestions.map((u) => (
            <option key={u.id} value={u.email}>
              {u.name}
            </option>
          ))}
        </datalist>
        <select value={role} onChange={(e) => setRole(e.target.value as ProjectRole)} aria-label="Role">
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button className="btn btn-primary btn-sm">Add member</button>
      </form>
      <ul className="role-legend">
        {ROLES.map((r) => (
          <li key={r.value}>
            <strong>{r.label}</strong> <span className="muted">· {r.hint}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function ColumnsSection() {
  const { data, update } = useProject();
  const run = useRunner();
  const key = data.project.key;
  const [name, setName] = useState("");
  const [category, setCategory] = useState<ColumnCategory>("in_progress");
  const counts = new Map<number, number>();
  data.issues.forEach((i) => counts.set(i.columnId, (counts.get(i.columnId) ?? 0) + 1));

  const replace = (column: BoardColumn) =>
    update({ columns: data.columns.map((c) => (c.id === column.id ? column : c)) });

  async function edit(column: BoardColumn, patch: Partial<Pick<BoardColumn, "name" | "category" | "wipLimit">>) {
    await run(async () => replace(await api.updateColumn(key, column.id, patch)));
  }

  async function move(index: number, delta: number) {
    const ids = data.columns.map((c) => c.id);
    const [moved] = ids.splice(index, 1);
    ids.splice(index + delta, 0, moved);
    await run(async () => update({ columns: await api.reorderColumns(key, ids) }));
  }

  async function remove(column: BoardColumn) {
    if (!window.confirm(`Delete the "${column.name}" column?`)) return;
    if (await run(() => api.deleteColumn(key, column.id))) update({ columns: await api.columns(key) });
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(async () =>
      update({ columns: [...data.columns, await api.createColumn(key, { name: name.trim(), category })] }),
    );
    if (ok) setName("");
  }

  return (
    <Section
      title="Board columns"
      description="Issues in a column marked Done count as finished, and stop blocking other issues."
    >
      <table className="table">
        <thead>
          <tr>
            <th>Order</th>
            <th>Name</th>
            <th>Category</th>
            <th>WIP limit</th>
            <th>Issues</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {data.columns.map((column, index) => (
            <tr key={column.id}>
              <td className="cell-order">
                <button
                  className="icon-button small"
                  aria-label={`Move ${column.name} earlier`}
                  disabled={index === 0}
                  onClick={() => void move(index, -1)}
                >
                  ↑
                </button>
                <button
                  className="icon-button small"
                  aria-label={`Move ${column.name} later`}
                  disabled={index === data.columns.length - 1}
                  onClick={() => void move(index, 1)}
                >
                  ↓
                </button>
              </td>
              <td>
                <CommitInput
                  value={column.name}
                  ariaLabel="Column name"
                  maxLength={60}
                  onCommit={(v) => v.trim() && edit(column, { name: v.trim() })}
                />
              </td>
              <td>
                <select
                  value={column.category}
                  aria-label={`Category for ${column.name}`}
                  onChange={(e) => void edit(column, { category: e.target.value as ColumnCategory })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <CommitInput
                  value={column.wipLimit?.toString() ?? ""}
                  ariaLabel={`WIP limit for ${column.name}`}
                  type="number"
                  placeholder="None"
                  className="narrow"
                  onCommit={(v) => edit(column, { wipLimit: v ? Math.max(1, Number(v)) : null })}
                />
              </td>
              <td className="muted">{counts.get(column.id) ?? 0}</td>
              <td className="cell-actions">
                <button
                  className="btn btn-ghost btn-sm danger"
                  disabled={(counts.get(column.id) ?? 0) > 0 || data.columns.length <= 1}
                  title={(counts.get(column.id) ?? 0) > 0 ? "Move its issues out first" : undefined}
                  onClick={() => void remove(column)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="inline-form" onSubmit={add}>
        <input placeholder="New column" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} required aria-label="Column name" />
        <select value={category} onChange={(e) => setCategory(e.target.value as ColumnCategory)} aria-label="Category">
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <button className="btn btn-primary btn-sm">Add column</button>
      </form>
    </Section>
  );
}

const LABEL_COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#6b7280"];

function LabelsSection() {
  const { data, update, reloadIssues } = useProject();
  const run = useRunner();
  const key = data.project.key;
  const [name, setName] = useState("");
  const [color, setColor] = useState(LABEL_COLORS[0]);
  const used = new Map<number, number>();
  data.issues.forEach((i) => i.labels.forEach((l) => used.set(l.id, (used.get(l.id) ?? 0) + 1)));

  const sorted = (labels: Label[]) => [...labels].sort((a, b) => a.name.localeCompare(b.name));

  async function edit(label: Label, patch: { name?: string; color?: string }) {
    const ok = await run(async () => {
      const saved = await api.updateLabel(key, label.id, patch);
      update({ labels: sorted(data.labels.map((l) => (l.id === saved.id ? saved : l))) });
    });
    if (ok) await reloadIssues();
  }

  async function remove(label: Label) {
    const n = used.get(label.id) ?? 0;
    if (!window.confirm(`Delete "${label.name}"?${n ? ` It will be removed from ${n} issue(s).` : ""}`)) return;
    if (await run(() => api.deleteLabel(key, label.id))) {
      update({ labels: data.labels.filter((l) => l.id !== label.id) });
      await reloadIssues();
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(async () =>
      update({ labels: sorted([...data.labels, await api.createLabel(key, name.trim(), color)]) }),
    );
    if (ok) {
      setName("");
      setColor(LABEL_COLORS[(data.labels.length + 1) % LABEL_COLORS.length]);
    }
  }

  return (
    <Section title="Labels" description="Tags for filtering issues, such as areas, modules or phases.">
      {data.labels.length === 0 ? (
        <p className="muted">No labels yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Preview</th>
              <th>Name</th>
              <th>Colour</th>
              <th>Issues</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {data.labels.map((label) => (
              <tr key={label.id}>
                <td>
                  <LabelChip label={label} />
                </td>
                <td>
                  <CommitInput
                    value={label.name}
                    ariaLabel="Label name"
                    maxLength={50}
                    onCommit={(v) => v.trim() && edit(label, { name: v.trim() })}
                  />
                </td>
                <td>
                  <input
                    type="color"
                    className="color-input"
                    value={label.color}
                    aria-label={`Colour for ${label.name}`}
                    onChange={(e) => void edit(label, { color: e.target.value })}
                  />
                </td>
                <td className="muted">{used.get(label.id) ?? 0}</td>
                <td className="cell-actions">
                  <button className="btn btn-ghost btn-sm danger" onClick={() => void remove(label)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form className="inline-form" onSubmit={add}>
        <input
          type="color"
          className="color-input"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          aria-label="New label colour"
        />
        <input placeholder="New label" value={name} maxLength={50} onChange={(e) => setName(e.target.value)} required aria-label="Label name" />
        <button className="btn btn-primary btn-sm">Add label</button>
      </form>
    </Section>
  );
}

/** Text input that saves on blur or Enter, and reverts on Escape. */
function CommitInput({
  value,
  onCommit,
  ariaLabel,
  type = "text",
  placeholder,
  maxLength,
  className,
}: {
  value: string;
  onCommit: (value: string) => unknown;
  ariaLabel: string;
  type?: "text" | "number";
  placeholder?: string;
  maxLength?: number;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const commit = () => {
    if (draft !== value) void onCommit(draft);
  };
  return (
    <input
      type={type}
      min={type === "number" ? 1 : undefined}
      value={draft}
      placeholder={placeholder}
      maxLength={maxLength}
      aria-label={ariaLabel}
      className={className}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") setDraft(value);
      }}
    />
  );
}
