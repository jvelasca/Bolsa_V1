export type ChartSeriesType =
  | 'bars'
  | 'candles'
  | 'hollow-candles'
  | 'volume-candles'
  | 'hlc-bars'
  | 'line'
  | 'line-markers'
  | 'line-step'
  | 'area'
  | 'area-hlc'
  | 'baseline'
  | 'columns'
  | 'high-low'
  | 'heikin-ashi'
  | 'renko'
  | 'line-break'
  | 'kagi'
  | 'point-and-figure';

export type ChartSeriesTypeMenuEntry =
  | { kind: 'type'; id: ChartSeriesType }
  | { kind: 'separator' };

export interface ChartSeriesTypeOption {
  id: ChartSeriesType;
  label: string;
  shortLabel: string;
  /** Fase de implementación en el motor de gráficos. */
  implementationPhase: 1 | 2 | 3 | 4;
  description?: string;
}

export const CHART_SERIES_TYPE_OPTIONS: Record<ChartSeriesType, ChartSeriesTypeOption> = {
  bars: {
    id: 'bars',
    label: 'Barras',
    shortLabel: 'Barras',
    implementationPhase: 1,
  },
  candles: {
    id: 'candles',
    label: 'Velas',
    shortLabel: 'Velas',
    implementationPhase: 1,
  },
  'hollow-candles': {
    id: 'hollow-candles',
    label: 'Velas huecas',
    shortLabel: 'Huecas',
    implementationPhase: 2,
  },
  'volume-candles': {
    id: 'volume-candles',
    label: 'Velas de volumen',
    shortLabel: 'Vol. velas',
    implementationPhase: 3,
  },
  'hlc-bars': {
    id: 'hlc-bars',
    label: 'Barras HLC (máx., mín., cierre)',
    shortLabel: 'HLC',
    implementationPhase: 2,
  },
  line: {
    id: 'line',
    label: 'Línea',
    shortLabel: 'Línea',
    implementationPhase: 1,
  },
  'line-markers': {
    id: 'line-markers',
    label: 'Línea con marcadores',
    shortLabel: 'Línea ●',
    implementationPhase: 2,
  },
  'line-step': {
    id: 'line-step',
    label: 'Línea escalonada',
    shortLabel: 'Escalón',
    implementationPhase: 2,
  },
  area: {
    id: 'area',
    label: 'Área',
    shortLabel: 'Área',
    implementationPhase: 2,
  },
  'area-hlc': {
    id: 'area-hlc',
    label: 'Área HLC',
    shortLabel: 'Área HLC',
    implementationPhase: 2,
  },
  baseline: {
    id: 'baseline',
    label: 'Línea de referencia',
    shortLabel: 'Referencia',
    implementationPhase: 2,
  },
  columns: {
    id: 'columns',
    label: 'Columnas',
    shortLabel: 'Columnas',
    implementationPhase: 2,
  },
  'high-low': {
    id: 'high-low',
    label: 'Máx.-mín.',
    shortLabel: 'Máx-mín',
    implementationPhase: 2,
  },
  'heikin-ashi': {
    id: 'heikin-ashi',
    label: 'Heikin-Ashi',
    shortLabel: 'HA',
    implementationPhase: 3,
  },
  renko: {
    id: 'renko',
    label: 'Renko',
    shortLabel: 'Renko',
    implementationPhase: 4,
    description: 'Requiere tamaño de ladrillo',
  },
  'line-break': {
    id: 'line-break',
    label: 'Ruptura de línea',
    shortLabel: 'Ruptura',
    implementationPhase: 4,
  },
  kagi: {
    id: 'kagi',
    label: 'Kagi',
    shortLabel: 'Kagi',
    implementationPhase: 4,
  },
  'point-and-figure': {
    id: 'point-and-figure',
    label: 'Punto y figura',
    shortLabel: 'P&F',
    implementationPhase: 4,
    description: 'Requiere caja y reversión',
  },
};

