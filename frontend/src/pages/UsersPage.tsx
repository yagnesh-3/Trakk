import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Avatar } from "../components/Avatar";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { SystemRole, User } from "../lib/types";

const MIN_PASSWORD = 10;

/** A readable random temporary password the admin can pass on. */
function generatePassword(): string {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(14));
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [issued, setIssued] = useState<{ email: string; password: string } | null>(null);
  const [showInactive, setShowInactive] = useState(false);

  useEffect(() => {
    api.users().then(setUsers).catch((err: Error) => setError(err.message));
  }, []);

  if (me?.systemRole !== "admin") return <Navigate to="/" replace />;

  async function update(target: User, patch: Parameters<typeof api.updateUser>[1]) {
    setError("");
    try {
      const saved = await api.updateUser(target.id, patch);
      setUsers((prev) => prev?.map((u) => (u.id === saved.id ? saved : u)) ?? null);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update user");
      return false;
    }
  }

  async function resetPassword(target: User) {
    if (!window.confirm(`Reset ${target.name}'s password? They'll be signed out everywhere.`)) return;
    const password = generatePassword();
    if (await update(target, { password })) setIssued({ email: target.email, password });
  }

  const shown = users?.filter((u) => showInactive || u.isActive) ?? [];

  return (
    <main className="page">
      <div className="page-header">
        <h1>Users</h1>
        {!creating && (
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            New user
          </button>
        )}
      </div>
      {creating && (
        <NewUserForm
          onCancel={() => setCreating(false)}
          onCreated={(user, password) => {
            setUsers((prev) => [...(prev ?? []), user].sort((a, b) => a.name.localeCompare(b.name)));
            setIssued({ email: user.email, password });
            setCreating(false);
          }}
        />
      )}
      {issued && (
        <div className="callout" role="status">
          <div>
            <strong>Temporary password for {issued.email}</strong>
            <p className="muted">
              Share it privately. They'll be asked to choose their own password on first sign-in. It won't be shown
              again.
            </p>
            <CopyField value={issued.password} />
          </div>
          <button className="icon-button" aria-label="Dismiss" onClick={() => setIssued(null)}>
            ✕
          </button>
        </div>
      )}
      {error && <div className="form-error">{error}</div>}
      <div className="toolbar">
        <label className="toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Show deactivated users
        </label>
      </div>
      {users === null ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="table-wrap panel flush">
          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th>System role</th>
                <th>Status</th>
                <th>Created</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} className={u.isActive ? undefined : "inactive"}>
                  <td>
                    <div className="person">
                      <Avatar user={u} size={28} />
                      <div>
                        <div>
                          {u.name}
                          {u.id === me.id && <span className="muted"> (you)</span>}
                        </div>
                        <div className="muted small">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <select
                      value={u.systemRole}
                      aria-label={`System role for ${u.name}`}
                      disabled={u.id === me.id}
                      onChange={(e) => void update(u, { systemRole: e.target.value as SystemRole })}
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td>
                    {!u.isActive ? (
                      <span className="status-pill off">Deactivated</span>
                    ) : u.mustChangePassword ? (
                      <span className="status-pill pending">Password not set</span>
                    ) : (
                      <span className="status-pill on">Active</span>
                    )}
                  </td>
                  <td className="muted nowrap">{formatDate(u.createdAt)}</td>
                  <td className="cell-actions">
                    {u.id !== me.id && (
                      <>
                        <button className="btn btn-ghost btn-sm" onClick={() => void resetPassword(u)}>
                          Reset password
                        </button>
                        <button
                          className={`btn btn-ghost btn-sm${u.isActive ? " danger" : ""}`}
                          onClick={() => void update(u, { isActive: !u.isActive })}
                        >
                          {u.isActive ? "Deactivate" : "Reactivate"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">
        Admins can create projects and act as owner on every project. Everyone else only sees projects they're a member
        of. Add people to a project from its Settings tab.
      </p>
    </main>
  );
}

function NewUserForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (user: User, password: string) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<SystemRole>("member");
  const [password, setPassword] = useState(generatePassword);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters`);
    setBusy(true);
    setError("");
    try {
      onCreated(await api.createUser({ name: name.trim(), email: email.trim(), password, systemRole: role }), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create user");
      setBusy(false);
    }
  }

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <label className="field">
        <span>Name</span>
        <input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} required autoFocus />
      </label>
      <label className="field">
        <span>System role</span>
        <select value={role} onChange={(e) => setRole(e.target.value as SystemRole)}>
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>
      </label>
      <label className="field">
        <span>Email</span>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="field">
        <span>Temporary password</span>
        <input value={password} onChange={(e) => setPassword(e.target.value)} required />
        <small className="muted">They must change it on first sign-in.</small>
      </label>
      {error && <div className="form-error span-2">{error}</div>}
      <div className="form-actions span-2">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={busy}>
          Create user
        </button>
      </div>
    </form>
  );
}

export function CopyField({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="copy-field">
      <code>{value}</code>
      <button
        type="button"
        className="btn btn-sm"
        onClick={() =>
          void navigator.clipboard.writeText(value).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
          })
        }
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
