/**
 * Layout columnas hub Instrumentos — anchos, orden, visibilidad, favoritas.
 * Patrón alineado con scan-results-column-layout.
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 */

export type InstrumentsHubColumnId =
  | 'symbol'
  | 'price'
  | 'changePct'
  | 'lists'
  | 'portfolio'
  | 'scoreIo'
  | 'scoreFa'
  | 'scoreTa'
  | 'tracking'
  | 'lastBar'
  | 'data'
  | 'coach'
  | 'actions';

export interface InstrumentsHubColumnLayoutItem {
  id: InstrumentsHubColumnId;
  width: number;
  visible: boolean;
}

export type InstrumentsHubColumnSortDirection = 'asc' | 'desc';

export interface InstrumentsHubColumnSortState {
  columnId: InstrumentsHubColumnId;
  direction: InstrumentsHubColumnSortDirection;
}

export const INSTRUMENTS_HUB_COLUMN_LABELS: Record<InstrumentsHubColumnId, string> = {
  symbol: 'Activo',
  price: 'Precio',
  changePct: 'Δ%',
  lists: 'Listas',
  portfolio: 'Cartera',
  scoreIo: 'Recom.',
  scoreFa: 'FA',
  scoreTa: 'TA',
  tracking: 'Seguim.',
  lastBar: 'Últ. vela',
  data: 'Datos',
  coach: 'Coach',
  actions: 'Acciones',
};

const MIN_WIDTH = 52;
const MAX_WIDTH = 420;

export function clampInstrumentsHubColumnWidth(width: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(width)));
}

export const DEFAULT_INSTRUMENTS_HUB_COLUMN_LAYOUT: InstrumentsHubColumnLayoutItem[] = [
  { id: 'symbol', width: 148, visible: true },
  { id: 'price', width: 88, visible: true },
  { id: 'changePct', width: 72, visible: true },
  { id: 'lists', width: 128, visible: true },
  { id: 'portfolio', width: 100, visible: true },
  { id: 'scoreIo', width: 64, visible: true },
  { id: 'scoreFa', width: 52, visible: true },
  { id: 'scoreTa', width: 52, visible: true },
  { id: 'tracking', width: 140, visible: true },
  { id: 'lastBar', width: 118, visible: true },
  { id: 'data', width: 96, visible: true },
  { id: 'coach', width: 100, visible: true },
  { id: 'actions', width: 128, visible: true },
];

export const DEFAULT_INSTRUMENTS_HUB_FAVORITE_COLUMN_IDS: InstrumentsHubColumnId[] = [
  'symbol',
  'price',
  'changePct',
  'scoreIo',
  'scoreFa',
  'scoreTa',
  'tracking',
  'lastBar',
];

export function normalizeInstrumentsHubColumnLayout(
  stored: InstrumentsHubColumnLayoutItem[] | undefined,
): InstrumentsHubColumnLayoutItem[] {
  const defaults = DEFAULT_INSTRUMENTS_HUB_COLUMN_LAYOUT.map((c) => ({ ...c }));
  if (!stored?.length) return defaults;

  const ordered: InstrumentsHubColumnLayoutItem[] = [];
  const seen = new Set<InstrumentsHubColumnId>();

  for (const saved of stored) {
    const def = defaults.find((d) => d.id === saved.id);
    if (!def || seen.has(saved.id)) continue;
    ordered.push({
      id: saved.id,
      width: clampInstrumentsHubColumnWidth(saved.width ?? def.width),
      visible: typeof saved.visible === 'boolean' ? saved.visible : def.visible,
    });
    seen.add(saved.id);
  }

  for (const def of defaults) {
    if (seen.has(def.id)) continue;
    // Insertar columnas nuevas junto a su vecino por defecto (p. ej. Recom. tras Cartera).
    const defIndex = defaults.findIndex((d) => d.id === def.id);
    const prevId = defIndex > 0 ? defaults[defIndex - 1]!.id : null;
    const insertAt = prevId
      ? ordered.findIndex((c) => c.id === prevId) + 1
      : 0;
    if (insertAt > 0 && insertAt <= ordered.length) {
      ordered.splice(insertAt, 0, { ...def });
    } else {
      ordered.push({ ...def });
    }
    seen.add(def.id);
  }
  return ordered;
}

export function visibleInstrumentsHubColumns(
  layout: InstrumentsHubColumnLayoutItem[],
): InstrumentsHubColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

