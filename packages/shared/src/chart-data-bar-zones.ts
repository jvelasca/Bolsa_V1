import type { ChartDataStripFieldFlags } from './chart-data-strip.js';

/** Campos de la zona de instrumento (metadatos del valor). */
export type ChartInstrumentBarField = Exclude<keyof ChartDataStripFieldFlags, 'volume'>;

/** Campos de la zona de cursor (precio / vela bajo el puntero). */
export type ChartCursorBarField =
  | 'open'
  | 'high'
  | 'low'
  | 'close'
  | 'changePct'
  | 'volume';

export const CHART_INSTRUMENT_BAR_FIELDS: ChartInstrumentBarField[] = [
  'symbol',
  'name',
  'yahooSymbol',
  'exchange',
  'sector',
  'listSource',
];

export const CHART_CURSOR_BAR_FIELDS: ChartCursorBarField[] = [
  'open',
  'high',
  'low',
  'close',
  'changePct',
  'volume',
];

export const CHART_INSTRUMENT_FIELD_LABELS: Record<ChartInstrumentBarField, string> = {
  symbol: 'Símbolo',
  name: 'Nombre',
  yahooSymbol: 'Ticker Yahoo',
  exchange: 'Mercado',
  sector: 'Sector',
  listSource: 'Lista origen',
};

export const CHART_INSTRUMENT_FIELD_SHORT_LABELS: Record<ChartInstrumentBarField, string> = {
  symbol: 'Sym',
  name: 'Nom',
  yahooSymbol: 'Yahoo',
  exchange: 'Mkt',
  sector: 'Sec',
  listSource: 'Lista',
};

export const CHART_CURSOR_FIELD_LABELS: Record<ChartCursorBarField, string> = {
  open: 'Apertura (O)',
  high: 'Máximo (H)',
  low: 'Mínimo (L)',
  close: 'Cierre (C)',
  changePct: 'Δ vela',
  volume: 'Volumen',
};

export const CHART_CURSOR_FIELD_SHORT_LABELS: Record<ChartCursorBarField, string> = {
  open: 'O',
  high: 'H',
  low: 'L',
  close: 'C',
  changePct: 'Δ',
  volume: 'Vol',
};

export const CHART_INSTRUMENT_FIELD_TIPS: Record<ChartInstrumentBarField, string> = {
  symbol: 'Ticker corto del valor en bolsa.',
  name: 'Razón social o descripción del instrumento.',
  yahooSymbol: 'Símbolo usado en Yahoo Finance para datos históricos.',
  exchange: 'Mercado o bolsa donde cotiza.',
  sector: 'Sector o industria de clasificación.',
  listSource: 'Lista desde la que abriste este gráfico.',
};

export const CHART_CURSOR_FIELD_TIPS: Record<ChartCursorBarField, string> = {
  open: 'Precio de apertura (O) de la vela bajo el cursor.',
  high: 'Máximo (H) de la vela bajo el cursor.',
  low: 'Mínimo (L) de la vela bajo el cursor.',
  close: 'Cierre (C) de la vela bajo el cursor (ancla de la zona).',
  changePct:
    'Variación de la vela bajo el cursor: cierre − apertura (moneda y %). En listas el % es vs el cierre anterior.',
  volume: 'Volumen negociado en la vela bajo el cursor.',
};

export const CHART_INSTRUMENT_BAR_MENU_GROUPS: ChartInstrumentBarField[][] = [
  ['symbol', 'name', 'yahooSymbol'],
  ['exchange', 'sector', 'listSource'],
];

export const CHART_CURSOR_BAR_MENU_GROUPS: ChartCursorBarField[][] = [
  ['open', 'high', 'low', 'close'],
  ['changePct', 'volume'],
];

/** Ancla fija de cada zona (siempre visible en la barra). */
export const CHART_INSTRUMENT_BAR_ANCHOR: ChartInstrumentBarField = 'symbol';
export const CHART_CURSOR_BAR_ANCHOR: ChartCursorBarField = 'close';

export const DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES: ChartInstrumentBarField[] = [
  'name',
  'listSource',
];

export const DEFAULT_CHART_CURSOR_FIELD_FAVORITES: ChartCursorBarField[] = [
  'open',
  'high',
  'low',
  'changePct',
];

const INSTRUMENT_FIELD_SET = new Set<string>(CHART_INSTRUMENT_BAR_FIELDS);
const CURSOR_FIELD_SET = new Set<string>(CHART_CURSOR_BAR_FIELDS);

export function isChartInstrumentBarField(value: string): value is ChartInstrumentBarField {
  return INSTRUMENT_FIELD_SET.has(value);
}

export function isChartCursorBarField(value: string): value is ChartCursorBarField {
  return CURSOR_FIELD_SET.has(value);
}

export function normalizeChartInstrumentFieldFavorites(
  raw?: ChartInstrumentBarField[] | null,
): ChartInstrumentBarField[] {
  if (!raw?.length) return [...DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES];
  const valid = raw.filter(isChartInstrumentBarField);
  return valid.length > 0 ? valid : [...DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES];
}

export function normalizeChartCursorFieldFavorites(
  raw?: ChartCursorBarField[] | null,
): ChartCursorBarField[] {
  if (!raw?.length) return [...DEFAULT_CHART_CURSOR_FIELD_FAVORITES];
  const valid = raw.filter(isChartCursorBarField);
  return valid.length > 0 ? valid : [...DEFAULT_CHART_CURSOR_FIELD_FAVORITES];
}

export function toggleBarZoneFavoriteList<T extends string>(
  favorites: T[],
  item: T,
  anchor: T,
): T[] {
  if (item === anchor) return favorites;
  if (favorites.includes(item)) {
    const next = favorites.filter((entry) => entry !== item);
    return next.length > 0 ? next : favorites;
  }
  return [...favorites, item];
}
