import { useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { Avatar } from "../../components/Avatar";
import { FilterBar, matches, useFilters } from "../../components/FilterBar";
import { LabelChip, PriorityIcon, TypeIcon } from "../../components/IssueBadges";
import { api } from "../../lib/api";
import { formatDate, isOverdue, PRIORITY_LABEL } from "../../lib/format";
import { canEditIssues } from "../../lib/permissions";
import { PRIORITIES, type Issue } from "../../lib/types";
import { useProject } from "./ProjectLayout";

type SortKey = "key" | "title" | "status" | "assignee" | "priority" | "due" | "updated";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "key", label: "Key" },
  { key: "title", label: "Title" },
  { key: "status", label: "Status" },
  { key: "assignee", label: "Assignee" },
  { key: "priority", label: "Priority" },
  { key: "due", label: "Due" },
  { key: "updated", label: "Updated" },
];

export default function ListView() {
  const { data, reloadIssues, openIssue, notify } = useProject();
  const { user } = useAuth();
  const [filters] = useFilters();
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "key", desc: false });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const editable = canEditIssues(data.project.myRole);

  const columnIndex = useMemo(() => new Map(data.columns.map((c, i) => [c.id, i])), [data.columns]);
  const columnName = useMemo(() => new Map(data.columns.map((c) => [c.id, c.name])), [data.columns]);

  const rows = useMemo(() => {
    const value = (i: Issue): string | number => {
      switch (sort.key) {
        case "key":
          return i.number;
        case "title":
          return i.title.toLowerCase();
        case "status":
          return (columnIndex.get(i.columnId) ?? 0) * 1e6 + i.position;
        case "assignee":
          return i.assignee?.name.toLowerCase() ?? "￿";
        case "priority":
          return PRIORITIES.indexOf(i.priority);
        case "due":
          return i.dueDate ?? "9999";
        case "updated":
          return -Date.parse(i.updatedAt);
      }
    };
    const filtered = user ? data.issues.filter((i) => matches(i, filters, user.id)) : [];
    return filtered.sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : a.number - b.number;
      return sort.desc ? -cmp : cmp;
    });
  }, [data.issues, filters, sort, user, columnIndex]);

  const visibleSelected = rows.filter((r) => selected.has(r.key));
  const allSelected = rows.length > 0 && visibleSelected.length === rows.length;

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function bulk(label: string, action: (issue: Issue) => Promise<unknown>) {
    setBusy(true);
    let failed = 0;
    for (const issue of visibleSelected) {
      try {
        await action(issue);
      } catch {
        failed += 1;
      }
    }
    await reloadIssues();
    setSelected(new Set());
    setBusy(false);
    notify(
      failed
        ? `${label}: ${visibleSelected.length - failed} updated, ${failed} failed`
        : `${label}: ${visibleSelected.length} issue(s) updated`,
    );
  }

  return (
    <>
      <FilterBar members={data.members} labels={data.labels} shown={rows.length} total={data.issues.length} />
      {editable && visibleSelected.length > 0 && (
        <div className="bulk-bar" role="region" aria-label="Bulk actions">
          <strong>{visibleSelected.length} selected</strong>
          <select
            aria-label="Move selected to"
            value=""
            disabled={busy}
            onChange={(e) => {
              const columnId = Number(e.target.value);
              void bulk("Moved", (i) =>
                i.columnId === columnId ? Promise.resolve() : api.moveIssue(i.key, columnId, 1_000_000),
              );
            }}
          >
            <option value="" disabled>
              Move to…
            </option>
            {data.columns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Assign selected to"
            value=""
            disabled={busy}
            onChange={(e) => {
              const assigneeId = e.target.value === "none" ? null : Number(e.target.value);
              void bulk("Assigned", (i) => api.updateIssue(i.key, { assigneeId }));
            }}
          >
            <option value="" disabled>
              Assign to…
            </option>
            <option value="none">Unassigned</option>
            {data.members.map((m) => (
              <option key={m.user.id} value={m.user.id}>
                {m.user.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Set priority of selected"
            value=""
            disabled={busy}
            onChange={(e) => {
              const priority = e.target.value as Issue["priority"];
              void bulk("Priority set", (i) => api.updateIssue(i.key, { priority }));
            }}
          >
            <option value="" disabled>
              Priority…
            </option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABEL[p]}
              </option>
            ))}
          </select>
          <button className="btn btn-ghost btn-sm" onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
        </div>
      )}
      <div className="table-wrap">
        <table className="table issue-table">
          <thead>
            <tr>
              {editable && (
                <th className="cell-check">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={allSelected}
                    onChange={() => setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.key)))}
                  />
                </th>
              )}
              {COLUMNS.map((col) => (
                <th key={col.key} aria-sort={sort.key === col.key ? (sort.desc ? "descending" : "ascending") : "none"}>
                  <button
                    className="sort-button"
                    onClick={() => setSort((s) => ({ key: col.key, desc: s.key === col.key ? !s.desc : false }))}
                  >
                    {col.label}
                    <span className="sort-arrow" aria-hidden="true">
                      {sort.key === col.key ? (sort.desc ? "▼" : "▲") : ""}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length + 1} className="muted empty-row">
                  No issues match.
                </td>
              </tr>
            )}
            {rows.map((issue) => (
              <tr key={issue.key} className={selected.has(issue.key) ? "selected" : undefined}>
                {editable && (
                  <td className="cell-check">
                    <input
                      type="checkbox"
                      aria-label={`Select ${issue.key}`}
                      checked={selected.has(issue.key)}
                      onChange={() => toggle(issue.key)}
                    />
                  </td>
                )}
                <td className="nowrap">
                  <span className="with-avatar">
                    <TypeIcon type={issue.type} />
                    <span className={`issue-key${issue.done ? " done" : ""}`}>{issue.key}</span>
                  </span>
                </td>
                <td className="cell-title">
                  <button className="link-button title-link" onClick={() => openIssue(issue.key)}>
                    {issue.title}
                  </button>
                  <span className="chip-row inline-chips">
                    {issue.blocked && <span className="blocked-badge">Blocked</span>}
                    {issue.labels.map((l) => (
                      <LabelChip key={l.id} label={l} />
                    ))}
                  </span>
                </td>
                <td className="nowrap">{columnName.get(issue.columnId)}</td>
                <td className="nowrap">
                  {issue.assignee ? (
                    <span className="with-avatar">
                      <Avatar user={issue.assignee} size={22} />
                      {issue.assignee.name}
                    </span>
                  ) : (
                    <span className="muted">Unassigned</span>
                  )}
                </td>
                <td className="nowrap">
                  <span className="with-avatar">
                    <PriorityIcon priority={issue.priority} />
                    {PRIORITY_LABEL[issue.priority]}
                  </span>
                </td>
                <td className={`nowrap${isOverdue(issue.dueDate, issue.done) ? " overdue-text" : ""}`}>
                  {issue.dueDate ? formatDate(issue.dueDate) : <span className="muted">—</span>}
                </td>
                <td className="nowrap muted">{formatDate(issue.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
