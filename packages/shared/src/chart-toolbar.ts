import type { ChartDrawTool } from './chart-drawings.js';
import type { DrawToolStyleMemory } from './chart-draw-style-memory.js';
import {
  DEFAULT_DRAW_TOOL_FAVORITES,
  IMPLEMENTED_DRAW_TOOLS,
  normalizeDrawToolFavorites,
  toggleDrawToolFavoriteList,
  type DrawingToolGroupId,
} from './chart-drawing-taxonomy.js';
import {
  DEFAULT_CHART_TIMEFRAME,
  DEFAULT_CHART_TIMEFRAME_FAVORITES,
  isChartTimeframe,
  type ChartTimeframe,
} from './chart-timeframes.js';
import {
  type ChartDataStripConfig,
  DEFAULT_CHART_DATA_STRIP_CONFIG,
  normalizeChartDataStripConfig,
} from './chart-data-strip.js';
import {
  DEFAULT_CHART_CURSOR_FIELD_FAVORITES,
  DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES,
  normalizeChartCursorFieldFavorites,
  normalizeChartInstrumentFieldFavorites,
  type ChartCursorBarField,
  type ChartInstrumentBarField,
} from './chart-data-bar-zones.js';
import {
  DEFAULT_CHART_SERIES_TYPE,
  DEFAULT_CHART_SERIES_TYPE_FAVORITES,
  normalizeChartSeriesType,
  normalizeChartSeriesTypeFavorites,
  type ChartSeriesType,
} from './chart-series-type.js';
import {
  DEFAULT_INDICATOR_TEMPLATE_FAVORITES,
  normalizeIndicatorTemplateFavorites,
} from './indicator-templates.js';
import {
  normalizeInspectorBarShortcutFavorites,
  type ChartInspectorBarShortcutId,
} from './chart-inspector-bar-shortcuts.js';

export interface ChartToolbarGlobalVisibility {
  indicators: boolean;
  indicatorTemplates: boolean;
  chartInspector: boolean;
  /** Compra / venta rápida sobre el gráfico activo. */
  tradeButtons: boolean;
  /** Estado de sincronización de datos (BD). */
  dataStatus: boolean;
  /**
   * Miniresumen Score_FUND + pierna TA (Composite) a la derecha de la barra general.
   * Enlaza a Backtesting → Análisis fundamental / técnico.
   */
  analysisScores: boolean;
  settingsButton: boolean;
}

export interface ChartToolbarChartVisibility {
  /** Zona Escala: resolución temporal y favoritos. */
  timeframe: boolean;
  /** Botones de zoom de velas en el gráfico. */
  timeframeZoom: boolean;
  /** Zona Estilo: tipo de barra / traza (velas, líneas…). */
  seriesZone: boolean;
  /** Zona Plantillas: conjuntos de indicadores y favoritos (icono LayoutTemplate). */
  indicatorTemplateZone: boolean;
  /** Zona Valor: metadatos del instrumento (símbolo, nombre, mercado…). */
  instrumentZone: boolean;
  /** Enlace externo al gráfico del instrumento activo en TradingView. */
  tradingView: boolean;
  /** Zona Cursor: OHLC y volumen de la vela bajo el puntero. */
  cursorZone: boolean;
  /**
   * Botón (i) tras Cursor: abre la misma ficha del valor que en la lista
   * (`InstrumentInfoDialog` — hechos / perfil / inventario BD).
   */
  instrumentInfo: boolean;
  /**
   * Botón IA tras (i): propose del valor → cola Supervisado F3 → Ayuda Plataforma IA.
   */
  instrumentAi: boolean;
  /** @deprecated Sustituido por `inspectorBarShortcutFavorites` (estrella en inspector). */
  overlayIndicators: boolean;
  settingsButton: boolean;
}

export interface ChartToolbarChartLayout {
  /**
   * Si true, las zonas que no caben pasan a la siguiente fila (sin scroll horizontal).
   * Si false, una sola fila con desplazamiento horizontal.
   */
  wrapRows: boolean;
}

export const DEFAULT_CHART_TOOLBAR_CHART_LAYOUT: ChartToolbarChartLayout = {
  wrapRows: true,
};

export interface ChartToolbarAppearance {
  globalBarBackground: string;
  chartBarBackground: string;
}

