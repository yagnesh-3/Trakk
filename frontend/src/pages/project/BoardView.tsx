import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { FilterBar, matches, useFilters } from "../../components/FilterBar";
import { IssueCardBody, SortableIssueCard } from "../../components/IssueCard";
import { api } from "../../lib/api";
import { canEditIssues, canMoveIssue } from "../../lib/permissions";
import type { BoardColumn, Issue } from "../../lib/types";
import { useProject, type ProjectData } from "./ProjectLayout";

type Containers = Record<number, string[]>;

const columnDropId = (id: number) => `col-${id}`;

export default function BoardView() {
  const { data, update, reloadIssues, openIssue, notify } = useProject();
  const { user } = useAuth();
  const [filters] = useFilters();
  if (!user) return null;
  const visible = data.issues.filter((i) => matches(i, filters, user.id));

  return (
    <>
      <FilterBar
        members={data.members}
        labels={data.labels}
        shown={visible.length}
        total={data.issues.length}
      />
      <Board
        data={data}
        visible={visible}
        onOpen={openIssue}
        onIssuesChanged={(issues) => update({ issues })}
        reload={reloadIssues}
        onError={notify}
      />
    </>
  );
}

function groupByColumn(columns: BoardColumn[], issues: Issue[]): Containers {
  const groups: Containers = Object.fromEntries(columns.map((c) => [c.id, [] as string[]]));
  [...issues]
    .sort((a, b) => a.position - b.position || a.number - b.number)
    .forEach((issue) => groups[issue.columnId]?.push(issue.key));
  return groups;
}

