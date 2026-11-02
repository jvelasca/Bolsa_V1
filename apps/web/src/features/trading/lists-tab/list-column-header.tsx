import { useEffect, useMemo, useRef, useState } from "react";

import type { ListColumnId } from "@bolsa/shared";

import {
  DEFAULT_LIST_COLUMN_WIDTHS,
  DEFAULT_LIST_ROW_ACTIONS_WIDTH,
  LIST_COLUMN_LABELS,
  clampListRowActionsWidth,
} from "@bolsa/shared";

import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  GripVertical,
  MoreHorizontal,
  Star,
} from "lucide-react";

import { cn } from "@/lib/utils";

import {
  LIST_HEADER_GRIP_INSET_PX,
  LIST_ROW_EXPAND_WIDTH_PX,
  LIST_ROW_HORIZONTAL_PADDING_PX,
  LIST_ROW_SELECT_WIDTH_PX,
  fitColumnWidthsToAvailable,
  isCenteredListColumn,
  isNumericListColumn,
  listColumnContentClass,
  listRowLeftGutterWidthPx,
  listRowMinWidthPx,
  patchListFavoriteColumn,
  resolveListFavoriteColumnIds,
} from "@/lib/list-column-layout";

import { useListColumnLayoutContext } from "@/features/trading/lists-tab/list-column-layout-context";
import { useWorkspaceStore } from "@/stores/workspace-store";

interface ListColumnHeaderProps {
  className?: string;
  /** Check de cabecera (selección masiva), estilo matriz Backtesting. */
  selectAllChecked?: boolean;
  selectAllIndeterminate?: boolean;
  onSelectAllToggle?: () => void;
}