export function buildInstrumentsHubGridTemplate(
  visibleColumns: InstrumentsHubColumnLayoutItem[],
): string {
  if (visibleColumns.length === 0) return 'minmax(0, 1fr)';
  // Anchos fijos: cabecera y filas comparten la misma plantilla (alineación exacta).
  return visibleColumns.map((column) => `${column.width}px`).join(' ');
}

export function instrumentsHubGridMinWidth(
  visibleColumns: InstrumentsHubColumnLayoutItem[],
): number {
  return visibleColumns.reduce((sum, column) => sum + column.width, 0);
}

export function resizeInstrumentsHubColumn(
  layout: InstrumentsHubColumnLayoutItem[],
  columnId: InstrumentsHubColumnId,
  width: number,
): InstrumentsHubColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampInstrumentsHubColumnWidth(width) }
      : column,
  );
}

export function reorderInstrumentsHubColumns(
  layout: InstrumentsHubColumnLayoutItem[],
  fromId: InstrumentsHubColumnId,
  toId: InstrumentsHubColumnId,
): InstrumentsHubColumnLayoutItem[] {
  const fromIndex = layout.findIndex((column) => column.id === fromId);
  const toIndex = layout.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  const next = [...layout];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved!);
  return next;
}

export function toggleInstrumentsHubFavoriteColumn(
  favoriteIds: InstrumentsHubColumnId[],
  columnId: InstrumentsHubColumnId,
): InstrumentsHubColumnId[] {
  const current = new Set(favoriteIds);
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);
  return DEFAULT_INSTRUMENTS_HUB_COLUMN_LAYOUT.map((column) => column.id).filter(
    (id) => id !== 'actions' && current.has(id),
  );
}

export function toggleInstrumentsHubColumn(
  layout: InstrumentsHubColumnLayoutItem[],
  columnId: InstrumentsHubColumnId,
): InstrumentsHubColumnLayoutItem[] {
  if (columnId === 'symbol' || columnId === 'actions') return layout;
  const next = layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
  if (!next.some((column) => column.visible && column.id !== 'actions')) return layout;
  return next;
}

export function isNumericInstrumentsHubColumn(columnId: InstrumentsHubColumnId): boolean {
  return (
    columnId === 'price' ||
    columnId === 'changePct' ||
    columnId === 'lists' ||
    columnId === 'portfolio' ||
    columnId === 'scoreIo' ||
    columnId === 'scoreFa' ||
    columnId === 'scoreTa' ||
    columnId === 'tracking' ||
    columnId === 'data'
  );
}

export function instrumentsHubColumnAlign(
  columnId: InstrumentsHubColumnId,
): 'left' | 'right' | 'center' {
  if (columnId === 'symbol' || columnId === 'lists' || columnId === 'tracking' || columnId === 'data') {
    return 'left';
  }
  if (columnId === 'coach' || columnId === 'actions') return 'center';
  return 'right';
}

export function isSortableInstrumentsHubColumn(columnId: InstrumentsHubColumnId): boolean {
  return columnId !== 'actions' && columnId !== 'coach';
}

export function cycleInstrumentsHubColumnSort(
  current: InstrumentsHubColumnSortState | null,
  columnId: InstrumentsHubColumnId,
): InstrumentsHubColumnSortState | null {
  if (!isSortableInstrumentsHubColumn(columnId)) return current;
  if (current?.columnId !== columnId) {
    return {
      columnId,
      direction: isNumericInstrumentsHubColumn(columnId) || columnId === 'lastBar' ? 'desc' : 'asc',
    };
  }
  if (current.direction === 'asc') return { columnId, direction: 'desc' };
  return { columnId, direction: 'asc' };
}

/** Mapea id de columna → clave de sort del modelo hub. */
export function instrumentsHubSortKeyFromColumn(
  columnId: InstrumentsHubColumnId,
):
  | 'symbol'
  | 'lastClose'
  | 'changePct'
  | 'listCount'
  | 'unrealizedPnl'
  | 'scoreIo'
  | 'scoreFa'
  | 'scoreTa'
  | 'trackerCount'
  | 'barCount'
  | 'lastBar'
  | null {
  switch (columnId) {
    case 'symbol':
      return 'symbol';
    case 'price':
      return 'lastClose';
    case 'changePct':
      return 'changePct';
    case 'lists':
      return 'listCount';
    case 'portfolio':
      return 'unrealizedPnl';
    case 'scoreIo':
      return 'scoreIo';
    case 'scoreFa':
      return 'scoreFa';
    case 'scoreTa':
      return 'scoreTa';
    case 'tracking':
      return 'trackerCount';
    case 'data':
      return 'barCount';
    case 'lastBar':
      return 'lastBar';
    default:
      return null;
  }
}