export interface ChartToolbarGlobalConfig {
  visibility: ChartToolbarGlobalVisibility;
  appearance: ChartToolbarAppearance;
  /**
   * @deprecated Los campos visibles se gestionan con favoritos (estrella) en Valor/Cursor.
   * Se conserva solo para migración de workspaces antiguos.
   */
  chartDefaults: ChartDataStripConfig;
  /** Timeframe inicial al abrir un gráfico nuevo. */
  defaultTimeframe: ChartTimeframe;
  /** Tipo de serie inicial al abrir un gráfico nuevo. */
  defaultSeriesType: ChartSeriesType;
  /** Visibilidad por defecto de la barra por gráfico. */
  chartVisibilityDefaults: ChartToolbarChartVisibility;
  /** Accesos directos de resolución temporal en la barra (favoritos). */
  timeframeFavorites: ChartTimeframe[];
  /** Accesos directos de tipo de serie en la barra (favoritos). */
  seriesTypeFavorites: ChartSeriesType[];
  /** Accesos directos de grupos de indicadores en la barra (favoritos). */
  indicatorTemplateFavorites: string[];
  /** Accesos directos en la zona de instrumento. */
  instrumentFieldFavorites: ChartInstrumentBarField[];
  /** Accesos directos en la zona de cursor / vela. */
  cursorFieldFavorites: ChartCursorBarField[];
  /** Herramientas con estrella por grupo (favoritos). */
  drawToolFavorites: ChartDrawTool[];
  /** Atajos al inspector fijados en la barra de datos (estrella en pestañas Config). */
  inspectorBarShortcutFavorites?: ChartInspectorBarShortcutId[];
  /** Herramienta de dibujo activa al cerrar sesión. */
  activeDrawTool?: ChartDrawTool;
  /** Última herramienta por grupo (p. ej. cursor → cruz). */
  lastDrawToolByGroup?: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
  /** Último estilo usado manualmente por herramienta (persiste entre sesiones). */
  lastDrawStyleByTool?: Partial<Record<ChartDrawTool, DrawToolStyleMemory>>;
  /** Comportamiento de la barra por gráfico en paneles estrechos. */
  chartLayoutDefaults: ChartToolbarChartLayout;
}

export interface ChartToolbarChartOverrides {
  /** Si true, ignora overrides y usa solo chartVisibilityDefaults / chartLayoutDefaults globales. */
  useGlobalDefaults?: boolean;
  visibility?: Partial<ChartToolbarChartVisibility>;
  layout?: Partial<ChartToolbarChartLayout>;
  appearance?: Partial<Pick<ChartToolbarAppearance, 'chartBarBackground'>>;
}

export interface ResolvedChartToolbarChart {
  visibility: ChartToolbarChartVisibility;
  layout: ChartToolbarChartLayout;
  chartBarBackground: string;
  customized: boolean;
}

export const CHART_TOOLBAR_GLOBAL_VISIBILITY_LABELS: Record<
  keyof ChartToolbarGlobalVisibility,
  string
> = {
  indicators: 'Catálogo de indicadores',
  indicatorTemplates: 'Plantillas de indicadores',
  chartInspector: 'Mostrar / ocultar inspector',
  tradeButtons: 'Compra / venta rápida',
  dataStatus: 'Estado de sincronización (BD)',
  analysisScores: 'Scores análisis técnico / fundamental',
  settingsButton: 'Botón de configuración',
};

export const CHART_TOOLBAR_CHART_VISIBILITY_LABELS: Record<
  keyof ChartToolbarChartVisibility,
  string
> = {
  timeframe: 'Escala temporal (resolución y favoritos)',
  timeframeZoom: 'Zoom de velas',
  seriesZone: 'Estilo (tipo de barra / traza)',
  indicatorTemplateZone: 'Plantillas de indicadores (icono en barra)',
  instrumentZone: 'Zona Valor (metadatos del instrumento)',
  tradingView: 'Abrir en TradingView',
  cursorZone: 'Zona Cursor (OHLC de la vela)',
  instrumentInfo: 'Información del valor (i)',
  instrumentAi: 'Estudio IA del valor (Supervisado F3)',
  overlayIndicators: 'Atajos al inspector (obsoleto — usar estrella en inspector)',
  settingsButton: 'Botón de configuración',
};

export const DEFAULT_CHART_TOOLBAR_CHART_VISIBILITY: ChartToolbarChartVisibility = {
  timeframe: true,
  timeframeZoom: true,
  seriesZone: true,
  indicatorTemplateZone: true,
  instrumentZone: true,
  tradingView: true,
  cursorZone: true,
  instrumentInfo: true,
  instrumentAi: true,
  overlayIndicators: false,
  settingsButton: true,
};

