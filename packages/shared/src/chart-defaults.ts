import type { ChartDrawing } from './chart-drawings.js';
import type {
  ListHubColumnId,
  ListHubColumnLayoutItem,
  ListHubSortState,
  WatchlistPanelTab,
} from './list-hub-columns.js';
import type { ChartListContext, ChartInstrumentSnapshot } from './chart-list-context.js';
import type { ChartDataStripConfig } from './chart-data-strip.js';
import type { ChartSeriesType, ChartSeriesTypeParams } from './chart-series-type.js';
import { DEFAULT_CHART_SERIES_TYPE, normalizeChartSeriesType, normalizeChartSeriesTypeParams } from './chart-series-type.js';
import type {
  ChartToolbarChartOverrides,
  ChartToolbarGlobalConfig,
} from './chart-toolbar.js';
import type { ChartDrawingTemplate } from './chart-drawing-templates.js';
import type { IndicatorFavoriteRef, IndicatorTemplate } from './indicator-templates.js';
import type { IndicatorPreset } from './indicator-presets.js';
import type { ChartDrawTool } from './chart-drawings.js';
import type { ChartTimeframe } from './chart-timeframes.js';
import { DEFAULT_CHART_TIMEFRAME } from './chart-timeframes.js';
import type { ChartIndicatorInstance } from './indicators-catalog.js';
import type { ChartNewTabSeed, NewChartConfigSource } from './chart-new-tab-setup.js';
import { normalizeChartNewTabSeed, normalizeNewChartConfigSource } from './chart-new-tab-setup.js';

export type ListColumnId =
  | 'symbol'
  | 'name'
  | 'lastClose'
  | 'changePct'
  | 'isin'
  | 'syncStatus'
  /** Capas Lab/CORE-R/redescubrir (3 iconos). Off por defecto. */
  | 'processStatus'
  /** Última pasada Lab / Finalistas. Off por defecto. */
  | 'lastLabAt'
  /** Último juicio / encolado CORE-R. Off por defecto. */
  | 'lastCoreRAt'
  /** Índice Operativo 0–100 (recomendación). Off por defecto. */
  | 'ioScore'
  /** Pierna técnica 0–100. Off por defecto. */
  | 'taScore'
  /** Pierna fundamental 0–100. Off por defecto. */
  | 'faScore'
  /** ★ dictamen diario. Off por defecto. */
  | 'dictamenStars'
  /** Postura del dictamen (buy / vigilar…). Off por defecto. */
  | 'recStance';

export interface ChartGridConfig {
  showVertical: boolean;
  showHorizontal: boolean;
  rightMarginPct: number;
  topMarginPct: number;
  /** Zoom vertical del eje de precio (0.5–3, 1 = normal). */
  priceScaleZoom?: number;
}

export interface ChartCursorConfig {
  mode: 'crosshair' | 'magnet';
  showOhlcInTooltip: boolean;
  /** Etiqueta de fecha/hora al pasar sobre el eje temporal (X). */
  showTimeAxisLabel?: boolean;
}

export interface ChartColorsConfig {
  upColor: string;
  downColor: string;
  gridColor: string;
  textColor: string;
  volumeUpColor: string;
  volumeDownColor: string;
  sma20Color: string;
  sma50Color: string;
  ema20Color: string;
  rsi14Color: string;
}

export interface ChartDisplayConfig {
  showVolume: boolean;
  showSma20: boolean;
  showSma50: boolean;
  showEma20: boolean;
  showRsi14: boolean;
  /** Altura fija (px) cuando el gráfico no rellena el contenedor padre */
  height: number;
}

export interface ChartInstanceConfig {
  id: string;
  grid: ChartGridConfig;
  cursor: ChartCursorConfig;
  colors: ChartColorsConfig;
  display: ChartDisplayConfig;
}

export interface ListColumnLayoutItem {
  id: ListColumnId;
  /** Ancho en píxeles */
  width: number;
  visible: boolean;
}