/** Orden del menú desplegable (con separadores). */
export const CHART_SERIES_TYPE_MENU: ChartSeriesTypeMenuEntry[] = [
  { kind: 'type', id: 'bars' },
  { kind: 'type', id: 'candles' },
  { kind: 'type', id: 'hollow-candles' },
  { kind: 'type', id: 'volume-candles' },
  { kind: 'type', id: 'hlc-bars' },
  { kind: 'separator' },
  { kind: 'type', id: 'line' },
  { kind: 'type', id: 'line-markers' },
  { kind: 'type', id: 'line-step' },
  { kind: 'separator' },
  { kind: 'type', id: 'area' },
  { kind: 'type', id: 'area-hlc' },
  { kind: 'type', id: 'baseline' },
  { kind: 'separator' },
  { kind: 'type', id: 'columns' },
  { kind: 'type', id: 'high-low' },
  { kind: 'separator' },
  { kind: 'type', id: 'heikin-ashi' },
  { kind: 'type', id: 'renko' },
  { kind: 'type', id: 'line-break' },
  { kind: 'type', id: 'kagi' },
  { kind: 'type', id: 'point-and-figure' },
];

/** Grupos del menú de estilo (separados visualmente en la barra). */
export const CHART_SERIES_TYPE_MENU_GROUPS: ChartSeriesType[][] = (() => {
  const groups: ChartSeriesType[][] = [];
  let current: ChartSeriesType[] = [];
  for (const entry of CHART_SERIES_TYPE_MENU) {
    if (entry.kind === 'separator') {
      if (current.length > 0) groups.push(current);
      current = [];
    } else {
      current.push(entry.id);
    }
  }
  if (current.length > 0) groups.push(current);
  return groups;
})();

export const DEFAULT_CHART_SERIES_TYPE: ChartSeriesType = 'candles';

/** Vacío = solo icono con estilo activo; chips opcionales vía estrella. */
export const DEFAULT_CHART_SERIES_TYPE_FAVORITES: ChartSeriesType[] = [];

const SERIES_TYPE_SET = new Set<string>(Object.keys(CHART_SERIES_TYPE_OPTIONS));

export function isChartSeriesType(value: string): value is ChartSeriesType {
  return SERIES_TYPE_SET.has(value);
}

/** Parámetros de tipos avanzados (Renko, P&F, etc.). */
export interface ChartSeriesTypeParams {
  renkoBrickSize?: number;
  pointAndFigureBox?: number;
  pointAndFigureReversal?: number;
  lineBreakLines?: number;
  kagiReversal?: number;
}

export function normalizeChartSeriesType(
  raw?: ChartSeriesType | string | null,
  fallback: ChartSeriesType = DEFAULT_CHART_SERIES_TYPE,
): ChartSeriesType {
  return raw && isChartSeriesType(raw) ? raw : fallback;
}

export function normalizeChartSeriesTypeParams(
  raw?: ChartSeriesTypeParams | null,
): ChartSeriesTypeParams {
  return raw ? { ...raw } : {};
}

export function seriesTypeRequiresParams(seriesType: ChartSeriesType): boolean {
  return CHART_SERIES_TYPE_OPTIONS[seriesType].implementationPhase >= 4;
}

export function findChartSeriesTypeOption(id: ChartSeriesType): ChartSeriesTypeOption {
  return CHART_SERIES_TYPE_OPTIONS[id];
}

export function normalizeChartSeriesTypeFavorites(
  raw?: ChartSeriesType[] | null,
): ChartSeriesType[] {
  if (raw == null) return [...DEFAULT_CHART_SERIES_TYPE_FAVORITES];
  return raw.filter((item) => isChartSeriesType(item));
}

export function toggleChartSeriesTypeFavoriteList(
  favorites: ChartSeriesType[],
  seriesType: ChartSeriesType,
): ChartSeriesType[] {
  if (favorites.includes(seriesType)) {
    return favorites.filter((item) => item !== seriesType);
  }
  return [...favorites, seriesType];
}

export function isChartSeriesTypeImplemented(
  seriesType: ChartSeriesType,
  maxPhase: 1 | 2 | 3 | 4 = 4,
): boolean {
  return CHART_SERIES_TYPE_OPTIONS[seriesType].implementationPhase <= maxPhase;
}

const SYNTHETIC_TIME_SERIES_TYPES = new Set<ChartSeriesType>([
  'renko',
  'line-break',
  'kagi',
  'point-and-figure',
]);

/** Tipos cuyo eje temporal no coincide 1:1 con las velas OHLC originales. */
export function chartSeriesUsesSyntheticTime(seriesType: ChartSeriesType): boolean {
  return SYNTHETIC_TIME_SERIES_TYPES.has(seriesType);
}
