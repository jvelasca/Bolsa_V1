import type { ScanHitDto } from "@bolsa/shared";

export type ScanResultsColumnId =
  | "symbol"
  | "name"
  | "signal"
  | "rating"
  | "quality"
  | "dataQuality"
  | "globalScore"
  | "trend"
  | "momentum"
  | "volatility"
  | "meanReversion"
  | "pattern"
  | "price"
  | "bar"
  | "actions";

export interface ScanResultsColumnLayoutItem {
  id: ScanResultsColumnId;
  width: number;
  visible: boolean;
}

export type ScanResultsSortDirection = "asc" | "desc";

export interface ScanResultsSortState {
  columnId: ScanResultsColumnId;
  direction: ScanResultsSortDirection;
}

export const SCAN_RESULTS_COLUMN_LABELS: Record<ScanResultsColumnId, string> = {
  symbol: "Símbolo",
  name: "Nombre",
  signal: "Señal",
  rating: "Rating",
  quality: "Setup",
  dataQuality: "Datos",
  globalScore: "Global",
  trend: "Tendencia",
  momentum: "Momentum",
  volatility: "Volatilidad",
  meanReversion: "Reversión",
  pattern: "Patrón",
  price: "Precio",
  bar: "Barra",
  actions: "Acciones",
};

const MIN_WIDTH = 52;
const MAX_WIDTH = 420;

export function clampScanResultsColumnWidth(width: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(width)));
}

const BASE_DEFAULT_LAYOUT: ScanResultsColumnLayoutItem[] = [
  { id: "symbol", width: 96, visible: true },
  { id: "name", width: 148, visible: true },
  { id: "signal", width: 108, visible: true },
  { id: "rating", width: 72, visible: true },
  { id: "quality", width: 108, visible: true },
  { id: "dataQuality", width: 72, visible: true },
  { id: "globalScore", width: 72, visible: true },
  { id: "trend", width: 76, visible: true },
  { id: "momentum", width: 84, visible: true },
  { id: "volatility", width: 84, visible: true },
  { id: "meanReversion", width: 84, visible: true },
  { id: "pattern", width: 72, visible: true },
  { id: "price", width: 88, visible: true },
  { id: "bar", width: 118, visible: true },
  { id: "actions", width: 196, visible: true },
];

export function defaultScanResultsColumnLayout(options: {
  full: boolean;
  hasRating: boolean;
  hasBreakdown: boolean;
  hasDataQuality: boolean;
}): ScanResultsColumnLayoutItem[] {
  return BASE_DEFAULT_LAYOUT.map((column) => {
    if (column.id === "name" || column.id === "actions") {
      return { ...column, visible: options.full };
    }
    if (
      column.id === "rating" ||
      column.id === "quality" ||
      column.id === "dataQuality" ||
      column.id === "globalScore" ||
      column.id === "trend" ||
      column.id === "momentum" ||
      column.id === "volatility" ||
      column.id === "meanReversion" ||
      column.id === "pattern"
    ) {
      if (column.id === "rating" || column.id === "quality") {
        return { ...column, visible: options.hasRating };
      }
      if (column.id === "dataQuality" || column.id === "globalScore") {
        return { ...column, visible: options.hasDataQuality };
      }
      return { ...column, visible: options.hasBreakdown };
    }
    return { ...column };
  });
}

export function normalizeScanResultsLayout(
  stored: ScanResultsColumnLayoutItem[] | undefined,
  options: {
    full: boolean;
    hasRating: boolean;
    hasBreakdown: boolean;
    hasDataQuality: boolean;
  },
): ScanResultsColumnLayoutItem[] {
  const defaults = defaultScanResultsColumnLayout(options);
  if (!stored?.length) return defaults;

  const byId = new Map(stored.map((column) => [column.id, column]));
  const merged = defaults.map((defaultColumn) => {
    const saved = byId.get(defaultColumn.id);
    if (!saved) return defaultColumn;
    return {
      ...defaultColumn,
      width: clampScanResultsColumnWidth(saved.width),
      visible: saved.visible,
    };
  });

  for (const column of stored) {
    if (!merged.some((item) => item.id === column.id)) {
      merged.push({
        ...column,
        width: clampScanResultsColumnWidth(column.width),
      });
    }
  }
  return merged;
}

export function visibleScanResultsColumns(
  layout: ScanResultsColumnLayoutItem[],
): ScanResultsColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

export function buildScanResultsGridTemplate(
  visibleColumns: ScanResultsColumnLayoutItem[],
): string {
  if (visibleColumns.length === 0) return "minmax(0, 1fr)";
  const flexId = visibleColumns.some((column) => column.id === "name")
    ? "name"
    : visibleColumns.at(-1)?.id;
  return visibleColumns
    .map((column) =>
      column.id === flexId
        ? `minmax(${column.width}px, 1fr)`
        : `minmax(0, ${column.width}px)`,
    )
    .join(" ");
}

