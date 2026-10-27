import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { formatDate, isOverdue } from "../lib/format";
import type { Issue } from "../lib/types";
import { Avatar } from "./Avatar";
import { LabelChip, PriorityIcon, TypeIcon } from "./IssueBadges";

interface CardProps {
  issue: Issue;
  onOpen?: (key: string) => void;
  overlay?: boolean;
}

export function IssueCardBody({ issue, onOpen, overlay }: CardProps) {
  const overdue = isOverdue(issue.dueDate, issue.done);
  return (
    <div className={`issue-card${issue.blocked ? " is-blocked" : ""}${overlay ? " is-overlay" : ""}`}>
      <button
        type="button"
        className="issue-card-title"
        onClick={() => onOpen?.(issue.key)}
        // Keep Enter/Space on the title for opening; the card itself handles keyboard dragging.
        onKeyDown={(e) => e.stopPropagation()}
      >
        {issue.title}
      </button>
      {(issue.labels.length > 0 || issue.blocked || issue.dueDate) && (
        <div className="issue-card-meta">
          {issue.blocked && (
            <span
              className="blocked-badge"
              title={
                issue.blockedBy.length
                  ? `Blocked by ${issue.blockedBy.join(", ")}`
                  : issue.blockedReason || "Blocked"
              }
            >
              Blocked
            </span>
          )}
          {issue.labels.map((label) => (
            <LabelChip key={label.id} label={label} />
          ))}
          {issue.dueDate && (
            <span className={`due-chip${overdue ? " overdue" : ""}`} title="Due date">
              {formatDate(issue.dueDate)}
            </span>
          )}
        </div>
      )}
      <div className="issue-card-foot">
        <TypeIcon type={issue.type} />
        <span className={`issue-key${issue.done ? " done" : ""}`}>{issue.key}</span>
        <PriorityIcon priority={issue.priority} />
        <span className="flex-spacer" />
        {issue.parentKey && <span className="parent-chip">{issue.parentKey}</span>}
        <Avatar user={issue.assignee} size={24} />
      </div>
    </div>
  );
}

export function SortableIssueCard({
  issue,
  onOpen,
  disabled,
}: {
  issue: Issue;
  onOpen: (key: string) => void;
  disabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: issue.key,
    disabled,
  });
  return (
    <li
      ref={setNodeRef}
      className={`card-slot${isDragging ? " is-dragging" : ""}${disabled ? "" : " draggable"}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      aria-roledescription={disabled ? undefined : "draggable issue"}
    >
      <IssueCardBody issue={issue} onOpen={onOpen} />
    </li>
  );
}