function ColumnResizeHandle({
  columnId,

  width,

  onResize,

  onResizeEnd,
}: {
  columnId: ListColumnId;

  width: number;

  onResize: (columnId: ListColumnId, width: number) => void;

  onResizeEnd: () => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();

    event.stopPropagation();

    startRef.current = { x: event.clientX, width };

    function onMouseMove(moveEvent: MouseEvent) {
      const delta = moveEvent.clientX - startRef.current.x;

      onResize(columnId, startRef.current.width + delta);
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
      aria-label={`Redimensionar ${LIST_COLUMN_LABELS[columnId]}`}
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
      aria-label="Redimensionar zona de botones"
      className="absolute -left-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

/** Cabecera interactiva: arrastrar para reordenar, borde para redimensionar. */

export function ListColumnHeader({
  className,
  selectAllChecked,
  selectAllIndeterminate,
  onSelectAllToggle,
}: ListColumnHeaderProps) {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);

  const {
    listId,
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
  } = useListColumnLayoutContext();

  const favoriteIds = new Set(resolveListFavoriteColumnIds(listConfig, listId));
  const [dragId, setDragId] = useState<ListColumnId | null>(null);

  const [dropTargetId, setDropTargetId] = useState<ListColumnId | null>(null);
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

  const selectEnabled = typeof onSelectAllToggle === "function";
  const headerSelectRef = useRef<HTMLInputElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [availableDataWidth, setAvailableDataWidth] = useState<number | null>(
    null,
  );

  useEffect(() => {
    if (!headerSelectRef.current) return;
    headerSelectRef.current.indeterminate = Boolean(selectAllIndeterminate);
  }, [selectAllIndeterminate]);

  // Ancho útil para las columnas = scrollport − gutter − acciones − padding de fila.
  useEffect(() => {
    if (!menuOpen) return;
    const scroller = headerRef.current?.parentElement;
    if (!scroller) return;
    setAvailableDataWidth(
      scroller.clientWidth -
        listRowLeftGutterWidthPx(selectEnabled) -
        clampListRowActionsWidth(rowActionsWidth) -
        LIST_ROW_HORIZONTAL_PADDING_PX,
    );
  }, [menuOpen, selectEnabled, rowActionsWidth, visibleColumns]);

  const overflowColumnCount = useMemo(() => {
    if (availableDataWidth == null) return 0;
    let consumed = 0;
    let hidden = 0;
    for (const column of visibleColumns) {
      consumed += column.width;
      if (consumed > availableDataWidth) hidden += 1;
    }
    return hidden;
  }, [availableDataWidth, visibleColumns]);

  function handleFitToWidth() {
    const scroller = headerRef.current?.parentElement;
    if (!scroller) return;
    const target =
      scroller.clientWidth -
      listRowLeftGutterWidthPx(selectEnabled) -
      clampListRowActionsWidth(rowActionsWidth) -
      LIST_ROW_HORIZONTAL_PADDING_PX;
    if (target <= 0) return;
    for (const column of fitColumnWidthsToAvailable(visibleColumns, target)) {
      resizeColumn(column.id, column.width);
    }
    setMenuOpen(false);
  }

  function handleResetWidths() {
    for (const column of layout) {
      resizeColumn(
        column.id,
        DEFAULT_LIST_COLUMN_WIDTHS[column.id] ?? column.width,
      );
    }
    resizeRowActionsWidth(DEFAULT_LIST_ROW_ACTIONS_WIDTH);
    setMenuOpen(false);
  }

  return (
    <div
      ref={headerRef}
      className={cn(
        "sticky top-0 z-10 flex items-center gap-0 border-b border-border bg-card px-1 py-1 text-[10px] text-muted-foreground select-none",

        className,
      )}
      style={{
        minWidth: listRowMinWidthPx(
          visibleColumns,
          rowActionsWidth,
          selectEnabled,
        ),
      }}
    >
      <div
        className="sticky left-0 z-[2] flex shrink-0 items-center bg-card"
        style={{ width: listRowLeftGutterWidthPx(selectEnabled) }}
      >
        {selectEnabled ? (
          <div
            className="flex shrink-0 items-center justify-center"
            style={{ width: LIST_ROW_SELECT_WIDTH_PX }}
          >
            <input
              ref={headerSelectRef}
              type="checkbox"
              className="h-3.5 w-3.5 accent-primary"
              checked={Boolean(selectAllChecked)}
              aria-label="Seleccionar todos los valores de la lista"
              title="Seleccionar todos"
              onChange={onSelectAllToggle}
            />
          </div>
        ) : null}
        <div
          className="shrink-0"
          style={{ width: LIST_ROW_EXPAND_WIDTH_PX }}
          aria-hidden
        />
      </div>

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
              "relative min-w-0",
              dragId === column.id && "opacity-40",
              dropTargetId === column.id &&
                "bg-primary/15 ring-1 ring-primary/40",
              isCenteredListColumn(column.id) && "flex justify-center",
            )}
            title="Clic para ordenar · arrastra para reordenar columna · borde para ancho"
          >
            <div
              className={cn(
                "relative flex min-w-0 items-center rounded py-0.5",
                listColumnContentClass(column.id, "header"),
                isCenteredListColumn(column.id) && "w-full justify-center",
              )}
            >
              {!isCenteredListColumn(column.id) && (
                <GripVertical
                  className="absolute left-0 h-3 w-3 shrink-0 cursor-grab opacity-40 active:cursor-grabbing"
                  style={{ width: LIST_HEADER_GRIP_INSET_PX }}
                />
              )}

              <button
                type="button"
                className={cn(
                  "flex min-w-0 items-center gap-0.5 truncate",
                  isCenteredListColumn(column.id)
                    ? "justify-center"
                    : isNumericListColumn(column.id)
                      ? "flex-1 justify-end"
                      : "flex-1 justify-start",
                )}
                onClick={(event) => {
                  event.stopPropagation();

                  cycleSort(column.id);
                }}
              >
                <span
                  className={cn(
                    "truncate",
                    isCenteredListColumn(column.id) && "text-[9px]",
                  )}
                >
                  {LIST_COLUMN_LABELS[column.id]}
                </span>
                {!isCenteredListColumn(column.id) &&
                  (sortState?.column === column.id ? (
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
        className="sticky right-0 z-[2] shrink-0 border-l border-border/50 bg-card shadow-[-6px_0_8px_-8px_rgba(0,0,0,0.45)]"
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
            title="Columnas visibles de esta lista (independiente por lista)"
            className="rounded p-1 hover:bg-accent"
            onClick={() => setMenuOpen((value) => !value)}
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full z-20 mt-1 min-w-[200px] rounded-md border border-border bg-card py-1 shadow-lg">
              <p className="px-2 py-1 text-[10px] font-medium text-foreground">
                Columnas (esta lista)
              </p>
              <p className="px-2 pb-1 text-[9px] leading-snug text-muted-foreground">
                Layout propio por lista. Sincro = velas; Procesos = Lab.
                IO/TA/FA/★/Postura = recomendación (activar con el check).
              </p>
              {layout.map((column) => (
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
                    {LIST_COLUMN_LABELS[column.id]}
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
                      updateListConfig(
                        patchListFavoriteColumn(listConfig, listId, column.id),
                      );
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
              <div className="mt-1 border-t border-border/60 px-2 pt-1">
                <p className="pb-1 text-[9px] leading-snug text-muted-foreground">
                  {visibleColumns.length} de {layout.length} columnas visibles
                  {overflowColumnCount > 0
                    ? ` · ${overflowColumnCount} fuera de vista (scroll horizontal)`
                    : ""}
                </p>
                <div className="flex items-center gap-1 pb-1">
                  <button
                    type="button"
                    title="Compacta las columnas para ver el máximo posible en el ancho actual (mínimo 40 px; si no cabe, la lista scrollea)"
                    className="flex-1 rounded border border-border px-1.5 py-1 text-[10px] font-medium hover:bg-accent"
                    onClick={handleFitToWidth}
                  >
                    Ajustar al ancho
                  </button>
                  <button
                    type="button"
                    title="Devuelve todas las columnas a su ancho por defecto"
                    className="flex-1 rounded border border-border px-1.5 py-1 text-[10px] font-medium hover:bg-accent"
                    onClick={handleResetWidths}
                  >
                    Restablecer
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
