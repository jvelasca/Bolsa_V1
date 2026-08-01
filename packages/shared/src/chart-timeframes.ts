/** Base temporal de una pestaña de gráfico (alineado con TimeFrame Python / API). */
export type ChartTimeframe =
  | '1m'
  | '5m'
  | '15m'
  | '30m'
  | '1h'
  | '4h'
  | '1d'
  | '1wk'
  | '1mo';

export type ChartTimeframeCategory = 'minutes' | 'hours' | 'days';

export interface ChartTimeframeOption {
  id: ChartTimeframe;
  label: string;
  /** Etiqueta abreviada en botones de la barra (p. ej. 1D, 1W). */
  shortLabel: string;
  category: ChartTimeframeCategory;
  /** Si el backend puede servir datos hoy. */
  dataAvailable: boolean;
  hint?: string;
}

export const CHART_TIMEFRAME_OPTIONS: ChartTimeframeOption[] = [
  { id: '1m', label: '1 min', shortLabel: '1m', category: 'minutes', dataAvailable: true, hint: 'Yahoo → cache BD · ~7 días' },
  { id: '5m', label: '5 min', shortLabel: '5m', category: 'minutes', dataAvailable: true, hint: 'Yahoo → cache BD · ~30 días' },
  { id: '15m', label: '15 min', shortLabel: '15m', category: 'minutes', dataAvailable: true, hint: 'Yahoo → cache BD · ~30 días' },
  { id: '30m', label: '30 min', shortLabel: '30m', category: 'minutes', dataAvailable: true, hint: 'Yahoo → cache BD · ~30 días' },
  { id: '1h', label: '1 h', shortLabel: '1h', category: 'hours', dataAvailable: true, hint: 'Yahoo → cache BD · ~1 año' },
  { id: '4h', label: '4 h', shortLabel: '4h', category: 'hours', dataAvailable: true, hint: 'Yahoo → cache BD · ~1 año' },
  { id: '1d', label: '1 día', shortLabel: '1D', category: 'days', dataAvailable: true, hint: 'PostgreSQL (sync Yahoo)' },
  { id: '1wk', label: '1 semana', shortLabel: '1W', category: 'days', dataAvailable: true, hint: 'Yahoo → cache BD · ~5 años' },
  { id: '1mo', label: '1 mes', shortLabel: '1M', category: 'days', dataAvailable: true, hint: 'Yahoo → cache BD · ~10 años' },
];

export const CHART_TIMEFRAME_CATEGORY_LABELS: Record<ChartTimeframeCategory, string> = {
  minutes: 'Minutos',
  hours: 'Horas',
  days: 'Días',
};

export const DEFAULT_CHART_TIMEFRAME: ChartTimeframe = '1d';

/** Favoritos por defecto (acceso directo en barra). Vacío = solo icono con valor activo. */
export const DEFAULT_CHART_TIMEFRAME_FAVORITES: ChartTimeframe[] = [];

/** Grupos del menú de resolución temporal (separados visualmente). */
export const CHART_TIMEFRAME_MENU_GROUPS: ChartTimeframe[][] = [
  ['1m', '5m', '15m', '30m'],
  ['1h', '4h'],
  ['1d', '1wk', '1mo'],
];

export function isChartTimeframe(value: string): value is ChartTimeframe {
  return CHART_TIMEFRAME_OPTIONS.some((option) => option.id === value);
}

export function findChartTimeframeOption(id: ChartTimeframe): ChartTimeframeOption {
  return CHART_TIMEFRAME_OPTIONS.find((option) => option.id === id)!;
}

export function isIntradayChartTimeframe(timeframe: ChartTimeframe): boolean {
  return timeframe !== '1d' && timeframe !== '1wk' && timeframe !== '1mo';
}
