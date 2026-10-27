import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatDateTime, PRIORITY_LABEL, TYPE_LABEL } from "../lib/format";
import { canComment, canEditDescription, canEditIssues, canMoveIssue } from "../lib/permissions";
import {
  ISSUE_TYPES,
  PRIORITIES,
  type Activity,
  type Comment,
  type IssueDetail,
  type IssueLink,
  type IssueUpdate,
  type Label,
} from "../lib/types";
import type { ProjectData } from "../pages/project/ProjectLayout";
import { Avatar } from "./Avatar";
import { LabelChip, PriorityIcon, TypeIcon } from "./IssueBadges";

interface Props {
  issueKey: string;
  data: ProjectData;
  onClose: () => void;
  onOpen: (key: string) => void;
  onChanged: () => void;
  onLabelsChanged: (labels: Label[]) => void;
}

export default function IssueDrawer({ issueKey, data, onClose, onOpen, onChanged, onLabelsChanged }: Props) {
  const [issue, setIssue] = useState<IssueDetail | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"comments" | "history">("comments");
  const role = data.project.myRole;

  const load = useCallback(() => {
    api
      .issue(issueKey)
      .then(setIssue)
      .catch((err: Error) => setError(err.message));
  }, [issueKey]);

  useEffect(load, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !(e.target as HTMLElement).closest("input, textarea, select")) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save(patch: IssueUpdate) {
    setError("");
    try {
      setIssue(await api.updateIssue(issueKey, patch));
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    }
  }

  async function move(columnId: number) {
    setError("");
    try {
      // A large index appends to the end of the target column.
      setIssue(await api.moveIssue(issueKey, columnId, 1_000_000));
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not move");
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${issueKey}? This cannot be undone.`)) return;
    try {
      await api.deleteIssue(issueKey);
      onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete");
    }
  }

  const editable = canEditIssues(role);

  return (
    <div className="drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Issue ${issueKey}`}>
        <header className="drawer-header">
          {issue && <TypeIcon type={issue.type} />}
          <span className="drawer-key">{issueKey}</span>
          <span className="flex-spacer" />
          {issue && editable && (
            <button className="btn btn-ghost btn-sm danger" onClick={() => void remove()}>
              Delete
            </button>
          )}
          <button className="icon-button" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        {error && <div className="form-error drawer-error">{error}</div>}
        {!issue ? (
          !error && <div className="drawer-loading muted">Loading…</div>
        ) : (
          <div className="drawer-content">
            <div className="drawer-main">
              <EditableTitle value={issue.title} editable={editable} onSave={(title) => save({ title })} />
              {issue.blocked && (
                <div className="blocked-banner">
                  <strong>Blocked</strong>
                  {issue.blockedBy.length > 0 && (
                    <span>
                      {" "}
                      by{" "}
                      {issue.blockedBy.map((k, i) => (
                        <span key={k}>
                          {i > 0 && ", "}
                          <button className="link-button" onClick={() => onOpen(k)}>
                            {k}
                          </button>
                        </span>
                      ))}
                    </span>
                  )}
                  {issue.isBlocked && issue.blockedReason && <span> · {issue.blockedReason}</span>}
                </div>
              )}
              <Description
                value={issue.description}
                editable={canEditDescription(role, issue)}
                onSave={(description) => save({ description })}
              />
              <LinksSection issue={issue} editable={editable} onOpen={onOpen} reload={load} onChanged={onChanged} />
              {issue.children.length > 0 && (
                <section className="drawer-section">
                  <h3>Child issues</h3>
                  <ul className="ref-list">
                    {issue.children.map((child) => (
                      <li key={child.key}>
                        <TypeIcon type={child.type} />
                        <button className={`link-button${child.done ? " done" : ""}`} onClick={() => onOpen(child.key)}>
                          {child.key}
                        </button>
                        <span className="ref-title">{child.title}</span>
                        <span className="muted">{data.columns.find((c) => c.id === child.columnId)?.name}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              <div className="tabs" role="tablist">
                <button role="tab" aria-selected={tab === "comments"} className={tab === "comments" ? "active" : ""} onClick={() => setTab("comments")}>
                  Comments
                </button>
                <button role="tab" aria-selected={tab === "history"} className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
                  History
                </button>
              </div>
              {tab === "comments" ? (
                <Comments issueKey={issueKey} canPost={canComment(role)} isOwner={role === "owner"} />
              ) : (
                <History issueKey={issueKey} version={issue.updatedAt} />
              )}
            </div>

            <div className="drawer-side">
              <Field label="Status">
                <select
                  value={issue.columnId}
                  disabled={!canMoveIssue(role, issue)}
                  onChange={(e) => void move(Number(e.target.value))}
                >
                  {data.columns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Assignee">
                <div className="with-avatar">
                  <Avatar user={issue.assignee} size={24} />
                  <select
                    value={issue.assignee?.id ?? ""}
                    disabled={!editable}
                    onChange={(e) => void save({ assigneeId: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">Unassigned</option>
                    {data.members.map((m) => (
                      <option key={m.user.id} value={m.user.id}>
                        {m.user.name}
                      </option>
                    ))}
                  </select>
                </div>
              </Field>
              <Field label="Priority">
                <div className="with-avatar">
                  <PriorityIcon priority={issue.priority} />
                  <select
                    value={issue.priority}
                    disabled={!editable}
                    onChange={(e) => void save({ priority: e.target.value as IssueDetail["priority"] })}
                  >
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {PRIORITY_LABEL[p]}
                      </option>
                    ))}
                  </select>
                </div>
              </Field>
              <Field label="Type">
                <select
                  value={issue.type}
                  disabled={!editable}
                  onChange={(e) => void save({ type: e.target.value as IssueDetail["type"] })}
                >
                  {ISSUE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABEL[t]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Labels">
                <LabelPicker
                  projectKey={data.project.key}
                  all={data.labels}
                  selected={issue.labels}
                  editable={editable}
                  onChange={(ids) => void save({ labelIds: ids })}
                  onLabelsChanged={onLabelsChanged}
                />
              </Field>
              <Field label="Due date">
                <input
                  type="date"
                  value={issue.dueDate ?? ""}
                  disabled={!editable}
                  onChange={(e) => void save({ dueDate: e.target.value || null })}
                />
              </Field>
              <Field label="Parent">
                <ParentField
                  value={issue.parentKey}
                  editable={editable}
                  onSave={(parentKey) => save({ parentKey })}
                  onOpen={onOpen}
                />
              </Field>
              <Field label="Blocked">
                <BlockedField issue={issue} editable={editable} onSave={save} />
              </Field>
              <dl className="meta-list">
                <dt>Reporter</dt>
                <dd>{issue.reporter?.name ?? "—"}</dd>
                <dt>Created</dt>
                <dd>{formatDateTime(issue.createdAt)}</dd>
                <dt>Updated</dt>
                <dd>{formatDateTime(issue.updatedAt)}</dd>
              </dl>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="side-field">
      <div className="side-label">{label}</div>
      {children}
    </div>
  );
}

function EditableTitle({
  value,
  editable,
  onSave,
}: {
  value: string;
  editable: boolean;
  onSave: (v: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null) {
    return (
      <h2
        className={`drawer-title${editable ? " editable" : ""}`}
        onClick={() => editable && setDraft(value)}
        tabIndex={editable ? 0 : undefined}
        onKeyDown={(e) => editable && e.key === "Enter" && setDraft(value)}
      >
        {value}
      </h2>
    );
  }
  const commit = () => {
    const next = draft.trim();
    setDraft(null);
    if (next && next !== value) void onSave(next);
  };
  return (
    <input
      className="drawer-title-input"
      value={draft}
      autoFocus
      maxLength={255}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") setDraft(null);
      }}
    />
  );
}

function Description({
  value,
  editable,
  onSave,
}: {
  value: string;
  editable: boolean;
  onSave: (v: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <section className="drawer-section">
      <div className="section-head">
        <h3>Description</h3>
        {editable && draft === null && (
          <button className="btn btn-ghost btn-sm" onClick={() => setDraft(value)}>
            Edit
          </button>
        )}
      </div>
      {draft === null ? (
        value ? (
          <div className="description">{value}</div>
        ) : (
          <p className="muted">{editable ? "No description yet." : "No description."}</p>
        )
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void onSave(draft).then(() => setDraft(null));
          }}
        >
          <textarea
            className="description-input"
            rows={8}
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="form-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft(null)}>
              Cancel
            </button>
            <button className="btn btn-primary btn-sm">Save</button>
          </div>
        </form>
      )}
    </section>
  );
}

const LINK_PHRASE = {
  blocks: { outward: "blocks", inward: "is blocked by" },
  relates: { outward: "relates to", inward: "relates to" },
} as const;

function LinksSection({
  issue,
  editable,
  onOpen,
  reload,
  onChanged,
}: {
  issue: IssueDetail;
  editable: boolean;
  onOpen: (key: string) => void;
  reload: () => void;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [kind, setKind] = useState<"blocks" | "blocked_by" | "relates">("blocks");
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");

  async function add(event: FormEvent) {
    event.preventDefault();
    const other = target.trim().toUpperCase();
    setError("");
    try {
      if (kind === "blocked_by") await api.addLink(other, "blocks", issue.key);
      else await api.addLink(issue.key, kind, other);
      setTarget("");
      setAdding(false);
      reload();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add link");
    }
  }

  async function remove(link: IssueLink) {
    try {
      await api.removeLink(link.id);
      reload();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove link");
    }
  }

  if (issue.links.length === 0 && !editable) return null;

  return (
    <section className="drawer-section">
      <div className="section-head">
        <h3>Linked issues</h3>
        {editable && !adding && (
          <button className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>
            Add link
          </button>
        )}
      </div>
      {issue.links.length === 0 && !adding && <p className="muted">No linked issues.</p>}
      <ul className="ref-list">
        {issue.links.map((link) => (
          <li key={link.id}>
            <span className="link-phrase">{LINK_PHRASE[link.type][link.direction]}</span>
            <TypeIcon type={link.issue.type} />
            <button className={`link-button${link.issue.done ? " done" : ""}`} onClick={() => onOpen(link.issue.key)}>
              {link.issue.key}
            </button>
            <span className="ref-title">{link.issue.title}</span>
            {editable && (
              <button className="icon-button small" aria-label="Remove link" onClick={() => void remove(link)}>
                ✕
              </button>
            )}
          </li>
        ))}
      </ul>
      {adding && (
        <form className="inline-form" onSubmit={add}>
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} aria-label="Link type">
            <option value="blocks">blocks</option>
            <option value="blocked_by">is blocked by</option>
            <option value="relates">relates to</option>
          </select>
          <input
            placeholder={`${issue.projectKey}-1`}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            aria-label="Issue key"
            required
            autoFocus
          />
          <button className="btn btn-primary btn-sm">Link</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(false)}>
            Cancel
          </button>
        </form>
      )}
      {error && <div className="form-error">{error}</div>}
    </section>
  );
}

function LabelPicker({
  projectKey,
  all,
  selected,
  editable,
  onChange,
  onLabelsChanged,
}: {
  projectKey: string;
  all: Label[];
  selected: Label[];
  editable: boolean;
  onChange: (ids: number[]) => void;
  onLabelsChanged: (labels: Label[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const selectedIds = new Set(selected.map((l) => l.id));

  if (!editable) {
    return selected.length ? (
      <div className="chip-row">
        {selected.map((l) => (
          <LabelChip key={l.id} label={l} />
        ))}
      </div>
    ) : (
      <span className="muted">None</span>
    );
  }

  function toggle(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange([...next]);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const colors = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777"];
    const label = await api.createLabel(projectKey, name.trim(), colors[all.length % colors.length]);
    onLabelsChanged([...all, label].sort((a, b) => a.name.localeCompare(b.name)));
    setName("");
    onChange([...selectedIds, label.id]);
  }

  return (
    <div>
      <button className="chip-row chip-button" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {selected.length ? selected.map((l) => <LabelChip key={l.id} label={l} />) : <span className="muted">None</span>}
      </button>
      {open && (
        <div className="label-picker">
          {all.map((l) => (
            <label key={l.id} className="label-option">
              <input type="checkbox" checked={selectedIds.has(l.id)} onChange={() => toggle(l.id)} />
              <LabelChip label={l} />
            </label>
          ))}
          <form className="inline-form" onSubmit={(e) => void create(e).catch(() => undefined)}>
            <input placeholder="New label" value={name} maxLength={50} onChange={(e) => setName(e.target.value)} />
            <button className="btn btn-sm" disabled={!name.trim()}>
              Add
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function ParentField({
  value,
  editable,
  onSave,
  onOpen,
}: {
  value: string | null;
  editable: boolean;
  onSave: (v: string | null) => Promise<void>;
  onOpen: (key: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null) {
    return (
      <div className="with-avatar">
        {value ? (
          <button className="link-button" onClick={() => onOpen(value)}>
            {value}
          </button>
        ) : (
          <span className="muted">None</span>
        )}
        {editable && (
          <button className="btn btn-ghost btn-sm" onClick={() => setDraft(value ?? "")}>
            Change
          </button>
        )}
      </div>
    );
  }
  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        const key = draft.trim().toUpperCase();
        setDraft(null);
        if (key !== (value ?? "")) void onSave(key || null);
      }}
    >
      <input value={draft} placeholder="Epic key, empty for none" autoFocus onChange={(e) => setDraft(e.target.value)} />
      <button className="btn btn-sm">Save</button>
    </form>
  );
}

function BlockedField({
  issue,
  editable,
  onSave,
}: {
  issue: IssueDetail;
  editable: boolean;
  onSave: (patch: IssueUpdate) => Promise<void>;
}) {
  const [reason, setReason] = useState(issue.blockedReason);
  useEffect(() => setReason(issue.blockedReason), [issue.blockedReason]);
  return (
    <div className="blocked-field">
      <label className="toggle">
        <input
          type="checkbox"
          checked={issue.isBlocked}
          disabled={!editable}
          onChange={(e) => void onSave({ isBlocked: e.target.checked })}
        />
        Flag as blocked
      </label>
      {issue.isBlocked && (
        <input
          placeholder="Reason"
          value={reason}
          disabled={!editable}
          onChange={(e) => setReason(e.target.value)}
          onBlur={() => reason !== issue.blockedReason && void onSave({ blockedReason: reason })}
        />
      )}
      {issue.blockedBy.length > 0 && (
        <small className="muted">Blocked by open issue{issue.blockedBy.length > 1 && "s"} {issue.blockedBy.join(", ")}</small>
      )}
    </div>
  );
}

function Comments({ issueKey, canPost, isOwner }: { issueKey: string; canPost: boolean; isOwner: boolean }) {
  const { user } = useAuth();
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [body, setBody] = useState("");
  const [editing, setEditing] = useState<{ id: number; body: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.comments(issueKey).then(setComments).catch((err: Error) => setError(err.message));
  }, [issueKey]);
  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <section className="comments">
      {canPost && (
        <form
          className="comment-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (body.trim()) void run(() => api.addComment(issueKey, body.trim())).then(() => setBody(""));
          }}
        >
          <textarea rows={3} placeholder="Add a comment…" value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="form-actions">
            <button className="btn btn-primary btn-sm" disabled={!body.trim()}>
              Comment
            </button>
          </div>
        </form>
      )}
      {error && <div className="form-error">{error}</div>}
      {comments?.length === 0 && <p className="muted">No comments yet.</p>}
      <ul className="comment-list">
        {comments
          ?.slice()
          .reverse()
          .map((c) => {
            const mine = c.author?.id === user?.id;
            return (
              <li key={c.id} className="comment">
                <Avatar user={c.author} size={28} />
                <div className="comment-main">
                  <div className="comment-head">
                    <strong>{c.author?.name ?? "Deleted user"}</strong>
                    <span className="muted">
                      {formatDateTime(c.createdAt)}
                      {Date.parse(c.updatedAt) - Date.parse(c.createdAt) > 1000 && " (edited)"}
                    </span>
                  </div>
                  {editing?.id === c.id ? (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(() => api.editComment(c.id, editing.body)).then(() => setEditing(null));
                      }}
                    >
                      <textarea rows={3} value={editing.body} autoFocus onChange={(e) => setEditing({ id: c.id, body: e.target.value })} />
                      <div className="form-actions">
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>
                          Cancel
                        </button>
                        <button className="btn btn-primary btn-sm">Save</button>
                      </div>
                    </form>
                  ) : (
                    <div className="comment-body">{c.body}</div>
                  )}
                  {editing?.id !== c.id && (mine || isOwner) && (
                    <div className="comment-actions">
                      {mine && (
                        <button className="link-button" onClick={() => setEditing({ id: c.id, body: c.body })}>
                          Edit
                        </button>
                      )}
                      <button
                        className="link-button"
                        onClick={() => window.confirm("Delete this comment?") && void run(() => api.deleteComment(c.id))}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
      </ul>
    </section>
  );
}

const FIELD_NAMES: Record<string, string> = {
  title: "title",
  description: "description",
  type: "type",
  priority: "priority",
  assignee: "assignee",
  parent: "parent",
  due_date: "due date",
  is_blocked: "blocked flag",
  blocked_reason: "blocked reason",
  labels: "labels",
};

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "none";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
  return String(value);
}

export function describeActivity(entry: Activity): ReactNode[] {
  const d = entry.details as Record<string, unknown>;
  switch (entry.action) {
    case "issue_created":
      return ["created the issue"];
    case "issue_moved":
      return [`moved it from ${show(d.from)} to ${show(d.to)}`];
    case "comment_added":
      return ["commented"];
    case "link_added":
      return [`linked: ${show(d.type)} ${show(d.target)}`];
    case "link_removed":
      return [`removed link: ${show(d.type)} ${show(d.target)}`];
    case "issue_updated":
      return Object.entries(d).map(([field, change]) => {
        const name = FIELD_NAMES[field] ?? field;
        const c = change as { from?: unknown; to?: unknown };
        return "to" in c ? `changed ${name} from ${show(c.from)} to ${show(c.to)}` : `updated the ${name}`;
      });
    default:
      return [entry.action.replace(/_/g, " ")];
  }
}

function History({ issueKey, version }: { issueKey: string; version: string }) {
  const [entries, setEntries] = useState<Activity[] | null>(null);
  useEffect(() => {
    api.issueActivity(issueKey).then(setEntries).catch(() => setEntries([]));
  }, [issueKey, version]);
  if (!entries) return <p className="muted">Loading…</p>;
  return (
    <ul className="history-list">
      {[...entries].reverse().map((entry) =>
        describeActivity(entry).map((text, i) => (
          <li key={`${entry.id}-${i}`}>
            <Avatar user={entry.actor} size={22} />
            <span>
              <strong>{entry.actor?.name ?? "Someone"}</strong> {text}
            </span>
            <span className="muted history-time">{formatDateTime(entry.createdAt)}</span>
          </li>
        )),
      )}
    </ul>
  );
}