export function resizeScanResultsColumn(
  layout: ScanResultsColumnLayoutItem[],
  columnId: ScanResultsColumnId,
  width: number,
): ScanResultsColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampScanResultsColumnWidth(width) }
      : column,
  );
}

export function reorderScanResultsColumns(
  layout: ScanResultsColumnLayoutItem[],
  fromId: ScanResultsColumnId,
  toId: ScanResultsColumnId,
): ScanResultsColumnLayoutItem[] {
  const fromIndex = layout.findIndex((column) => column.id === fromId);
  const toIndex = layout.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  const next = [...layout];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved!);
  return next;
}

export const DEFAULT_SCAN_RESULTS_FAVORITE_COLUMN_IDS: ScanResultsColumnId[] = [
  "symbol",
  "signal",
  "rating",
  "globalScore",
];

export function toggleScanResultsFavoriteColumn(
  favoriteIds: ScanResultsColumnId[],
  columnId: ScanResultsColumnId,
): ScanResultsColumnId[] {
  const current = new Set(favoriteIds);
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);
  return BASE_DEFAULT_LAYOUT.map((column) => column.id).filter(
    (id) => id !== "actions" && current.has(id),
  );
}

export function toggleScanResultsColumn(
  layout: ScanResultsColumnLayoutItem[],
  columnId: ScanResultsColumnId,
): ScanResultsColumnLayoutItem[] {
  const next = layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
  if (!next.some((column) => column.visible && column.id !== "actions"))
    return layout;
  return next;
}

export function isNumericScanResultsColumn(
  columnId: ScanResultsColumnId,
): boolean {
  return (
    columnId === "rating" ||
    columnId === "dataQuality" ||
    columnId === "globalScore" ||
    columnId === "trend" ||
    columnId === "momentum" ||
    columnId === "volatility" ||
    columnId === "meanReversion" ||
    columnId === "pattern" ||
    columnId === "price"
  );
}

export function scanResultsColumnAlign(
  columnId: ScanResultsColumnId,
): "left" | "right" | "center" {
  if (columnId === "symbol" || columnId === "name") return "left";
  if (
    columnId === "signal" ||
    columnId === "quality" ||
    columnId === "dataQuality" ||
    columnId === "globalScore" ||
    columnId === "actions"
  ) {
    return "center";
  }
  return "right";
}

export function qualityFromScore(score: number): {
  label: string;
  className: string;
} {
  if (score >= 75) {
    return {
      label: "Alta",
      className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    };
  }
  if (score >= 60) {
    return {
      label: "Media-alta",
      className: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
    };
  }
  if (score >= 45) {
    return {
      label: "Media",
      className: "bg-amber-500/15 text-amber-800 dark:text-amber-300",
    };
  }
  return { label: "Baja", className: "bg-muted text-muted-foreground" };
}

function sortableValue(
  hit: ScanHitDto,
  columnId: ScanResultsColumnId,
): string | number | null {
  switch (columnId) {
    case "symbol":
      return hit.symbol;
    case "name":
      return hit.name;
    case "signal":
      return hit.signal.kind;
    case "rating":
      return hit.aiScore ?? null;
    case "quality":
      return hit.aiScore ?? null;
    case "dataQuality":
      return hit.dataQualityScore ?? null;
    case "globalScore":
      return hit.globalScore ?? null;
    case "trend":
      return hit.ratingBreakdown?.trend ?? null;
    case "momentum":
      return hit.ratingBreakdown?.momentum ?? null;
    case "volatility":
      return hit.ratingBreakdown?.volatility ?? null;
    case "meanReversion":
      return hit.ratingBreakdown?.meanReversion ?? null;
    case "pattern":
      return hit.ratingBreakdown?.pattern ?? null;
    case "price":
      return hit.signal.price;
    case "bar":
      return hit.signal.timestamp;
    default:
      return null;
  }
}

export function sortScanHits(
  hits: ScanHitDto[],
  sort: ScanResultsSortState | null,
): ScanHitDto[] {
  if (!sort || sort.columnId === "actions") return hits;
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...hits].sort((a, b) => {
    const left = sortableValue(a, sort.columnId);
    const right = sortableValue(b, sort.columnId);
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === "number" && typeof right === "number") {
      return (left - right) * direction;
    }
    return String(left).localeCompare(String(right), "es") * direction;
  });
}

export function cycleScanResultsSort(
  current: ScanResultsSortState | null,
  columnId: ScanResultsColumnId,
): ScanResultsSortState | null {
  if (columnId === "actions") return current;
  if (current?.columnId !== columnId) {
    return {
      columnId,
      direction: isNumericScanResultsColumn(columnId) ? "desc" : "asc",
    };
  }
  if (current.direction === "desc" && isNumericScanResultsColumn(columnId)) {
    return { columnId, direction: "asc" };
  }
  if (current.direction === "asc" && !isNumericScanResultsColumn(columnId)) {
    return { columnId, direction: "desc" };
  }
  return null;
}
