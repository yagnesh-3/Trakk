import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { Avatar } from "../../components/Avatar";
import { describeActivity } from "../../components/IssueDrawer";
import { TypeIcon } from "../../components/IssueBadges";
import { api } from "../../lib/api";
import { formatDate, formatDateTime, isOverdue, TYPE_LABEL } from "../../lib/format";
import { ISSUE_TYPES, type Issue, type ProjectSummary } from "../../lib/types";
import { useProject } from "./ProjectLayout";

export default function DashboardView() {
  const { data, openIssue } = useProject();
  const { user } = useAuth();
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [error, setError] = useState("");

  // Re-fetch whenever the issue list changes (e.g. after an edit in the drawer).
  useEffect(() => {
    api
      .summary(data.project.key)
      .then(setSummary)
      .catch((err: Error) => setError(err.message));
  }, [data.project.key, data.issues]);

  if (error) return <div className="form-error">{error}</div>;
  if (!summary) return <p className="muted">Loading…</p>;

  const open = data.issues.filter((i) => !i.done);
  const blocked = open.filter((i) => i.blocked);
  const overdue = open
    .filter((i) => isOverdue(i.dueDate, i.done))
    .sort((a, b) => (a.dueDate ?? "").localeCompare(b.dueDate ?? ""));
  const decisions = open.filter((i) => i.type === "decision");
  const mine = open.filter((i) => i.assignee?.id === user?.id);
  const done = summary.total - summary.open;

  return (
    <div className="dashboard">
      <div className="kpi-row">
        <StatTile label="Open issues" value={summary.open} note={`${done} done of ${summary.total}`} />
        <StatTile label="Blocked" value={summary.blocked} tone={summary.blocked ? "critical" : undefined} icon="⛔" />
        <StatTile label="Overdue" value={summary.overdue} tone={summary.overdue ? "warning" : undefined} icon="⏰" />
        <StatTile label="Open decisions" value={summary.openDecisions} icon="❓" />
      </div>

      <div className="dash-grid">
        <section className="panel">
          <h2 className="panel-title">Issues by status</h2>
          <BarList
            rows={summary.byColumn.map((c) => ({ id: String(c.columnId), label: c.name, value: c.count }))}
            unit="issue"
          />
        </section>
        <section className="panel">
          <h2 className="panel-title">Open issues by type</h2>
          <BarList
            rows={ISSUE_TYPES.map((t) => ({
              id: t,
              label: TYPE_LABEL[t],
              icon: <TypeIcon type={t} />,
              value: summary.byType[t] ?? 0,
            }))}
            unit="open issue"
          />
        </section>

        <IssueList title="Blocked" issues={blocked} empty="Nothing is blocked." onOpen={openIssue} showBlockers />
        <IssueList title="Overdue" issues={overdue} empty="Nothing is overdue." onOpen={openIssue} showDue />
        <IssueList
          title="Open decisions"
          issues={decisions}
          empty="No decisions waiting."
          onOpen={openIssue}
          showAssignee
        />
        <IssueList title="Assigned to me" issues={mine} empty="Nothing assigned to you." onOpen={openIssue} />

        <section className="panel span-all">
          <h2 className="panel-title">Recent activity</h2>
          {summary.recentActivity.length === 0 ? (
            <p className="muted">No activity yet.</p>
          ) : (
            <ul className="history-list">
              {summary.recentActivity.map((entry) =>
                describeActivity(entry).map((text, i) => (
                  <li key={`${entry.id}-${i}`}>
                    <Avatar user={entry.actor} size={22} />
                    <span>
                      <strong>{entry.actor?.name ?? "Someone"}</strong> {text}
                      {entry.issueKey && (
                        <>
                          {" on "}
                          <button className="link-button" onClick={() => openIssue(entry.issueKey)}>
                            {entry.issueKey}
                          </button>
                        </>
                      )}
                    </span>
                    <span className="muted history-time">{formatDateTime(entry.createdAt)}</span>
                  </li>
                )),
              )}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  note,
  tone,
  icon,
}: {
  label: string;
  value: number;
  note?: string;
  tone?: "warning" | "critical";
  icon?: string;
}) {
  return (
    <div className={`stat-tile${tone ? ` tone-${tone}` : ""}`}>
      <div className="stat-label">
        {tone && icon && <span aria-hidden="true">{icon} </span>}
        {label}
      </div>
      <div className="stat-value">{value}</div>
      {note && <div className="stat-note muted">{note}</div>}
    </div>
  );
}

/** Single-series horizontal bars: one hue, direct value labels, hover title per bar. */
function BarList({
  rows,
  unit,
}: {
  rows: { id: string; label: string; value: number; icon?: React.ReactNode }[];
  unit: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <table className="bar-list">
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} title={`${row.label}: ${row.value} ${unit}${row.value === 1 ? "" : "s"}`}>
            <th scope="row">
              <span className="with-avatar">
                {row.icon}
                {row.label}
              </span>
            </th>
            <td className="bar-cell">
              <span className="bar-track">
                {row.value > 0 && <span className="bar" style={{ width: `${(row.value / max) * 100}%` }} />}
              </span>
            </td>
            <td className="bar-value">{row.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function IssueList({
  title,
  issues,
  empty,
  onOpen,
  showDue,
  showAssignee,
  showBlockers,
}: {
  title: string;
  issues: Issue[];
  empty: string;
  onOpen: (key: string) => void;
  showDue?: boolean;
  showAssignee?: boolean;
  showBlockers?: boolean;
}) {
  return (
    <section className="panel">
      <h2 className="panel-title">
        {title} <span className="muted">{issues.length}</span>
      </h2>
      {issues.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <ul className="ref-list">
          {issues.slice(0, 8).map((issue) => (
            <li key={issue.key}>
              <TypeIcon type={issue.type} />
              <button className="link-button" onClick={() => onOpen(issue.key)}>
                {issue.key}
              </button>
              <span className="ref-title">{issue.title}</span>
              {showDue && issue.dueDate && <span className="overdue-text small">{formatDate(issue.dueDate)}</span>}
              {showBlockers && (
                <span className="muted small">
                  {issue.blockedBy.length ? `by ${issue.blockedBy.join(", ")}` : "flagged"}
                </span>
              )}
              {showAssignee && <Avatar user={issue.assignee} size={22} />}
            </li>
          ))}
          {issues.length > 8 && <li className="muted small">and {issues.length - 8} more</li>}
        </ul>
      )}
    </section>
  );
}