export interface ListPanelConfig {
  id: string;
  name: string;
  source: 'catalog' | 'api' | 'virtual';
  /** ID de lista en API cuando source === 'api' */
  apiListId?: string;
  /** Columnas visibles en orden (derivado de columnLayout) */
  columns: ListColumnId[];
  /** Orden, visibilidad y ancho de todas las columnas */
  columnLayout?: ListColumnLayoutItem[];
  /** Layout de columnas por ID de lista (virtual o API) */
  columnLayoutsByListId?: Record<string, ListColumnLayoutItem[]>;
  /** Ordenación activa por ID de lista */
  sortByListId?: Record<string, ListSortState>;
  /** IDs de listas API fijadas en el carrusel (las virtuales siempre se muestran) */
  carouselListIds?: string[];
  /** Nombres de listas API fijadas (sobrevive a cambios de ID tras reseed de BD). */
  carouselPinnedListNames?: string[];
  /** Listas ocultas del carrusel (incluye virtuales desmarcadas). */
  carouselHiddenListIds?: string[];
  /** Evita re-sembrar IBEX tras desmarcar listas en el carrusel */
  carouselInitialized?: boolean;
  /** Ancho de la zona de botones por fila (px). */
  rowActionsWidth?: number;
  /** Contenido de la lista virtual Visualización (persistido entre sesiones). */
  visualizationEntries?: VisualizationPersistedEntry[];
  /** Pestaña activa del panel watchlist. */
  watchlistTab?: WatchlistPanelTab;
  /** Columnas del hub de listas (pestaña Listas). */
  hubColumnLayout?: ListHubColumnLayoutItem[];
  /** Columnas favoritas del hub (atajo en menú de configuración). */
  hubFavoriteColumnIds?: ListHubColumnId[];
  /** Ordenación del hub de listas. */
  hubSort?: ListHubSortState;
  /** Ancho zona de acciones por fila en hub de listas (px). */
  hubRowActionsWidth?: number;
  /** Columnas favoritas por lista (pestaña Valores). */
  favoriteColumnIdsByListId?: Record<string, ListColumnId[]>;
}

export const DEFAULT_LIST_ROW_ACTIONS_WIDTH = 72;
export const MIN_LIST_ROW_ACTIONS_WIDTH = 56;
export const MAX_LIST_ROW_ACTIONS_WIDTH = 112;

export function clampListRowActionsWidth(width: number): number {
  return Math.min(
    MAX_LIST_ROW_ACTIONS_WIDTH,
    Math.max(MIN_LIST_ROW_ACTIONS_WIDTH, Math.round(width)),
  );
}

export function resolveListRowActionsWidth(width: number | undefined): number {
  return clampListRowActionsWidth(width ?? DEFAULT_LIST_ROW_ACTIONS_WIDTH);
}

export interface ListSortState {
  column: ListColumnId;
  direction: 'asc' | 'desc';
}

/** Instrumento en la lista virtual Visualización (persistido en workspace). */
export interface VisualizationPersistedEntry {
  instrumentId: string;
  symbol: string;
  name: string;
  firstViewedAt: string;
  lastViewedAt: string;
  viewCount: number;
  lastSearchQuery?: string;
}

export interface ChartTabState {
  id: string;
  instrumentId: string;
  label: string;
  timeframe: ChartTimeframe;
  /** Tipo de representación del precio (velas, barras, línea…). */
  seriesType: ChartSeriesType;
  /** Parámetros para tipos avanzados (Renko, P&F…). */
  seriesTypeParams?: ChartSeriesTypeParams;
  chart: ChartInstanceConfig;
  indicatorInstances: ChartIndicatorInstance[];
  drawings: ChartDrawing[];
  /** Ocultar capa de dibujos sin borrarlos. */
  drawingsLayerHidden?: boolean;
  /** Bloquear todos los dibujos del tab. */
  drawingsLayerLocked?: boolean;
  /** Lista desde la que se abrió este gráfico. */
  sourceListId?: string;
  /** Plantilla de indicadores aplicada a este gráfico (independiente de estrategias). */
  activeIndicatorTemplateId?: string | null;
  /**
   * Switch barra Indicadores: pintar indicadores del Finalista TOP #1
   * (mismo TF que el gráfico). Las instancias llevan `origin: 'finalist-top1'`.
   * Independiente del default workspace (`preferences.finalistTop1DefaultOn`).
   */
  showFinalistTop1Indicators?: boolean;
  /** Personalización de la barra de herramientas de este gráfico. */
  toolbar?: ChartToolbarChartOverrides;
  /** Alto del panel de precio (% del stack precio + indicadores inferiores). */
  pricePanelHeightPct?: number;
}