export const DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG: ChartToolbarGlobalConfig = {
  visibility: {
    indicators: true,
    indicatorTemplates: true,
    chartInspector: true,
    tradeButtons: true,
    dataStatus: true,
    analysisScores: true,
    settingsButton: true,
  },
  appearance: {
    globalBarBackground: 'transparent',
    chartBarBackground: 'transparent',
  },
  chartDefaults: DEFAULT_CHART_DATA_STRIP_CONFIG,
  defaultTimeframe: DEFAULT_CHART_TIMEFRAME,
  defaultSeriesType: DEFAULT_CHART_SERIES_TYPE,
  chartVisibilityDefaults: { ...DEFAULT_CHART_TOOLBAR_CHART_VISIBILITY },
  timeframeFavorites: [...DEFAULT_CHART_TIMEFRAME_FAVORITES],
  seriesTypeFavorites: [...DEFAULT_CHART_SERIES_TYPE_FAVORITES],
  indicatorTemplateFavorites: [...DEFAULT_INDICATOR_TEMPLATE_FAVORITES],
  instrumentFieldFavorites: [...DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES],
  cursorFieldFavorites: [...DEFAULT_CHART_CURSOR_FIELD_FAVORITES],
  drawToolFavorites: [...DEFAULT_DRAW_TOOL_FAVORITES],
  inspectorBarShortcutFavorites: [],
  chartLayoutDefaults: { ...DEFAULT_CHART_TOOLBAR_CHART_LAYOUT },
};

function normalizeLastDrawToolByGroup(
  raw?: Partial<Record<DrawingToolGroupId, ChartDrawTool>> | null,
): Partial<Record<DrawingToolGroupId, ChartDrawTool>> | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const next: Partial<Record<DrawingToolGroupId, ChartDrawTool>> = {};
  for (const [group, tool] of Object.entries(raw)) {
    if (IMPLEMENTED_DRAW_TOOLS.includes(tool as ChartDrawTool)) {
      next[group as DrawingToolGroupId] = tool as ChartDrawTool;
    }
  }
  return Object.keys(next).length > 0 ? next : undefined;
}

function normalizeChartVisibilityDefaults(
  raw?: Partial<ChartToolbarChartVisibility> & {
    /** @deprecated Migración desde workspaces con `dataStrip` único */
    dataStrip?: boolean;
    dataStatus?: boolean;
    tradeButtons?: boolean;
    /** @deprecated Renombrado a indicatorTemplateZone (jul 2026) */
    indicatorGroupZone?: boolean;
  } | null,
): ChartToolbarChartVisibility {
  const base = DEFAULT_CHART_TOOLBAR_CHART_VISIBILITY;
  const legacyStrip = raw?.dataStrip;
  return {
    timeframe: raw?.timeframe ?? base.timeframe,
    timeframeZoom: raw?.timeframeZoom ?? base.timeframeZoom,
    seriesZone: raw?.seriesZone ?? base.seriesZone,
    indicatorTemplateZone:
      raw?.indicatorTemplateZone ?? raw?.indicatorGroupZone ?? base.indicatorTemplateZone,
    instrumentZone: raw?.instrumentZone ?? legacyStrip ?? base.instrumentZone,
    tradingView: raw?.tradingView ?? base.tradingView,
    cursorZone: raw?.cursorZone ?? legacyStrip ?? base.cursorZone,
    instrumentInfo: raw?.instrumentInfo ?? base.instrumentInfo,
    instrumentAi: raw?.instrumentAi ?? base.instrumentAi,
    overlayIndicators: raw?.overlayIndicators ?? base.overlayIndicators,
    settingsButton: true,
  };
}

export function normalizeChartTimeframeFavorites(
  raw?: ChartTimeframe[] | null,
): ChartTimeframe[] {
  if (raw == null) return [...DEFAULT_CHART_TIMEFRAME_FAVORITES];
  return raw.filter((item) => isChartTimeframe(item));
}

export function toggleChartTimeframeFavoriteList(
  favorites: ChartTimeframe[],
  timeframe: ChartTimeframe,
): ChartTimeframe[] {
  if (favorites.includes(timeframe)) {
    return favorites.filter((item) => item !== timeframe);
  }
  return [...favorites, timeframe];
}