function Board({
  data,
  visible,
  onOpen,
  onIssuesChanged,
  reload,
  onError,
}: {
  data: ProjectData;
  visible: Issue[];
  onOpen: (key: string) => void;
  onIssuesChanged: (issues: Issue[]) => void;
  reload: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const role = data.project.myRole;
  const byKey = useMemo(() => new Map(data.issues.map((i) => [i.key, i])), [data.issues]);
  const visibleGroups = useMemo(() => groupByColumn(data.columns, visible), [data.columns, visible]);
  // While dragging, cards move between containers locally; null otherwise.
  const [dragGroups, setDragGroups] = useState<Containers | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const groups = dragGroups ?? visibleGroups;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function containerOf(id: string, source: Containers): number | undefined {
    if (id.startsWith("col-")) return Number(id.slice(4));
    const entry = Object.entries(source).find(([, keys]) => keys.includes(id));
    return entry ? Number(entry[0]) : undefined;
  }

  function onDragStart({ active }: DragStartEvent) {
    setActiveKey(String(active.id));
    setDragGroups(structuredClone(visibleGroups));
  }

  function onDragOver({ active, over }: DragOverEvent) {
    if (!over || !dragGroups) return;
    const activeId = String(active.id);
    const overId = String(over.id);
    const from = containerOf(activeId, dragGroups);
    const to = containerOf(overId, dragGroups);
    if (from === undefined || to === undefined || from === to) return;
    setDragGroups((prev) => {
      if (!prev) return prev;
      const source = prev[from].filter((k) => k !== activeId);
      const target = [...prev[to]];
      const overIndex = target.indexOf(overId);
      target.splice(overIndex >= 0 ? overIndex : target.length, 0, activeId);
      return { ...prev, [from]: source, [to]: target };
    });
  }

  function onDragCancel() {
    setActiveKey(null);
    setDragGroups(null);
  }

  async function onDragEnd({ active, over }: DragEndEvent) {
    const activeId = String(active.id);
    const current = dragGroups;
    setActiveKey(null);
    setDragGroups(null);
    const issue = byKey.get(activeId);
    if (!over || !current || !issue) return;

    const columnId = containerOf(activeId, current);
    if (columnId === undefined) return;
    let visibleOrder = current[columnId];
    const overId = String(over.id);
    if (visibleOrder.includes(overId) && overId !== activeId) {
      visibleOrder = arrayMove(visibleOrder, visibleOrder.indexOf(activeId), visibleOrder.indexOf(overId));
    }

    // Translate the position among visible cards into an index in the full column, so
    // dropping on a filtered board lands next to the same neighbours.
    const fullOrder = data.issues
      .filter((i) => i.columnId === columnId && i.key !== activeId)
      .sort((a, b) => a.position - b.position || a.number - b.number)
      .map((i) => i.key);
    const at = visibleOrder.indexOf(activeId);
    const nextKey = visibleOrder[at + 1];
    const prevKey = visibleOrder[at - 1];
    const index = nextKey
      ? fullOrder.indexOf(nextKey)
      : prevKey
        ? fullOrder.indexOf(prevKey) + 1
        : fullOrder.length;

    const unchanged =
      columnId === issue.columnId &&
      [...fullOrder.slice(0, index), activeId, ...fullOrder.slice(index)].join() ===
        groupByColumn(data.columns, data.issues)[columnId].join();
    if (unchanged) return;

    // Optimistic update: renumber the affected columns locally.
    const newFull = [...fullOrder];
    newFull.splice(index, 0, activeId);
    const positions = new Map(newFull.map((k, i) => [k, i]));
    const oldColumnOrder = data.issues
      .filter((i) => i.columnId === issue.columnId && i.key !== activeId)
      .sort((a, b) => a.position - b.position)
      .map((i) => i.key);
    if (issue.columnId !== columnId) oldColumnOrder.forEach((k, i) => positions.set(k, i));
    const targetDone = data.columns.find((c) => c.id === columnId)?.category === "done";
    onIssuesChanged(
      data.issues.map((i) =>
        i.key === activeId
          ? { ...i, columnId, position: positions.get(i.key)!, done: targetDone }
          : positions.has(i.key)
            ? { ...i, position: positions.get(i.key)! }
            : i,
      ),
    );

    try {
      await api.moveIssue(activeId, columnId, index);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not move the issue");
    }
    // Blocked state of other issues may change (e.g. a decision moved to Done).
    await reload().catch(() => undefined);
  }

  const activeIssue = activeKey ? byKey.get(activeKey) : undefined;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={(e) => void onDragEnd(e)}
      onDragCancel={onDragCancel}
    >
      <div className="board">
        {data.columns.map((column) => (
          <ColumnView
            key={column.id}
            column={column}
            keys={groups[column.id] ?? []}
            byKey={byKey}
            total={data.issues.filter((i) => i.columnId === column.id).length}
            canAdd={canEditIssues(role)}
            canDrag={(issue) => canMoveIssue(role, issue)}
            onOpen={onOpen}
            projectKey={data.project.key}
            onCreated={() => void reload()}
            onError={onError}
          />
        ))}
      </div>
      <DragOverlay dropAnimation={null}>
        {activeIssue ? <IssueCardBody issue={activeIssue} overlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function ColumnView({
  column,
  keys,
  byKey,
  total,
  canAdd,
  canDrag,
  onOpen,
  projectKey,
  onCreated,
  onError,
}: {
  column: BoardColumn;
  keys: string[];
  byKey: Map<string, Issue>;
  total: number;
  canAdd: boolean;
  canDrag: (issue: Issue) => boolean;
  onOpen: (key: string) => void;
  projectKey: string;
  onCreated: () => void;
  onError: (message: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: columnDropId(column.id) });
  const overLimit = column.wipLimit !== null && total > column.wipLimit;

  return (
    <section className={`column${isOver ? " is-over" : ""}`} aria-label={column.name}>
      <header className="column-header">
        <span className={`column-dot cat-${column.category}`} aria-hidden="true" />
        <h2>{column.name}</h2>
        <span className={`column-count${overLimit ? " over-limit" : ""}`}>
          {keys.length !== total ? `${keys.length}/${total}` : total}
          {column.wipLimit !== null && ` · max ${column.wipLimit}`}
        </span>
      </header>
      <SortableContext items={keys} strategy={verticalListSortingStrategy}>
        <ul ref={setNodeRef} className="column-body">
          {keys.map((k) => {
            const issue = byKey.get(k);
            return issue ? (
              <SortableIssueCard key={k} issue={issue} onOpen={onOpen} disabled={!canDrag(issue)} />
            ) : null;
          })}
          {keys.length === 0 && <li className="column-empty">No issues</li>}
        </ul>
      </SortableContext>
      {canAdd && (
        <QuickAdd projectKey={projectKey} columnId={column.id} onCreated={onCreated} onError={onError} />
      )}
    </section>
  );
}

function QuickAdd({
  projectKey,
  columnId,
  onCreated,
  onError,
}: {
  projectKey: string;
  columnId: number;
  onCreated: () => void;
  onError: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.createIssue(projectKey, { title: title.trim(), columnId });
      setTitle("");
      onCreated();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not create the issue");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="quick-add-button" onClick={() => setOpen(true)}>
        + Add issue
      </button>
    );
  }
  return (
    <form className="quick-add" onSubmit={submit}>
      <textarea
        rows={2}
        placeholder="What needs to be done?"
        value={title}
        autoFocus
        disabled={busy}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.currentTarget.form?.requestSubmit();
          }
          if (e.key === "Escape") setOpen(false);
        }}
      />
      <div className="form-actions">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" disabled={busy || !title.trim()}>
          Add
        </button>
      </div>
    </form>
  );
}