export const DEFAULT_PRICE_PANEL_HEIGHT_PCT = 55;
export const MIN_PRICE_PANEL_HEIGHT_PCT = 25;
export const MAX_PRICE_PANEL_HEIGHT_PCT = 85;

export function clampPricePanelHeightPct(value: number): number {
  return Math.min(
    MAX_PRICE_PANEL_HEIGHT_PCT,
    Math.max(MIN_PRICE_PANEL_HEIGHT_PCT, Math.round(value)),
  );
}

export function resolvePricePanelHeightPct(value: number | undefined): number {
  return clampPricePanelHeightPct(value ?? DEFAULT_PRICE_PANEL_HEIGHT_PCT);
}

export interface WorkspaceDocument {
  version: 1;
  id: string;
  name: string;
  updatedAt: string;
  layout: {
    listPanelOpen: boolean;
    listPanelSizePct: number;
    rightPanelOpen: boolean;
    rightPanelSizePct: number;
    /** Panel inspector de objetos gráficos (derecha del gráfico). */
    chartInspectorOpen: boolean;
    activeRoute: string;
  };
  preferences: {
    autoSave: boolean;
    openOnStartup: boolean;
    /** Pestaña plantilla para gráficos nuevos; `null` = defaults del workspace. */
    newChartTemplateChartId?: string | null;
    /**
     * Si true, los gráficos nuevos (y el switch «todos» de la barra general)
     * activan el overlay Finalista TOP #1. Cada gráfico puede desactivarlo solo.
     */
    finalistTop1DefaultOn?: boolean;
    /** @deprecated Usar `newChartTemplateChartId`. */
    newChartConfigSource?: NewChartConfigSource;
  };
  /** @deprecated Ya no se persiste; la plantilla vive en la pestaña anclada. */
  chartNewTabSeed?: ChartNewTabSeed | null;
  charts: ChartTabState[];
  activeChartId: string | null;
  /** Configuración de gráfico por par lista+instrumento (`listId::instrumentId`). */
  chartStateByListInstrument?: Record<string, ChartInstrumentSnapshot>;
  /** Lista e instrumento activos al abrir desde el panel de listas. */
  chartListContext?: ChartListContext | null;
  /** Plantillas de objetos gráficos (estilo XTB). */
  drawingTemplates?: ChartDrawingTemplate[];
  /** Plantilla activa por herramienta de dibujo */
  activeDrawingTemplateByTool?: Partial<Record<ChartDrawTool, string>>;
  /** Plantillas de indicadores por gráfico (independientes de estrategias). */
  indicatorTemplates?: IndicatorTemplate[];
  /** Variantes guardadas de indicadores (catálogo del workspace). */
  indicatorPresets?: IndicatorPreset[];
  /** Grupo aplicado por defecto a gráficos nuevos. */
  defaultIndicatorTemplateId?: string | null;
  /** Favoritos de barra por ID de lista (acceso directo estilo XTB). */
  indicatorFavoritesByListId?: Record<string, IndicatorFavoriteRef[]>;
  list: ListPanelConfig;
  /** Barra de herramientas global del workspace. */
  chartToolbarGlobal?: ChartToolbarGlobalConfig;
  /** @deprecated Usar chartToolbarGlobal.chartDefaults */
  chartDataStrip?: ChartDataStripConfig;
}

/** Preferencias del dock de trading (paneles listas/operaciones). */
export interface TradingDockLayoutPrefs {
  listsOpen: boolean;
  operationsOpen: boolean;
  listsWidthPct: number;
  operationsHeightPct: number;
}

export interface WorkspacePayload {
  document: WorkspaceDocument;
  dockLayout?: TradingDockLayoutPrefs;
}

