import type { StrategyMatrixRow } from '@/features/backtests/backtest-strategy-matrix';

export type StrategyMatrixColumnId =
  | 'label'
  | 'kind'
  | 'category'
  | 'status'
  | 'returnPct'
  | 'excessPct'
  | 'buyHoldPct'
  | 'drawdownPct'
  | 'tradeCount'
  | 'library'
  | 'remove'
  | 'actions';

export type StrategyMatrixColumnLayoutItem = {
  id: StrategyMatrixColumnId;
  width: number;
  visible: boolean;
};

export type StrategyMatrixSortDirection = 'asc' | 'desc';

export type StrategyMatrixSortState = {
  columnId: StrategyMatrixColumnId;
  direction: StrategyMatrixSortDirection;
};

export const STRATEGY_MATRIX_COLUMN_LABELS: Record<StrategyMatrixColumnId, string> = {
  label: 'Estrategia',
  kind: 'Tipo',
  category: 'Familia',
  status: 'Estado',
  returnPct: 'Retorno',
  excessPct: 'vs B&H',
  buyHoldPct: 'Buy & hold',
  drawdownPct: 'Drawdown',
  tradeCount: 'Ops',
  library: 'Biblio',
  remove: 'Borrar',
  actions: 'Ver',
};

export const STRATEGY_MATRIX_COLUMN_TIPS: Record<StrategyMatrixColumnId, string> = {
  label: 'Nombre de la estrategia (genérica o guardada). Arrastra la cabecera para reordenar columnas.',
  kind: 'Genérica = plantilla del catálogo. Mis estrategias = definición tuya (reutilizable o, más adelante, ajuste a un valor).',
  category: 'Familia de reglas (tendencia, momentum, reversión…).',
  status: 'Estado de la última prueba en esta sesión: cola, en curso, OK, error o cancelado.',
  returnPct: 'Rentabilidad total de la estrategia en el periodo (después de comisiones/slippage).',
  excessPct: 'Exceso vs comprar y mantener el valor en el mismo periodo. Positivo = batir al buy & hold.',
  buyHoldPct: 'Rentabilidad de comprar al inicio y mantener hasta el final (referencia).',
  drawdownPct: 'Máxima caída desde un pico de equity durante la prueba (más negativo = peor).',
  tradeCount: 'Número de operaciones (entradas/salidas) cerradas en la simulación.',
  library: 'Abrir esta estrategia en Biblioteca (ver definición, renombrar, duplicar, eliminar).',
  remove: 'Eliminar una estrategia guardada (Mis estrategias). No aplica a genéricas del catálogo.',
  actions: 'Abrir el detalle completo de la última prueba OK de esta fila (lo más importante).',
};

/** Columnas de acción: no ordenables; «Ver» (actions) fija el menú (…). */
export function isStrategyMatrixActionColumn(columnId: StrategyMatrixColumnId): boolean {
  return columnId === 'actions' || columnId === 'library' || columnId === 'remove';
}

const MIN_WIDTH = 48;
const MAX_WIDTH = 360;

export function clampStrategyMatrixColumnWidth(width: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(width)));
}

export const DEFAULT_STRATEGY_MATRIX_COLUMN_LAYOUT: StrategyMatrixColumnLayoutItem[] = [
  { id: 'label', width: 140, visible: true },
  { id: 'kind', width: 72, visible: false },
  { id: 'category', width: 88, visible: false },
  { id: 'status', width: 64, visible: false },
  { id: 'returnPct', width: 64, visible: true },
  { id: 'excessPct', width: 64, visible: true },
  { id: 'buyHoldPct', width: 72, visible: false },
  { id: 'drawdownPct', width: 72, visible: false },
  { id: 'tradeCount', width: 48, visible: true },
  { id: 'library', width: 56, visible: true },
  { id: 'remove', width: 56, visible: true },
  { id: 'actions', width: 52, visible: true },
];

