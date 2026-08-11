import { useEffect, useRef, useState } from "react";
import type { ListHubColumnId } from "@bolsa/shared";
import { LIST_HUB_COLUMN_LABELS } from "@bolsa/shared";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  GripVertical,
  MoreHorizontal,
  Star,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  LIST_HUB_HEADER_GRIP_INSET_PX,
  LIST_HUB_ROW_CHART_MEMBERSHIP_WIDTH_PX,
  LIST_HUB_ROW_EXPAND_WIDTH_PX,
  isCenteredListHubColumn,
  isNumericListHubColumn,
  isSortableListHubColumn,
  listHubColumnContentClass,
  toggleListHubFavoriteColumn,
} from "@/lib/list-hub-column-layout";
import { useListHubColumnLayoutContext } from "@/features/trading/lists-tab/list-hub-column-layout-context";
import { useWorkspaceStore } from "@/stores/workspace-store";

function ColumnResizeHandle({
  columnId,
  width,
  onResize,
  onResizeEnd,
}: {
  columnId: ListHubColumnId;
  width: number;
  onResize: (columnId: ListHubColumnId, width: number) => void;
  onResizeEnd: () => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    startRef.current = { x: event.clientX, width };

    function onMouseMove(moveEvent: MouseEvent) {
      onResize(
        columnId,
        startRef.current.width + (moveEvent.clientX - startRef.current.x),
      );
    }

    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      onResizeEnd();
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  return (
    <button
      type="button"
      aria-label={`Redimensionar ${LIST_HUB_COLUMN_LABELS[columnId]}`}
      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

function RowActionsResizeHandle({
  width,
  onResize,
  onResizeEnd,
}: {
  width: number;
  onResize: (width: number) => void;
  onResizeEnd: () => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    startRef.current = { x: event.clientX, width };

    function onMouseMove(moveEvent: MouseEvent) {
      const delta = startRef.current.x - moveEvent.clientX;
      onResize(startRef.current.width + delta);
    }

    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      onResizeEnd();
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  return (
    <button
      type="button"
      aria-label="Redimensionar zona de acciones"
      className="absolute -left-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

export function ListHubColumnHeader({
  chartInstrumentLabel,
}: {
  chartInstrumentLabel?: string;
}) {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);

  const {
    layout,
    visibleColumns,
    dataGridTemplateColumns,
    rowActionsWidth,
    sortState,
    reorderColumns,
    resizeColumn,
    resizeRowActionsWidth,
    cycleSort,
    toggleColumn,
    commitLayout,
  } = useListHubColumnLayoutContext();

  const favoriteIds = new Set(
    listConfig.hubFavoriteColumnIds ?? ["name", "count"],
  );
  const configurableColumns = layout.filter(
    (column) => column.id !== "carousel",
  );
  const [dragId, setDragId] = useState<ListHubColumnId | null>(null);
  const [dropTargetId, setDropTargetId] = useState<ListHubColumnId | null>(
    null,
  );
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [menuOpen]);

  function handleResizeEnd() {
    commitLayout();
  }

  return (
    <div className="sticky top-0 z-10 flex items-center gap-0 border-b border-border bg-card px-1 py-1 text-[10px] text-muted-foreground select-none">
      <span
        className="shrink-0"
        style={{ width: LIST_HUB_ROW_EXPAND_WIDTH_PX }}
        aria-hidden
      />

      {chartInstrumentLabel && (
        <span
          className="flex shrink-0 items-center justify-center"
          style={{ width: LIST_HUB_ROW_CHART_MEMBERSHIP_WIDTH_PX }}
          title={
            chartInstrumentLabel
              ? `${chartInstrumentLabel} · ¿está en cada lista? (solo lectura)`
              : "Pertenencia del valor del gráfico a cada lista"
          }
        >
          <Check className="h-3 w-3 shrink-0 opacity-40" />
        </span>
      )}

      <div
        className="grid min-w-0 flex-1 items-center"
        style={{ gridTemplateColumns: dataGridTemplateColumns }}
      >
        {visibleColumns.map((column) => (
          <div
            key={column.id}
            draggable
            onDragStart={() => setDragId(column.id)}
            onDragEnd={() => {
              setDragId(null);
              setDropTargetId(null);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              if (dragId && dragId !== column.id) setDropTargetId(column.id);
            }}
            onDragLeave={() => {
              if (dropTargetId === column.id) setDropTargetId(null);
            }}
            onDrop={(event) => {
              event.preventDefault();
              if (dragId && dragId !== column.id) {
                reorderColumns(dragId, column.id);
              }
              setDragId(null);
              setDropTargetId(null);
            }}
            className={cn(
              "relative min-w-0 overflow-hidden",
              dragId === column.id && "opacity-40",
              dropTargetId === column.id &&
                "bg-primary/15 ring-1 ring-primary/40",
              isCenteredListHubColumn(column.id) && "flex justify-center",
            )}
            title="Clic para ordenar · arrastra para reordenar · borde para ancho"
          >
            <div
              className={cn(
                "relative flex min-w-0 items-center rounded py-0.5",
                listHubColumnContentClass(column.id, "header"),
                isCenteredListHubColumn(column.id) && "w-full justify-center",
              )}
            >
              {!isCenteredListHubColumn(column.id) && (
                <GripVertical
                  className="absolute left-0 h-3 w-3 shrink-0 cursor-grab opacity-40 active:cursor-grabbing"
                  style={{ width: LIST_HUB_HEADER_GRIP_INSET_PX }}
                />
              )}
              <button
                type="button"
                disabled={!isSortableListHubColumn(column.id)}
                className={cn(
                  "flex min-w-0 items-center gap-0.5",
                  isCenteredListHubColumn(column.id)
                    ? "justify-center"
                    : isNumericListHubColumn(column.id)
                      ? "flex-1 justify-end pr-1"
                      : "flex-1 justify-start pl-3.5",
                )}
                onClick={(event) => {
                  event.stopPropagation();
                  cycleSort(column.id);
                }}
              >
                <span
                  className={cn(
                    "truncate",
                    isCenteredListHubColumn(column.id) && "text-[9px]",
                  )}
                >
                  {LIST_HUB_COLUMN_LABELS[column.id]}
                </span>
                {isSortableListHubColumn(column.id) &&
                  (sortState.column === column.id ? (
                    sortState.direction === "asc" ? (
                      <ArrowUp className="h-3 w-3 shrink-0 text-primary" />
                    ) : (
                      <ArrowDown className="h-3 w-3 shrink-0 text-primary" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 shrink-0 opacity-30" />
                  ))}
              </button>
            </div>
            <ColumnResizeHandle
              columnId={column.id}
              width={column.width}
              onResize={resizeColumn}
              onResizeEnd={handleResizeEnd}
            />
          </div>
        ))}
      </div>

      <div
        className="relative shrink-0 border-l border-border/50"
        style={{ width: rowActionsWidth }}
      >
        <RowActionsResizeHandle
          width={rowActionsWidth}
          onResize={resizeRowActionsWidth}
          onResizeEnd={handleResizeEnd}
        />
        <div
          ref={menuRef}
          className="flex h-full items-center justify-end pr-0.5"
        >
          <button
            type="button"
            title="Configurar columnas de Listas"
            className="rounded p-1 hover:bg-accent"
            onClick={() => setMenuOpen((value) => !value)}
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full z-20 mt-1 min-w-[180px] rounded-md border border-border bg-card py-1 shadow-lg">
              <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground">
                Columnas (Listas)
              </p>
              {configurableColumns.map((column) => (
                <label
                  key={column.id}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-accent/50"
                >
                  <input
                    type="checkbox"
                    checked={column.visible}
                    onChange={() => toggleColumn(column.id)}
                  />
                  <span className="flex-1">
                    {LIST_HUB_COLUMN_LABELS[column.id]}
                  </span>
                  <button
                    type="button"
                    title={
                      favoriteIds.has(column.id)
                        ? "Quitar de favoritas"
                        : "Marcar como favorita"
                    }
                    className={cn(
                      "rounded p-0.5",
                      favoriteIds.has(column.id)
                        ? "text-amber-500"
                        : "text-muted-foreground/40 hover:text-muted-foreground",
                    )}
                    onClick={(event) => {
                      event.preventDefault();
                      updateListConfig({
                        hubFavoriteColumnIds: toggleListHubFavoriteColumn(
                          listConfig,
                          column.id,
                        ),
                      });
                      save();
                    }}
                  >
                    <Star
                      className="h-3 w-3"
                      fill={
                        favoriteIds.has(column.id) ? "currentColor" : "none"
                      }
                    />
                  </button>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