export interface WorkspaceSummaryDto {
  id: string;
  name: string;
  isDefault: boolean;
  updatedAt: string;
}

export interface SyncSettingsDto {
  autoSyncEnabled: boolean;
  scanIntervalMinutes: number;
  minDelaySeconds: number;
  postMarketOnly: boolean;
  maxRetries: number;
  retryBackoffMinutes: number;
  scope: string;
  updatedAt: string;
}

export interface SyncQueueItemDto {
  id: string;
  instrumentId: string;
  symbol: string;
  status: string;
  priority: number;
  scheduledAt: string;
  attempts: number;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface PendingOrderDto {
  id: string;
  instrumentId: string;
  symbol: string;
  side: 'buy' | 'sell';
  orderType: string;
  quantity: number;
  limitPrice: number;
  expiryAt: string | null;
  createdAt: string;
}

export const LIST_COLUMN_LABELS: Record<ListColumnId, string> = {
  symbol: 'Símbolo',
  name: 'Nombre',
  lastClose: 'Último',
  changePct: '% día',
  isin: 'ISIN',
  syncStatus: 'Sincro',
  processStatus: 'Procesos',
  lastLabAt: 'Últ. Lab',
  lastCoreRAt: 'Últ. CORE-R',
  ioScore: 'IO',
  taScore: 'TA',
  faScore: 'FA',
  dictamenStars: '★ Dict.',
  recStance: 'Postura',
};

export const ALL_LIST_COLUMNS: ListColumnId[] = [
  'symbol',
  'name',
  'lastClose',
  'changePct',
  'isin',
  'syncStatus',
  'processStatus',
  'lastLabAt',
  'lastCoreRAt',
  'ioScore',
  'taScore',
  'faScore',
  'dictamenStars',
  'recStance',
];

/** Columnas de supervisión: visibles solo si el usuario las enciende. */
export const ESTUDIO_OPTIONAL_LIST_COLUMNS: ListColumnId[] = [
  'processStatus',
  'lastLabAt',
  'lastCoreRAt',
];

/** Columnas de recomendación (IO / dictamen). Off por defecto; activables en (…). */
export const RECOMMENDATION_OPTIONAL_LIST_COLUMNS: ListColumnId[] = [
  'ioScore',
  'taScore',
  'faScore',
  'dictamenStars',
  'recStance',
];

export const MIN_LIST_COLUMN_WIDTH = 40;
export const MAX_LIST_COLUMN_WIDTH = 280;

export const DEFAULT_LIST_COLUMN_WIDTHS: Record<ListColumnId, number> = {
  symbol: 56,
  name: 148,
  lastClose: 64,
  changePct: 56,
  isin: 96,
  syncStatus: 40,
  processStatus: 72,
  lastLabAt: 72,
  lastCoreRAt: 72,
  ioScore: 40,
  taScore: 40,
  faScore: 40,
  dictamenStars: 48,
  recStance: 64,
};

export function clampListColumnWidth(width: number): number {
  return Math.min(MAX_LIST_COLUMN_WIDTH, Math.max(MIN_LIST_COLUMN_WIDTH, Math.round(width)));
}

export function buildDefaultColumnLayout(
  columnIds: ListColumnId[] = ['symbol', 'lastClose', 'changePct'],
): ListColumnLayoutItem[] {
  const visibleSet = new Set(columnIds);
  const ordered: ListColumnLayoutItem[] = [];

  for (const id of columnIds) {
    ordered.push({
      id,
      width: DEFAULT_LIST_COLUMN_WIDTHS[id],
      visible: true,
    });
  }

  for (const id of ALL_LIST_COLUMNS) {
    if (!visibleSet.has(id)) {
      ordered.push({
        id,
        width: DEFAULT_LIST_COLUMN_WIDTHS[id],
        visible: false,
      });
    }
  }

  return ordered;
}

export function visibleListColumns(layout: ListColumnLayoutItem[]): ListColumnId[] {
  return layout.filter((column) => column.visible).map((column) => column.id);
}

export function normalizeColumnLayout(
  raw: ListColumnLayoutItem[] | undefined,
  legacyColumns?: ListColumnId[],
): ListColumnLayoutItem[] {
  const migrateColumnId = (id: string): ListColumnId | null => {
    const mapped = id === 'barCount' ? 'isin' : id;
    return ALL_LIST_COLUMNS.includes(mapped as ListColumnId) ? (mapped as ListColumnId) : null;
  };

  const fallback = buildDefaultColumnLayout(
    legacyColumns?.map((id) => (String(id) === 'barCount' ? 'isin' : id)),
  );
  if (!raw?.length) return fallback;

  const byId = new Map<ListColumnId, ListColumnLayoutItem>();
  for (const item of raw) {
    const columnId = migrateColumnId(item.id);
    if (!columnId) continue;
    byId.set(columnId, {
      id: columnId,
      width: clampListColumnWidth(item.width ?? DEFAULT_LIST_COLUMN_WIDTHS[columnId]),
      visible: Boolean(item.visible),
    });
  }

  const ordered: ListColumnLayoutItem[] = [];
  for (const item of raw) {
    const columnId = migrateColumnId(item.id);
    if (!columnId) continue;
    const normalized = byId.get(columnId);
    if (normalized) {
      ordered.push(normalized);
      byId.delete(columnId);
    }
  }

  for (const id of ALL_LIST_COLUMNS) {
    const remaining = byId.get(id);
    if (remaining) {
      ordered.push(remaining);
      byId.delete(id);
    }
  }

  // Columnas nuevas del producto (p. ej. IO/★) que aún no están en el layout guardado.
  for (const id of ALL_LIST_COLUMNS) {
    if (ordered.some((column) => column.id === id)) continue;
    ordered.push({
      id,
      width: DEFAULT_LIST_COLUMN_WIDTHS[id],
      visible: false,
    });
  }

  if (!ordered.some((column) => column.visible)) {
    return fallback;
  }

  return ordered;
}

export const DEFAULT_CHART_CONFIG: ChartInstanceConfig = {
  id: 'main',
  grid: {
    showVertical: true,
    showHorizontal: true,
    rightMarginPct: 5,
    topMarginPct: 5,
    priceScaleZoom: 1,
  },
  cursor: {
    mode: 'crosshair',
    showOhlcInTooltip: true,
    showTimeAxisLabel: true,
  },
  colors: {
    upColor: '#22c55e',
    downColor: '#ef4444',
    gridColor: '#243044',
    textColor: '#8b98a8',
    volumeUpColor: 'rgba(34, 197, 94, 0.5)',
    volumeDownColor: 'rgba(239, 68, 68, 0.5)',
    sma20Color: '#38bdf8',
    sma50Color: '#a78bfa',
    ema20Color: '#fbbf24',
    rsi14Color: '#f472b6',
  },
  display: {
    showVolume: true,
    showSma20: true,
    showSma50: true,
    showEma20: true,
    showRsi14: false,
    height: 480,
  },
};

const DEFAULT_VISIBLE_COLUMNS: ListColumnId[] = ['symbol', 'lastClose', 'changePct'];

export const DEFAULT_COLUMN_LAYOUT = buildDefaultColumnLayout(DEFAULT_VISIBLE_COLUMNS);

export const DEFAULT_LIST_CONFIG: ListPanelConfig = {
  id: 'ibex35',
  name: 'IBEX 35',
  source: 'api',
  columns: DEFAULT_VISIBLE_COLUMNS,
  columnLayout: DEFAULT_COLUMN_LAYOUT,
};

/** Ancho por defecto del panel listas (%) */
export const DEFAULT_LIST_PANEL_SIZE_PCT = 28;

/** Ancho por defecto del panel propiedades (%) */
export const DEFAULT_RIGHT_PANEL_SIZE_PCT = 24;

/** Mínimos recomendados (%) para paneles laterales */
export const MIN_LIST_PANEL_SIZE_PCT = 18;
export const MIN_RIGHT_PANEL_SIZE_PCT = 18;
export const MAX_LIST_PANEL_SIZE_PCT = 50;
export const MAX_RIGHT_PANEL_SIZE_PCT = 40;