/** Formato última vela: fecha (+ hora si viene en ISO) · sync opcional. */
export function formatInstrumentLastBarLabel(opts: {
  lastBarDate?: string | null;
  lastSyncAt?: string | null;
}): { primary: string; secondary?: string; sortKey: string | null } {
  const bar = opts.lastBarDate?.trim() || null;
  const sync = opts.lastSyncAt?.trim() || null;

  if (!bar && !sync) {
    return { primary: '—', sortKey: null };
  }

  if (bar && bar.includes('T')) {
    const d = new Date(bar);
    if (!Number.isNaN(d.getTime())) {
      return {
        primary: d.toLocaleString('es-ES', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
        sortKey: d.toISOString(),
      };
    }
  }

  if (bar) {
    const d = new Date(`${bar.slice(0, 10)}T12:00:00`);
    const dateLabel = Number.isNaN(d.getTime())
      ? bar.slice(0, 10)
      : d.toLocaleDateString('es-ES', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
        });
    let timeLabel: string | undefined;
    if (sync) {
      const s = new Date(sync);
      if (!Number.isNaN(s.getTime())) {
        timeLabel = s.toLocaleTimeString('es-ES', {
          hour: '2-digit',
          minute: '2-digit',
        });
      }
    }
    return {
      primary: timeLabel ? `${dateLabel} · ${timeLabel}` : dateLabel,
      secondary: sync
        ? `Sync ${new Date(sync).toLocaleString('es-ES', {
            day: '2-digit',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
          })}`
        : undefined,
      sortKey: bar.slice(0, 10) + (sync ?? ''),
    };
  }

  const s = new Date(sync!);
  return {
    primary: Number.isNaN(s.getTime())
      ? sync!
      : s.toLocaleString('es-ES', {
          day: '2-digit',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        }),
    secondary: 'Solo sync (sin vela)',
    sortKey: sync,
  };
}

const FIT_CELL_PAD = 24;
/** Grip + icono orden + huecos en cabecera (debe caber la etiqueta completa). */
const FIT_HEADER_CHROME = 40;
const FIT_FONT = '600 11px ui-sans-serif, system-ui, sans-serif';

let measureCanvas: HTMLCanvasElement | null = null;

export function measureInstrumentsHubTextWidth(text: string): number {
  const fallback = Math.ceil(text.length * 7.2);
  if (typeof document === 'undefined') return fallback;
  if (typeof process !== 'undefined' && process.env.VITEST) return fallback;
  try {
    if (!measureCanvas) measureCanvas = document.createElement('canvas');
    const ctx = measureCanvas.getContext('2d');
    if (!ctx) return fallback;
    ctx.font = FIT_FONT;
    return Math.ceil(ctx.measureText(text).width);
  } catch {
    return fallback;
  }
}

/**
 * Ajusta anchos al contenido de filas **y** al texto de cabecera (misma métrica).
 */
export function fitInstrumentsHubColumnsToContent(
  layout: InstrumentsHubColumnLayoutItem[],
  contentSamples: Partial<Record<InstrumentsHubColumnId, string[]>>,
): InstrumentsHubColumnLayoutItem[] {
  return layout.map((column) => {
    const header = INSTRUMENTS_HUB_COLUMN_LABELS[column.id];
    const headerW =
      measureInstrumentsHubTextWidth(header) + FIT_CELL_PAD + FIT_HEADER_CHROME;
    const samples = contentSamples[column.id] ?? [];
    let contentW = 0;
    for (const sample of samples) {
      if (!sample) continue;
      contentW = Math.max(contentW, measureInstrumentsHubTextWidth(sample) + FIT_CELL_PAD);
    }
    // La cabecera cuenta como muestra más (por si el label es más largo que las celdas).
    contentW = Math.max(contentW, measureInstrumentsHubTextWidth(header) + FIT_CELL_PAD);
    const floor =
      column.id === 'actions'
        ? 120
        : column.id === 'scoreFa' || column.id === 'scoreTa' || column.id === 'scoreIo'
          ? 52
          : MIN_WIDTH;
    const width = clampInstrumentsHubColumnWidth(Math.max(floor, headerW, contentW));
    return { ...column, width };
  });
}
