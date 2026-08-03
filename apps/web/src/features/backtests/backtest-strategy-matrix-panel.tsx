/**
 * Matriz de estrategias (panel izquierdo Probar).
 *
 * - Filtros: carrusel Todas / Genéricas / Mis / Finalistas con contadores.
 * - CTA **Probar + coach**: lote = selección del filtro, o todas las filas visibles.
 * - No fuerza Genéricas: Finalistas / Mis / Todas respetan el filtro activo.
 *
 * @see docs/engineering/research-lifecycle.md § Hub UX Probar
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  GripVertical,
  MoreHorizontal,
  Star,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { OpaqueMenuLabel, OpaqueMenuPanel } from '@/components/ui/opaque-menu-panel';
import { cn } from '@/lib/utils';
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  filterStrategyMatrixRows,
  formatPct,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
  type StrategyMatrixRunProgress,
} from '@/features/backtests/backtest-strategy-matrix';
import { StrategyFilterCarousel } from '@/features/backtests/strategy-filter-carousel';
import {
  loadBacktestZonePrefs,
  patchStrategyMatrixTablePrefs,
  clampListHeightPx,
  MATRIX_LIST_HEIGHT_MAX,
  MATRIX_LIST_HEIGHT_MIN,
} from '@/features/backtests/backtest-zone-prefs';
import {
  STRATEGY_MATRIX_COLUMN_LABELS,
  STRATEGY_MATRIX_COLUMN_TIPS,
  buildStrategyMatrixGridTemplate,
  cycleStrategyMatrixSort,
  isStrategyMatrixActionColumn,
  reorderStrategyMatrixColumns,
  resizeStrategyMatrixColumn,
  sortStrategyMatrixRows,
  strategyMatrixColumnAlign,
  toggleStrategyMatrixColumn,
  toggleStrategyMatrixFavoriteColumn,
  visibleStrategyMatrixColumns,
  type StrategyMatrixColumnId,
  type StrategyMatrixColumnLayoutItem,
  type StrategyMatrixSortState,
} from '@/features/backtests/strategy-matrix-column-layout';

type Props = {
  rows: StrategyMatrixRow[];
  filter: StrategyMatrixFilter;
  selectedIds: Set<string>;
  running: boolean;
  progress: StrategyMatrixRunProgress;
  disabled?: boolean;
  /** Label for finalists filter chip, e.g. "Finalistas · ACS". */
  finalistsFilterLabel?: string;
  finalistsFilterDisabled?: boolean;
  onFilterChange: (filter: StrategyMatrixFilter) => void;
  onToggle: (rowId: string) => void;
  /**
   * Aplicar selección:
   * - replace: deja solo estos ids
   * - add: une (hasta el tope)
   * - remove: quita estos ids
   */
  onApplySelection: (mode: 'replace' | 'add' | 'remove', rowIds: string[]) => void;
  onClearSelection: () => void;
  /** Batería de genéricas → panel Coach (único CTA de lanzamiento). */
  onRunCoach: (opts?: { forceResim?: boolean }) => void;
  coachDisabled?: boolean;
  coachCount?: number;
  onStop: () => void;
  onOpenDetail: (runId: string) => void;
  onGoToStrategies?: () => void;
  /** Abrir fila en Biblioteca (Mis estrategias / genérica). */
  onOpenInLibrary?: (row: StrategyMatrixRow) => void;
  /** Eliminar estrategia guardada (Mis estrategias). */
  onDeleteSavedStrategy?: (row: StrategyMatrixRow) => void;
  /** Altura lista (px) controlada desde prefs de zona. */
  listHeightPx?: number;
  onListHeightPxChange?: (next: number) => void;
};

function statusLabel(row: StrategyMatrixRow): string {
  switch (row.status) {
    case 'running':
      return 'En curso…';
    case 'pending':
      return 'En cola';
    case 'ok':
      return 'OK';
    case 'error':
      return 'Error';
    case 'skipped':
      return 'Cancelada';
    default:
      return '';
  }
}

