export interface ChartDataStripFieldFlags {
  symbol: boolean;
  name: boolean;
  yahooSymbol: boolean;
  exchange: boolean;
  listSource: boolean;
  sector: boolean;
  volume: boolean;
}

export interface ChartDataStripOhlcFlags {
  enabled: boolean;
  open: boolean;
  high: boolean;
  low: boolean;
  close: boolean;
  changePct: boolean;
}

export interface ChartDataStripConfig {
  fields: ChartDataStripFieldFlags;
  ohlc: ChartDataStripOhlcFlags;
  /** Color CSS o `transparent` */
  backgroundColor: string;
  showTradeButtons: boolean;
  tradeButtonsPosition: 'left' | 'right';
}

export const CHART_DATA_STRIP_FIELD_LABELS: Record<keyof ChartDataStripFieldFlags, string> = {
  symbol: 'Símbolo',
  name: 'Nombre / descripción',
  yahooSymbol: 'Ticker Yahoo',
  exchange: 'Mercado',
  listSource: 'Lista de origen',
  sector: 'Sector',
  volume: 'Volumen',
};

export const CHART_DATA_STRIP_OHLC_LABELS: Record<
  keyof Omit<ChartDataStripOhlcFlags, 'enabled'>,
  string
> = {
  open: 'Apertura',
  high: 'Máximo',
  low: 'Mínimo',
  close: 'Cierre',
  changePct: '% variación',
};

export const DEFAULT_CHART_DATA_STRIP_CONFIG: ChartDataStripConfig = {
  fields: {
    symbol: true,
    name: true,
    yahooSymbol: false,
    exchange: false,
    listSource: true,
    sector: false,
    volume: true,
  },
  ohlc: {
    enabled: true,
    open: true,
    high: true,
    low: true,
    close: true,
    changePct: true,
  },
  backgroundColor: 'transparent',
  showTradeButtons: true,
  tradeButtonsPosition: 'right',
};

export function normalizeChartDataStripConfig(
  raw?: Partial<ChartDataStripConfig> | null,
): ChartDataStripConfig {
  const base = DEFAULT_CHART_DATA_STRIP_CONFIG;
  if (!raw) return { ...base, fields: { ...base.fields }, ohlc: { ...base.ohlc } };
  return {
    fields: { ...base.fields, ...raw.fields },
    ohlc: { ...base.ohlc, ...raw.ohlc },
    backgroundColor: raw.backgroundColor ?? base.backgroundColor,
    showTradeButtons: raw.showTradeButtons ?? base.showTradeButtons,
    tradeButtonsPosition: raw.tradeButtonsPosition ?? base.tradeButtonsPosition,
  };
}