export const DEFAULT_STRATEGY_MATRIX_FAVORITE_COLUMN_IDS: StrategyMatrixColumnId[] = [
  'label',
  'returnPct',
  'excessPct',
  'tradeCount',
  'library',
  'remove',
];

const ALL_IDS = DEFAULT_STRATEGY_MATRIX_COLUMN_LAYOUT.map((c) => c.id);

export function normalizeStrategyMatrixLayout(
  stored: StrategyMatrixColumnLayoutItem[] | undefined,
): StrategyMatrixColumnLayoutItem[] {
  const defaults = DEFAULT_STRATEGY_MATRIX_COLUMN_LAYOUT.map((c) => ({ ...c }));
  if (!stored?.length) return defaults;

  const byId = new Map(stored.map((column) => [column.id, column]));
  const ordered: StrategyMatrixColumnLayoutItem[] = [];
  const seen = new Set<StrategyMatrixColumnId>();

  for (const column of stored) {
    if (!ALL_IDS.includes(column.id) || seen.has(column.id)) continue;
    const fallback = defaults.find((d) => d.id === column.id)!;
    ordered.push({
      id: column.id,
      width: clampStrategyMatrixColumnWidth(column.width ?? fallback.width),
      visible: typeof column.visible === 'boolean' ? column.visible : fallback.visible,
    });
    seen.add(column.id);
  }

  for (const fallback of defaults) {
    if (seen.has(fallback.id)) continue;
    ordered.push({ ...fallback });
  }

  // Always keep at least label (+ actions can stay).
  if (!ordered.some((c) => c.visible && c.id === 'label')) {
    return ordered.map((c) => (c.id === 'label' ? { ...c, visible: true } : c));
  }
  return ordered;
}

export function normalizeStrategyMatrixFavorites(
  stored: StrategyMatrixColumnId[] | undefined,
): StrategyMatrixColumnId[] {
  const source = stored?.length ? stored : DEFAULT_STRATEGY_MATRIX_FAVORITE_COLUMN_IDS;
  // «Ver» (actions) no es favorito: fija el menú (…). Biblio/Borrar sí.
  const set = new Set(source.filter((id) => ALL_IDS.includes(id) && id !== 'actions'));
  return ALL_IDS.filter((id) => id !== 'actions' && set.has(id));
}

export function visibleStrategyMatrixColumns(
  layout: StrategyMatrixColumnLayoutItem[],
): StrategyMatrixColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

export function buildStrategyMatrixGridTemplate(
  visibleColumns: StrategyMatrixColumnLayoutItem[],
  selectWidthPx = 28,
): string {
  const data = visibleColumns
    .map((column) =>
      column.id === 'label'
        ? `minmax(${column.width}px, 1fr)`
        : `minmax(0, ${column.width}px)`,
    )
    .join(' ');
  return `${selectWidthPx}px ${data || 'minmax(0, 1fr)'}`;
}

export function resizeStrategyMatrixColumn(
  layout: StrategyMatrixColumnLayoutItem[],
  columnId: StrategyMatrixColumnId,
  width: number,
): StrategyMatrixColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampStrategyMatrixColumnWidth(width) }
      : column,
  );
}

export function reorderStrategyMatrixColumns(
  layout: StrategyMatrixColumnLayoutItem[],
  fromId: StrategyMatrixColumnId,
  toId: StrategyMatrixColumnId,
): StrategyMatrixColumnLayoutItem[] {
  // «Ver» (actions) ancla el menú (…) a la derecha: no reordenar.
  if (fromId === 'actions' || toId === 'actions') return layout;
  const fromIndex = layout.findIndex((column) => column.id === fromId);
  const toIndex = layout.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  const next = [...layout];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved!);
  return next;
}

export function toggleStrategyMatrixColumn(
  layout: StrategyMatrixColumnLayoutItem[],
  columnId: StrategyMatrixColumnId,
): StrategyMatrixColumnLayoutItem[] {
  // Label y Ver siempre visibles.
  if (columnId === 'label' || columnId === 'actions') return layout;
  const next = layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
  if (!next.some((column) => column.visible && column.id !== 'actions')) return layout;
  return next;
}