/** @deprecated Solo migración JSON; la UI usa favoritos por zona. */
function readLegacyChartDefaults(
  raw?: Partial<ChartToolbarGlobalConfig> | null,
  legacyDataStrip?: Partial<ChartDataStripConfig> | null,
): ChartDataStripConfig {
  const base = DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG.chartDefaults;
  const chartDefaultsSource = raw?.chartDefaults ?? legacyDataStrip ?? base;
  return normalizeChartDataStripConfig(chartDefaultsSource);
}

export function normalizeChartToolbarGlobalConfig(
  raw?: Partial<ChartToolbarGlobalConfig> | null,
  legacyDataStrip?: Partial<ChartDataStripConfig> | null,
): ChartToolbarGlobalConfig {
  const base = DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG;
  const legacyChartVis = raw?.chartVisibilityDefaults as
    | (Partial<ChartToolbarChartVisibility> & {
        dataStrip?: boolean;
        dataStatus?: boolean;
        tradeButtons?: boolean;
      })
    | undefined;
  const legacyGlobalVis = raw?.visibility as
    | (Partial<ChartToolbarGlobalVisibility> & { tradingView?: boolean })
    | undefined;
  const { tradingView: _legacyTradingView, ...restGlobalVisibility } = legacyGlobalVis ?? {};
  return {
    visibility: {
      ...base.visibility,
      ...restGlobalVisibility,
      dataStatus:
        raw?.visibility?.dataStatus ?? legacyChartVis?.dataStatus ?? base.visibility.dataStatus,
      tradeButtons:
        raw?.visibility?.tradeButtons ?? legacyChartVis?.tradeButtons ?? base.visibility.tradeButtons,
      settingsButton: true,
    },
    appearance: { ...base.appearance, ...raw?.appearance },
    chartDefaults: readLegacyChartDefaults(raw, legacyDataStrip),
    defaultTimeframe:
      raw?.defaultTimeframe && isChartTimeframe(raw.defaultTimeframe)
        ? raw.defaultTimeframe
        : base.defaultTimeframe,
    defaultSeriesType: normalizeChartSeriesType(raw?.defaultSeriesType, base.defaultSeriesType),
    chartVisibilityDefaults: normalizeChartVisibilityDefaults({
      ...base.chartVisibilityDefaults,
      ...raw?.chartVisibilityDefaults,
      tradingView:
        raw?.chartVisibilityDefaults?.tradingView ??
        _legacyTradingView ??
        base.chartVisibilityDefaults.tradingView,
    }),
    timeframeFavorites: normalizeChartTimeframeFavorites(raw?.timeframeFavorites),
    seriesTypeFavorites: normalizeChartSeriesTypeFavorites(raw?.seriesTypeFavorites),
    indicatorTemplateFavorites: normalizeIndicatorTemplateFavorites(
      raw?.indicatorTemplateFavorites,
    ),
    instrumentFieldFavorites: normalizeChartInstrumentFieldFavorites(
      raw?.instrumentFieldFavorites,
    ),
    cursorFieldFavorites: normalizeChartCursorFieldFavorites(raw?.cursorFieldFavorites),
    drawToolFavorites: normalizeDrawToolFavorites(raw?.drawToolFavorites, IMPLEMENTED_DRAW_TOOLS),
    inspectorBarShortcutFavorites: normalizeInspectorBarShortcutFavorites(
      raw?.inspectorBarShortcutFavorites,
    ),
    activeDrawTool:
      raw?.activeDrawTool && IMPLEMENTED_DRAW_TOOLS.includes(raw.activeDrawTool)
        ? raw.activeDrawTool
        : undefined,
    lastDrawToolByGroup: normalizeLastDrawToolByGroup(raw?.lastDrawToolByGroup),
    lastDrawStyleByTool: raw?.lastDrawStyleByTool ?? {},
    chartLayoutDefaults: {
      ...DEFAULT_CHART_TOOLBAR_CHART_LAYOUT,
      ...raw?.chartLayoutDefaults,
    },
  };
}

function migrateVisibilityOverrides(
  raw: Partial<ChartToolbarChartVisibility> & { dataStrip?: boolean },
): Partial<ChartToolbarChartVisibility> {
  const { dataStrip, ...rest } = raw;
  if (dataStrip === undefined) return { ...rest };
  return {
    ...rest,
    instrumentZone: rest.instrumentZone ?? dataStrip,
    cursorZone: rest.cursorZone ?? dataStrip,
  };
}

