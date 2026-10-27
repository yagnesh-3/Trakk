import { PRIORITY_LABEL, TYPE_LABEL } from "../lib/format";
import type { IssueType, Label, Priority } from "../lib/types";

const TYPE_GLYPH: Record<IssueType, string> = {
  epic: "E",
  story: "S",
  task: "T",
  bug: "B",
  decision: "D",
};

export function TypeIcon({ type }: { type: IssueType }) {
  return (
    <span className={`type-icon type-${type}`} title={TYPE_LABEL[type]} aria-label={TYPE_LABEL[type]}>
      {TYPE_GLYPH[type]}
    </span>
  );
}

const PRIORITY_ARROW: Record<Priority, string> = {
  highest: "⇈",
  high: "↑",
  medium: "=",
  low: "↓",
  lowest: "⇊",
};

export function PriorityIcon({ priority }: { priority: Priority }) {
  return (
    <span
      className={`priority-icon priority-${priority}`}
      title={`${PRIORITY_LABEL[priority]} priority`}
      aria-label={`${PRIORITY_LABEL[priority]} priority`}
    >
      {PRIORITY_ARROW[priority]}
    </span>
  );
}

export function LabelChip({ label }: { label: Label }) {
  return (
    <span className="label-chip" style={{ "--label": label.color } as React.CSSProperties}>
      {label.name}
    </span>
  );
}