export function toggleStrategyMatrixFavoriteColumn(
  favoriteIds: StrategyMatrixColumnId[],
  columnId: StrategyMatrixColumnId,
): StrategyMatrixColumnId[] {
  if (columnId === 'actions') return favoriteIds;
  const current = new Set(favoriteIds);
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);
  return ALL_IDS.filter((id) => id !== 'actions' && current.has(id));
}

export function isNumericStrategyMatrixColumn(columnId: StrategyMatrixColumnId): boolean {
  return (
    columnId === 'returnPct' ||
    columnId === 'excessPct' ||
    columnId === 'buyHoldPct' ||
    columnId === 'drawdownPct' ||
    columnId === 'tradeCount'
  );
}

export function strategyMatrixColumnAlign(
  columnId: StrategyMatrixColumnId,
): 'left' | 'right' | 'center' {
  if (columnId === 'label' || columnId === 'kind' || columnId === 'category' || columnId === 'status') {
    return 'left';
  }
  if (isStrategyMatrixActionColumn(columnId)) return 'center';
  return 'right';
}

function statusRank(status: StrategyMatrixRow['status']): number {
  switch (status) {
    case 'running':
      return 5;
    case 'pending':
      return 4;
    case 'ok':
      return 3;
    case 'error':
      return 2;
    case 'skipped':
      return 1;
    default:
      return 0;
  }
}

function sortableValue(
  row: StrategyMatrixRow,
  columnId: StrategyMatrixColumnId,
): string | number | null {
  switch (columnId) {
    case 'label':
      return row.label;
    case 'kind':
      return row.kind;
    case 'category':
      return row.subtitle;
    case 'status':
      return statusRank(row.status);
    case 'returnPct':
      return row.totalReturnPct ?? null;
    case 'excessPct':
      return row.excessReturnPct ?? null;
    case 'buyHoldPct':
      return row.buyHoldReturnPct ?? null;
    case 'drawdownPct':
      return row.maxDrawdownPct ?? null;
    case 'tradeCount':
      return row.tradeCount ?? null;
    default:
      return null;
  }
}

export function sortStrategyMatrixRows(
  rows: StrategyMatrixRow[],
  sort: StrategyMatrixSortState | null,
): StrategyMatrixRow[] {
  if (!sort || isStrategyMatrixActionColumn(sort.columnId)) return rows;
  const direction = sort.direction === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = sortableValue(a, sort.columnId);
    const right = sortableValue(b, sort.columnId);
    if (left == null && right == null) return a.label.localeCompare(b.label, 'es');
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === 'number' && typeof right === 'number') {
      return (left - right) * direction;
    }
    return String(left).localeCompare(String(right), 'es') * direction;
  });
}

export function cycleStrategyMatrixSort(
  current: StrategyMatrixSortState | null,
  columnId: StrategyMatrixColumnId,
): StrategyMatrixSortState | null {
  if (isStrategyMatrixActionColumn(columnId)) return current;
  if (current?.columnId !== columnId) {
    return {
      columnId,
      direction: isNumericStrategyMatrixColumn(columnId) ? 'desc' : 'asc',
    };
  }
  if (current.direction === 'desc' && isNumericStrategyMatrixColumn(columnId)) {
    return { columnId, direction: 'asc' };
  }
  if (current.direction === 'asc' && !isNumericStrategyMatrixColumn(columnId)) {
    return { columnId, direction: 'desc' };
  }
  return null;
}

export function normalizeStrategyMatrixSort(
  stored: StrategyMatrixSortState | null | undefined,
): StrategyMatrixSortState | null {
  if (!stored) return null;
  if (!ALL_IDS.includes(stored.columnId) || isStrategyMatrixActionColumn(stored.columnId)) {
    return null;
  }
  if (stored.direction !== 'asc' && stored.direction !== 'desc') return null;
  return { columnId: stored.columnId, direction: stored.direction };
}
