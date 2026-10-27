import { useSearchParams } from "react-router-dom";
import { PRIORITY_LABEL, TYPE_LABEL } from "../lib/format";
import { ISSUE_TYPES, PRIORITIES, type Issue, type Label, type Member } from "../lib/types";

export interface Filters {
  q: string;
  type: string;
  assignee: string; // user id, "me", "none" or ""
  label: string;
  priority: string;
  blocked: boolean;
}

const KEYS = ["q", "type", "assignee", "label", "priority", "blocked"] as const;

/** Filters live in the URL so a filtered board can be shared or bookmarked. */
export function useFilters(): [Filters, (patch: Partial<Filters>) => void, () => void] {
  const [params, setParams] = useSearchParams();
  const filters: Filters = {
    q: params.get("q") ?? "",
    type: params.get("type") ?? "",
    assignee: params.get("assignee") ?? "",
    label: params.get("label") ?? "",
    priority: params.get("priority") ?? "",
    blocked: params.get("blocked") === "1",
  };
  const update = (patch: Partial<Filters>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(patch)) {
          if (value === "" || value === false) next.delete(key);
          else next.set(key, value === true ? "1" : String(value));
        }
        return next;
      },
      { replace: true },
    );
  const clear = () =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        KEYS.forEach((k) => next.delete(k));
        return next;
      },
      { replace: true },
    );
  return [filters, update, clear];
}

export function hasFilters(f: Filters) {
  return Boolean(f.q || f.type || f.assignee || f.label || f.priority || f.blocked);
}

export function matches(issue: Issue, f: Filters, meId: number): boolean {
  if (f.q) {
    const q = f.q.trim().toLowerCase();
    if (!issue.title.toLowerCase().includes(q) && !issue.key.toLowerCase().includes(q)) {
      return false;
    }
  }
  if (f.type && issue.type !== f.type) return false;
  if (f.priority && issue.priority !== f.priority) return false;
  if (f.blocked && !issue.blocked) return false;
  if (f.label && !issue.labels.some((l) => String(l.id) === f.label)) return false;
  if (f.assignee === "none" && issue.assignee) return false;
  if (f.assignee === "me" && issue.assignee?.id !== meId) return false;
  if (/^\d+$/.test(f.assignee) && String(issue.assignee?.id) !== f.assignee) return false;
  return true;
}

export function FilterBar({
  members,
  labels,
  shown,
  total,
}: {
  members: Member[];
  labels: Label[];
  shown: number;
  total: number;
}) {
  const [filters, update, clear] = useFilters();
  return (
    <div className="filter-bar">
      <input
        type="search"
        className="filter-search"
        placeholder="Search issues"
        aria-label="Search issues"
        value={filters.q}
        onChange={(e) => update({ q: e.target.value })}
      />
      <select
        aria-label="Assignee"
        value={filters.assignee}
        onChange={(e) => update({ assignee: e.target.value })}
      >
        <option value="">Any assignee</option>
        <option value="me">Assigned to me</option>
        <option value="none">Unassigned</option>
        {members.map((m) => (
          <option key={m.user.id} value={m.user.id}>
            {m.user.name}
          </option>
        ))}
      </select>
      <select aria-label="Type" value={filters.type} onChange={(e) => update({ type: e.target.value })}>
        <option value="">Any type</option>
        {ISSUE_TYPES.map((t) => (
          <option key={t} value={t}>
            {TYPE_LABEL[t]}
          </option>
        ))}
      </select>
      <select
        aria-label="Priority"
        value={filters.priority}
        onChange={(e) => update({ priority: e.target.value })}
      >
        <option value="">Any priority</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {PRIORITY_LABEL[p]}
          </option>
        ))}
      </select>
      {labels.length > 0 && (
        <select
          aria-label="Label"
          value={filters.label}
          onChange={(e) => update({ label: e.target.value })}
        >
          <option value="">Any label</option>
          {labels.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      )}
      <label className="toggle">
        <input
          type="checkbox"
          checked={filters.blocked}
          onChange={(e) => update({ blocked: e.target.checked })}
        />
        Blocked only
      </label>
      {hasFilters(filters) && (
        <>
          <span className="muted filter-count">
            {shown} of {total}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={clear}>
            Clear
          </button>
        </>
      )}
    </div>
  );
}