export function normalizeChartToolbarChartOverrides(
  raw?: ChartToolbarChartOverrides | null,
): ChartToolbarChartOverrides | undefined {
  if (!raw) return undefined;
  return {
    useGlobalDefaults: raw.useGlobalDefaults,
    visibility: raw.visibility ? migrateVisibilityOverrides(raw.visibility) : undefined,
    layout: raw.layout ? { ...raw.layout } : undefined,
    appearance: raw.appearance ? { ...raw.appearance } : undefined,
  };
}

export function isChartToolbarCustomized(
  overrides?: ChartToolbarChartOverrides | null,
): boolean {
  if (!overrides) return false;
  if (overrides.useGlobalDefaults) return false;
  return Boolean(
    overrides.visibility ||
      overrides.layout ||
      overrides.appearance?.chartBarBackground,
  );
}

/** Fusiona configuración global de barras; la fuente primaria gana por campo. */
export function mergeChartToolbarGlobalConfig(
  primary?: ChartToolbarGlobalConfig | null,
  secondary?: ChartToolbarGlobalConfig | null,
): ChartToolbarGlobalConfig {
  const base = normalizeChartToolbarGlobalConfig(secondary);
  const patch: Partial<ChartToolbarGlobalConfig> = primary ?? {};
  return normalizeChartToolbarGlobalConfig({
    ...base,
    ...patch,
    visibility: { ...base.visibility, ...patch.visibility },
    appearance: { ...base.appearance, ...patch.appearance },
    chartVisibilityDefaults: {
      ...base.chartVisibilityDefaults,
      ...patch.chartVisibilityDefaults,
    },
    chartLayoutDefaults: { ...base.chartLayoutDefaults, ...patch.chartLayoutDefaults },
    timeframeFavorites: patch.timeframeFavorites ?? base.timeframeFavorites,
    seriesTypeFavorites: patch.seriesTypeFavorites ?? base.seriesTypeFavorites,
    indicatorTemplateFavorites:
      patch.indicatorTemplateFavorites ?? base.indicatorTemplateFavorites,
    instrumentFieldFavorites: patch.instrumentFieldFavorites ?? base.instrumentFieldFavorites,
    cursorFieldFavorites: patch.cursorFieldFavorites ?? base.cursorFieldFavorites,
    drawToolFavorites: patch.drawToolFavorites ?? base.drawToolFavorites,
    activeDrawTool: patch.activeDrawTool ?? base.activeDrawTool,
    lastDrawToolByGroup: { ...base.lastDrawToolByGroup, ...patch.lastDrawToolByGroup },
    lastDrawStyleByTool: { ...base.lastDrawStyleByTool, ...patch.lastDrawStyleByTool },
  });
}

export { toggleDrawToolFavoriteList };

/** Conserva overrides por pestaña si alguna fuente los personalizó. */
export function mergeChartToolbarChartOverrides(
  primary?: ChartToolbarChartOverrides | null,
  secondary?: ChartToolbarChartOverrides | null,
): ChartToolbarChartOverrides | undefined {
  const primaryNorm = normalizeChartToolbarChartOverrides(primary);
  const secondaryNorm = normalizeChartToolbarChartOverrides(secondary);
  if (isChartToolbarCustomized(primaryNorm)) return primaryNorm;
  if (isChartToolbarCustomized(secondaryNorm)) return secondaryNorm;
  return undefined;
}

export function resolveChartToolbarForTab(
  global: ChartToolbarGlobalConfig,
  overrides?: ChartToolbarChartOverrides | null,
): ResolvedChartToolbarChart {
  const normalized = normalizeChartToolbarChartOverrides(overrides);
  const useGlobal =
    !normalized ||
    normalized.useGlobalDefaults === true ||
    !isChartToolbarCustomized(normalized);

  const visibility = normalizeChartVisibilityDefaults(
    useGlobal
      ? global.chartVisibilityDefaults
      : {
          ...global.chartVisibilityDefaults,
          ...normalized?.visibility,
        },
  );

  const chartBarBackground = useGlobal
    ? global.appearance.chartBarBackground
    : (normalized?.appearance?.chartBarBackground ?? global.appearance.chartBarBackground);

  const layout = useGlobal
    ? { ...global.chartLayoutDefaults }
    : {
        ...global.chartLayoutDefaults,
        ...normalized?.layout,
      };

  return {
    visibility,
    layout,
    chartBarBackground,
    customized: isChartToolbarCustomized(normalized),
  };
}