function ColumnResizeHandle({
  columnId,
  width,
  onResize,
}: {
  columnId: StrategyMatrixColumnId;
  width: number;
  onResize: (columnId: StrategyMatrixColumnId, width: number) => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    startRef.current = { x: event.clientX, width };

    function onMouseMove(moveEvent: MouseEvent) {
      onResize(columnId, startRef.current.width + (moveEvent.clientX - startRef.current.x));
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  return (
    <button
      type="button"
      aria-label={`Redimensionar ${STRATEGY_MATRIX_COLUMN_LABELS[columnId]}`}
      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

export function BacktestStrategyMatrixPanel({
  rows,
  filter,
  selectedIds,
  running,
  progress,
  disabled,
  finalistsFilterLabel = 'Finalistas',
  finalistsFilterDisabled,
  onFilterChange,
  onToggle,
  onApplySelection,
  onClearSelection: _onClearSelection,
  onRunCoach,
  coachDisabled,
  coachCount = 21,
  onStop,
  onOpenDetail,
  onGoToStrategies,
  onOpenInLibrary,
  onDeleteSavedStrategy,
  listHeightPx: listHeightPxProp,
  onListHeightPxChange,
}: Props) {
  const initial = useMemo(() => loadBacktestZonePrefs().strategyMatrix, []);
  const [layout, setLayout] = useState<StrategyMatrixColumnLayoutItem[]>(initial.columnLayout);
  const [sortState, setSortState] = useState<StrategyMatrixSortState | null>(initial.sort);
  const [favoriteColumnIds, setFavoriteColumnIds] = useState<StrategyMatrixColumnId[]>(
    initial.favoriteColumnIds,
  );
  const [listHeightPxLocal, setListHeightPxLocal] = useState(initial.listHeightPx);
  const listHeightPx = listHeightPxProp ?? listHeightPxLocal;

  useEffect(() => {
    if (listHeightPxProp != null) setListHeightPxLocal(listHeightPxProp);
  }, [listHeightPxProp]);

  function setListHeightPx(next: number) {
    const clamped = clampListHeightPx(next);
    setListHeightPxLocal(clamped);
    if (onListHeightPxChange) onListHeightPxChange(clamped);
    else patchStrategyMatrixTablePrefs({ listHeightPx: clamped });
  }

  const [menuOpen, setMenuOpen] = useState(false);
  const [dragId, setDragId] = useState<StrategyMatrixColumnId | null>(null);
  const [dropTargetId, setDropTargetId] = useState<StrategyMatrixColumnId | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const headerSelectRef = useRef<HTMLInputElement>(null);
  const listResizeRef = useRef({ y: 0, height: initial.listHeightPx });
  /** Ancla para Shift+clic (estilo lista Windows). */
  const selectionAnchorRef = useRef<string | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  const favoriteIds = useMemo(() => new Set(favoriteColumnIds), [favoriteColumnIds]);
  const visibleColumns = useMemo(() => visibleStrategyMatrixColumns(layout), [layout]);
  const gridTemplate = useMemo(
    () => buildStrategyMatrixGridTemplate(visibleColumns, 44),
    [visibleColumns],
  );

  const filtered = useMemo(() => filterStrategyMatrixRows(rows, filter), [rows, filter]);
  const visible = useMemo(
    () => sortStrategyMatrixRows(filtered, sortState),
    [filtered, sortState],
  );

  const filterCounts = useMemo(() => {
    let preset = 0;
    let saved = 0;
    let finalists = 0;
    for (const row of rows) {
      if (row.kind === 'preset') preset += 1;
      if (row.kind === 'saved') saved += 1;
      if (row.topRank != null) finalists += 1;
    }
    return { all: rows.length, preset, saved, finalists };
  }, [rows]);

  const selectedCount = selectedIds.size;
  const canRunCoach = !coachDisabled && !disabled && !running;

  /** Filas de la lista actual (filtro + orden) — el check de cabecera opera sobre todas. */
  const listRowIds = useMemo(() => visible.map((row) => row.rowId), [visible]);
  const selectedAmongList = useMemo(
    () => listRowIds.filter((id) => selectedIds.has(id)).length,
    [listRowIds, selectedIds],
  );
  const headerChecked =
    listRowIds.length > 0 && selectedAmongList === listRowIds.length;
  const headerIndeterminate = selectedAmongList > 0 && !headerChecked;
  const headerDisabled = running || visible.length === 0;

  useEffect(() => {
    if (headerSelectRef.current) {
      headerSelectRef.current.indeterminate = headerIndeterminate;
    }
  }, [headerIndeterminate]);

  function handleHeaderSelectToggle() {
    if (headerChecked || headerIndeterminate) {
      onApplySelection('remove', listRowIds);
      selectionAnchorRef.current = null;
      return;
    }
    onApplySelection('replace', listRowIds);
    selectionAnchorRef.current = listRowIds[0] ?? null;
  }

  function rangeRowIds(fromId: string, toId: string): string[] {
    const ids = visible.map((row) => row.rowId);
    const a = ids.indexOf(fromId);
    const b = ids.indexOf(toId);
    if (a < 0 || b < 0) return [toId];
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    return ids.slice(lo, hi + 1);
  }

  function handleRowPointerSelect(rowId: string, event: React.MouseEvent) {
    if (running) return;
    const withCtrl = event.ctrlKey || event.metaKey;
    const withShift = event.shiftKey;

    if (withShift && selectionAnchorRef.current) {
      const range = rangeRowIds(selectionAnchorRef.current, rowId);
      if (withCtrl) {
        onApplySelection('add', range);
      } else {
        onApplySelection('replace', range);
      }
      return;
    }

    if (withCtrl) {
      onToggle(rowId);
      selectionAnchorRef.current = rowId;
      return;
    }

    // Clic simple en fila: deja solo esta (como lista Windows).
    onApplySelection('replace', [rowId]);
    selectionAnchorRef.current = rowId;
  }

  function handleCheckboxClick(rowId: string, event: React.MouseEvent) {
    event.stopPropagation();
    if (running) return;
    const withCtrl = event.ctrlKey || event.metaKey;
    const withShift = event.shiftKey;

    if (withShift && selectionAnchorRef.current) {
      event.preventDefault();
      const range = rangeRowIds(selectionAnchorRef.current, rowId);
      if (withCtrl) {
        onApplySelection('add', range);
      } else {
        onApplySelection('replace', range);
      }
      return;
    }

    // Check sin modificadores: toggle de esa fila (tabla con checks).
    event.preventDefault();
    onToggle(rowId);
    selectionAnchorRef.current = rowId;
    void withCtrl;
  }

  function handleFilterChange(next: StrategyMatrixFilter) {
    onFilterChange(next);
    patchStrategyMatrixTablePrefs({ filter: next });
  }

  function onListResizeMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    listResizeRef.current = { y: event.clientY, height: listHeightPx };

    function onMouseMove(moveEvent: MouseEvent) {
      setListHeightPx(
        clampListHeightPx(
          listResizeRef.current.height + (moveEvent.clientY - listResizeRef.current.y),
        ),
      );
    }

    function onMouseUp(upEvent: MouseEvent) {
      const next = clampListHeightPx(
        listResizeRef.current.height + (upEvent.clientY - listResizeRef.current.y),
      );
      setListHeightPx(next);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  function persistLayout(next: StrategyMatrixColumnLayoutItem[]) {
    setLayout(next);
    patchStrategyMatrixTablePrefs({ columnLayout: next });
  }

  function persistSort(next: StrategyMatrixSortState | null) {
    setSortState(next);
    patchStrategyMatrixTablePrefs({ sort: next });
  }

  function persistFavorites(next: StrategyMatrixColumnId[]) {
    setFavoriteColumnIds(next);
    patchStrategyMatrixTablePrefs({ favoriteColumnIds: next });
  }

  function renderCell(columnId: StrategyMatrixColumnId, row: StrategyMatrixRow) {
    switch (columnId) {
      case 'label':
        return (
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-1 truncate font-medium" title={row.label}>
              {row.topRank != null && (
                <span
                  className="shrink-0 rounded bg-emerald-500/20 px-1 py-px text-[9px] font-semibold text-emerald-800 dark:text-emerald-200"
                  title={`Finalista #${row.topRank} del valor`}
                >
                  #{row.topRank}
                </span>
              )}
              <span className="truncate">{row.label}</span>
            </div>
            <div className="truncate text-[10px] text-muted-foreground">
              {row.status === 'running' || row.status === 'pending'
                ? statusLabel(row)
                : row.subtitle}
            </div>
          </div>
        );
      case 'kind':
        return (
          <span className="truncate text-muted-foreground">
            {row.kind === 'preset' ? 'Genérica' : 'Mía'}
          </span>
        );
      case 'category':
        return <span className="truncate text-muted-foreground">{row.subtitle}</span>;
      case 'status':
        return (
          <span
            className={cn(
              'truncate',
              row.status === 'error' && 'text-destructive',
              row.status === 'ok' && 'text-emerald-700 dark:text-emerald-400',
            )}
            title={row.error}
          >
            {statusLabel(row) || '—'}
          </span>
        );
      case 'returnPct':
        return (
          <span className="tabular-nums">
            {row.status === 'ok' ? formatPct(row.totalReturnPct) : statusLabel(row) || '—'}
          </span>
        );
      case 'excessPct':
        return (
          <span
            className={cn(
              'tabular-nums',
              row.excessReturnPct != null && row.excessReturnPct > 0
                ? 'text-emerald-700 dark:text-emerald-400'
                : row.excessReturnPct != null && row.excessReturnPct < 0
                  ? 'text-rose-700 dark:text-rose-400'
                  : '',
            )}
          >
            {row.status === 'ok' ? formatPct(row.excessReturnPct) : '—'}
          </span>
        );
      case 'buyHoldPct':
        return (
          <span className="tabular-nums">
            {row.status === 'ok' ? formatPct(row.buyHoldReturnPct) : '—'}
          </span>
        );
      case 'drawdownPct':
        return (
          <span className="tabular-nums">
            {row.status === 'ok' && row.maxDrawdownPct != null
              ? formatPct(row.maxDrawdownPct)
              : '—'}
          </span>
        );
      case 'tradeCount':
        return (
          <span className="tabular-nums">
            {row.status === 'ok' ? (row.tradeCount ?? '—') : '—'}
          </span>
        );
      case 'actions':
        return (
          <div
            className="flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            {row.runId ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 px-1.5 text-[10px] font-medium"
                title="Ver detalle de la última prueba"
                onClick={() => onOpenDetail(row.runId!)}
              >
                Ver
              </Button>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
        );
      case 'library':
        return (
          <div
            className="flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            {onOpenInLibrary &&
            (row.kind === 'saved'
              ? Boolean(row.strategyDefinitionId)
              : Boolean(row.presetKey)) ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 px-1.5 text-[10px]"
                title="Abrir en Biblioteca"
                onClick={() => onOpenInLibrary(row)}
              >
                Biblio
              </Button>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
        );
      case 'remove':
        return (
          <div
            className="flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            {onDeleteSavedStrategy &&
            row.kind === 'saved' &&
            row.strategyDefinitionId ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 px-1.5 text-[10px] text-destructive"
                title="Eliminar de Mis estrategias"
                disabled={running}
                onClick={() => onDeleteSavedStrategy(row)}
              >
                Borrar
              </Button>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
        );
      default:
        return null;
    }
  }

  const columnsMenu = (
    <div className="relative" ref={menuRef}>
      <IconButton
        icon={MoreHorizontal}
        title="Configurar columnas y favoritos"
        active={menuOpen}
        onClick={() => setMenuOpen((v) => !v)}
        className={menuOpen ? 'bg-accent text-foreground' : undefined}
      />
      {menuOpen && (
        <OpaqueMenuPanel className="absolute right-0 top-full z-30 mt-1 min-w-[200px] p-2">
          <OpaqueMenuLabel>Columnas visibles</OpaqueMenuLabel>
          {layout
            .filter((column) => column.id !== 'actions')
            .map((column) => {
              const locked = column.id === 'label';
              return (
                <label
                  key={column.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
                >
                  <input
                    type="checkbox"
                    checked={column.visible}
                    disabled={locked}
                    onChange={() => persistLayout(toggleStrategyMatrixColumn(layout, column.id))}
                  />
                  <span className="flex-1">{STRATEGY_MATRIX_COLUMN_LABELS[column.id]}</span>
                  <button
                    type="button"
                    title={
                      favoriteIds.has(column.id)
                        ? 'Quitar de favoritas'
                        : 'Marcar como favorita'
                    }
                    className={cn(
                      'rounded p-0.5',
                      favoriteIds.has(column.id)
                        ? 'text-amber-500'
                        : 'text-muted-foreground/50 hover:text-muted-foreground',
                    )}
                    onClick={(event) => {
                      event.preventDefault();
                      persistFavorites(
                        toggleStrategyMatrixFavoriteColumn(favoriteColumnIds, column.id),
                      );
                    }}
                  >
                    <Star
                      className="h-3 w-3"
                      fill={favoriteIds.has(column.id) ? 'currentColor' : 'none'}
                    />
                  </button>
                </label>
              );
            })}
          <p className="mt-1 border-t border-border px-2 pt-2 text-[10px] text-muted-foreground">
            ★ Favoritas en este dispositivo · Biblio / Borrar opcionales · Ver = detalle ·
            Arrastra el borde inferior para altura
          </p>
        </OpaqueMenuPanel>
      )}
    </div>
  );

  return (
    <div className="space-y-2 rounded-md border border-border/80 bg-muted/20 p-2">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <p className="shrink-0 text-[11px] font-medium">
            Estrategias
            <span
              className={cn(
                'ml-1.5 tabular-nums',
                selectedCount > 0 ? 'text-foreground' : 'font-normal text-muted-foreground',
              )}
              title="Seleccionadas / máximo por lote"
            >
              {selectedCount}/{STRATEGY_MATRIX_MAX_SELECTED}
            </span>
          </p>
          <div className="flex shrink-0 items-center gap-1">
            {onGoToStrategies ? (
              <button
                type="button"
                className="text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline disabled:opacity-40"
                onClick={onGoToStrategies}
                disabled={running}
                title="Abrir biblioteca de estrategias"
              >
                Biblioteca
              </button>
            ) : null}
            {columnsMenu}
          </div>
        </div>
        <StrategyFilterCarousel
          value={filter}
          onChange={(id) => {
            if (running) return;
            handleFilterChange(id as StrategyMatrixFilter);
          }}
          ariaLabel="Filtro de la matriz de estrategias"
          chips={[
            {
              id: 'all',
              label: 'Todas',
              count: filterCounts.all,
              title: 'Catálogo + Mis estrategias',
              disabled: running,
            },
            {
              id: 'preset',
              label: 'Genéricas',
              count: filterCounts.preset,
              title: 'Plantillas del catálogo',
              disabled: running,
            },
            {
              id: 'saved',
              label: 'Mis estrategias',
              count: filterCounts.saved,
              title: 'Biblioteca guardada',
              disabled: running,
            },
            {
              id: 'finalists',
              label: finalistsFilterLabel,
              count: filterCounts.finalists,
              disabled: running || Boolean(finalistsFilterDisabled),
              title: finalistsFilterDisabled
                ? 'Sin TOP para este valor (Coach → Guardar TOP-3 o Lab)'
                : 'Solo finalistas del valor actual',
            },
          ]}
        />
      </div>

      <div className="overflow-hidden rounded border border-border/60 bg-background">
        <div
          className="overflow-auto"
          style={{ height: listHeightPx }}
        >
        <div className="sticky top-0 z-10 border-b border-border bg-muted/95 backdrop-blur">
          <div
            className="grid min-w-0 items-center"
            style={{ gridTemplateColumns: gridTemplate }}
          >
            <div className="flex h-7 items-center justify-center px-1">
              <input
                ref={headerSelectRef}
                type="checkbox"
                checked={headerChecked}
                disabled={headerDisabled}
                onChange={handleHeaderSelectToggle}
                title={
                  headerChecked || headerIndeterminate
                    ? 'Desmarcar todas las de este filtro'
                    : listRowIds.length === 0
                      ? 'No hay filas en este filtro'
                      : `Seleccionar las ${listRowIds.length} de este filtro`
                }
                aria-label={
                  headerChecked || headerIndeterminate
                    ? 'Desmarcar todas las estrategias del filtro'
                    : `Seleccionar las ${listRowIds.length} estrategias del filtro`
                }
              />
            </div>
            {visibleColumns.map((column) => {
              const align = strategyMatrixColumnAlign(column.id);
              const isSorted = sortState?.columnId === column.id;
              const sortable = !isStrategyMatrixActionColumn(column.id);
              const draggable = !isStrategyMatrixActionColumn(column.id);

              return (
                <div
                  key={column.id}
                  draggable={draggable}
                  onDragStart={() => {
                    if (!draggable) return;
                    setDragId(column.id);
                  }}
                  onDragEnd={() => {
                    setDragId(null);
                    setDropTargetId(null);
                  }}
                  onDragOver={(event) => {
                    if (!draggable) return;
                    event.preventDefault();
                    if (dragId && dragId !== column.id) setDropTargetId(column.id);
                  }}
                  onDragLeave={() => {
                    if (dropTargetId === column.id) setDropTargetId(null);
                  }}
                  onDrop={(event) => {
                    if (!draggable) return;
                    event.preventDefault();
                    if (dragId && dragId !== column.id) {
                      persistLayout(reorderStrategyMatrixColumns(layout, dragId, column.id));
                    }
                    setDragId(null);
                    setDropTargetId(null);
                  }}
                  className={cn(
                    'relative h-7 min-w-0',
                    dragId === column.id && 'opacity-40',
                    dropTargetId === column.id && 'bg-primary/15 ring-1 ring-primary/40',
                  )}
                  title={STRATEGY_MATRIX_COLUMN_TIPS[column.id]}
                >
                  <div
                    className={cn(
                      'flex h-full min-w-0 items-center gap-0.5 px-1.5 text-[10px] font-medium text-muted-foreground',
                      align === 'left' && 'justify-start',
                      align === 'center' && 'justify-center',
                      align === 'right' && 'justify-end',
                      sortable && 'cursor-pointer select-none hover:text-foreground',
                    )}
                    onClick={() => {
                      if (!sortable) return;
                      persistSort(cycleStrategyMatrixSort(sortState, column.id));
                    }}
                  >
                    {draggable && (
                      <GripVertical
                        className="absolute left-0 top-1/2 h-3 w-3 -translate-y-1/2 cursor-grab opacity-35"
                        aria-hidden
                      />
                    )}
                    <span className={cn('truncate', draggable && align === 'left' && 'pl-3')}>
                      {STRATEGY_MATRIX_COLUMN_LABELS[column.id]}
                    </span>
                    {sortable && (
                      <span className="shrink-0">
                        {!isSorted && <ArrowUpDown className="h-3 w-3 opacity-50" />}
                        {isSorted && sortState?.direction === 'asc' && (
                          <ArrowUp className="h-3 w-3" />
                        )}
                        {isSorted && sortState?.direction === 'desc' && (
                          <ArrowDown className="h-3 w-3" />
                        )}
                      </span>
                    )}
                  </div>
                  {draggable ? (
                    <ColumnResizeHandle
                      columnId={column.id}
                      width={column.width}
                      onResize={(columnId, width) =>
                        persistLayout(resizeStrategyMatrixColumn(layout, columnId, width))
                      }
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        {visible.length === 0 ? (
          <p className="px-2 py-3 text-center text-[11px] text-muted-foreground">
            {filter === 'saved'
              ? 'No hay estrategias en Mis estrategias. Clona una genérica o importa desde el gráfico.'
              : filter === 'finalists'
                ? 'Sin finalistas para este valor. En Coach: Guardar TOP-3 (o adopta en Lab).'
                : 'Sin estrategias en este filtro.'}
          </p>
        ) : (
          <div className="divide-y divide-border/40 text-[11px]">
            {visible.map((row) => {
              const checked = selectedIds.has(row.rowId);
              const atCap = !checked && selectedCount >= STRATEGY_MATRIX_MAX_SELECTED;
              return (
                <div
                  key={row.rowId}
                  className={cn(
                    'grid min-w-0 cursor-default items-center py-1 hover:bg-muted/40',
                    row.status === 'running' && 'bg-primary/5',
                    row.status === 'skipped' && 'opacity-60',
                    checked && 'bg-primary/10',
                    row.topRank != null && 'border-l-2 border-l-emerald-500/70',
                  )}
                  style={{ gridTemplateColumns: gridTemplate }}
                  title={
                    row.status === 'error' || row.status === 'skipped'
                      ? row.error
                      : `${row.subtitle ?? ''} · Clic = solo esta · Ctrl = sumar/quitar · Shift = rango`
                  }
                  onClick={(event) => handleRowPointerSelect(row.rowId, event)}
                >
                  <div className="flex items-center justify-center px-1.5">
                    <input
                      type="checkbox"
                      className="align-middle"
                      checked={checked}
                      disabled={running || (atCap && !checked)}
                      onClick={(event) => handleCheckboxClick(row.rowId, event)}
                      onChange={() => {
                        /* selección vía onClick (Ctrl/Shift); evita doble toggle */
                      }}
                      aria-label={`Seleccionar ${row.label}`}
                    />
                  </div>
                  {visibleColumns.map((column) => {
                    const align = strategyMatrixColumnAlign(column.id);
                    return (
                      <div
                        key={column.id}
                        className={cn(
                          'min-w-0 px-1.5',
                          align === 'left' && 'text-left',
                          align === 'center' && 'text-center',
                          align === 'right' && 'text-right',
                          column.id === 'label' && 'pl-[1.125rem]',
                        )}
                      >
                        {renderCell(column.id, row)}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}
        </div>
        <button
          type="button"
          className="group flex h-3 w-full cursor-ns-resize items-center justify-center border-t border-border/60 bg-muted/50 hover:bg-muted"
          onMouseDown={onListResizeMouseDown}
          title={`Altura del listado (${MATRIX_LIST_HEIGHT_MIN}–${MATRIX_LIST_HEIGHT_MAX} px). Arrastra para redimensionar · se guarda en este dispositivo.`}
          aria-label="Redimensionar listado de estrategias"
        >
          <span
            className="h-1 w-10 rounded-full bg-border transition-colors group-hover:bg-foreground/40"
            aria-hidden
          />
        </button>
      </div>

      {running ? (
        <div className="space-y-1.5 rounded-md border border-border/70 bg-background/80 px-2 py-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-medium">
              Lote en curso · {progress.done}/{progress.total}
            </p>
            <Button type="button" size="sm" variant="outline" className="h-7" onClick={onStop}>
              Parar
            </Button>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-[width] duration-300"
              style={{
                width:
                  progress.total > 0
                    ? `${Math.min(100, Math.round((progress.done / progress.total) * 100))}%`
                    : '0%',
              }}
            />
          </div>
          <p className="text-[10px] leading-snug text-muted-foreground">
            OK {progress.ok}
            {progress.error ? ` · Error ${progress.error}` : ''}
            {progress.skipped ? ` · Canceladas ${progress.skipped}` : ''}
            {progress.pending ? ` · En cola ${progress.pending}` : ''}
            {progress.runningLabels.length
              ? ` · Ahora: ${progress.runningLabels.join(', ')}`
              : ''}
            {typeof progress.elapsedMs === 'number'
              ? ` · ${progress.elapsedMs < 1000 ? `${progress.elapsedMs} ms` : `${(progress.elapsedMs / 1000).toFixed(1)} s`}`
              : ''}
          </p>
          <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
            Parar en cualquier momento: las pruebas no finalizadas no se guardan como resultado
            (quedan como canceladas). Las ya OK sí permanecen.
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          <Button
            className="w-full"
            size="sm"
            onClick={() => onRunCoach()}
            disabled={!canRunCoach}
            title="Simula las del filtro actual (o la selección) y abre el Coach. Reutiliza lote si no cambió."
          >
            Probar + coach ({coachCount})
          </Button>
          <Button
            className="w-full"
            size="sm"
            variant="outline"
            onClick={() => onRunCoach({ forceResim: true })}
            disabled={!canRunCoach}
            title="Ignora la reutilización del lote y vuelve a simular todas las del filtro/selección."
          >
            Forzar re-sim
          </Button>
          <p className="text-[10px] leading-snug text-muted-foreground">
            Ejecuta el filtro activo
            {coachCount > 0 ? ` (${coachCount})` : ''}: si hay filas marcadas, solo esas;
            si no, todas las visibles. «Forzar re-sim» ignora el lote cacheado. Periodo/capital en
            Opciones avanzadas.
          </p>
        </div>
      )}
    </div>
  );
}
