import type {
  ChartTabState,
  ChartInstanceConfig,
  WorkspaceDocument,
} from "./chart-defaults.js";
import type { ChartToolbarChartOverrides } from "./chart-toolbar.js";
import type {
  ChartSeriesType,
  ChartSeriesTypeParams,
} from "./chart-series-type.js";
import {
  normalizeChartSeriesType,
  normalizeChartSeriesTypeParams,
} from "./chart-series-type.js";
import type { ChartTimeframe } from "./chart-timeframes.js";
import type { ChartIndicatorInstance } from "./indicators-catalog.js";
import { newIndicatorInstanceId } from "./indicators-catalog.js";
import { normalizeChartToolbarChartOverrides } from "./chart-toolbar.js";

/** Id de pestaña cuya configuración copian los gráficos nuevos; `null` = defaults del workspace. */
export function normalizeNewChartTemplateChartId(
  raw: string | null | undefined,
  charts: { id: string }[],
): string | null {
  if (!raw) return null;
  return charts.some((tab) => tab.id === raw) ? raw : null;
}

export const NEW_CHART_TEMPLATE_PIN_TOOLTIP =
  "Usar la configuración de este gráfico (indicadores, barra de datos, estilo) como plantilla para los valores que abras a partir de ahora. Si está desactivado, los gráficos nuevos usarán la configuración por defecto del workspace.";

export type NewChartConfigSource = "defaults" | "inheritLast";

export function resolveNewChartTemplateTab(
  workspace: Pick<WorkspaceDocument, "charts" | "preferences">,
): ChartTabState | null {
  const id = workspace.preferences.newChartTemplateChartId;
  if (!id) return null;
  return workspace.charts.find((tab) => tab.id === id) ?? null;
}

/**
 * Plantilla de configuración copiable entre pestañas (sin dibujos ni ids de pestaña).
 */
export interface ChartNewTabSeed {
  timeframe: ChartTimeframe;
  seriesType: ChartSeriesType;
  seriesTypeParams?: ChartSeriesTypeParams;
  chart: ChartInstanceConfig;
  indicatorInstances: ChartIndicatorInstance[];
  activeIndicatorTemplateId?: string | null;
  toolbar?: ChartToolbarChartOverrides;
  pricePanelHeightPct?: number;
  drawingsLayerHidden?: boolean;
  drawingsLayerLocked?: boolean;
}

export function extractChartNewTabSeed(tab: ChartTabState): ChartNewTabSeed {
  return {
    timeframe: tab.timeframe,
    seriesType: tab.seriesType,
    seriesTypeParams: tab.seriesTypeParams
      ? { ...tab.seriesTypeParams }
      : undefined,
    chart: {
      ...tab.chart,
      grid: { ...tab.chart.grid },
      cursor: { ...tab.chart.cursor },
      colors: { ...tab.chart.colors },
      display: { ...tab.chart.display },
    },
    indicatorInstances: tab.indicatorInstances
      .filter((instance) => instance.origin !== "finalist-top1")
      .map((instance) => ({
        ...instance,
        parameters: { ...instance.parameters },
      })),
    activeIndicatorTemplateId: tab.activeIndicatorTemplateId ?? null,
    toolbar: tab.toolbar
      ? normalizeChartToolbarChartOverrides(tab.toolbar)
      : undefined,
    pricePanelHeightPct: tab.pricePanelHeightPct,
    drawingsLayerHidden: tab.drawingsLayerHidden,
    drawingsLayerLocked: tab.drawingsLayerLocked,
  };
}

export function cloneIndicatorInstancesForNewTab(
  instances: ChartIndicatorInstance[],
): ChartIndicatorInstance[] {
  return instances.map((instance) => ({
    ...instance,
    instanceId: newIndicatorInstanceId(
      instance.definitionId,
      instance.parameters,
    ),
    parameters: { ...instance.parameters },
  }));
}

export function applyChartNewTabSeed(
  baseTab: ChartTabState,
  seed: ChartNewTabSeed,
  cloneChart: (config?: ChartInstanceConfig) => ChartInstanceConfig,
): ChartTabState {
  const indicatorInstances = cloneIndicatorInstancesForNewTab(
    seed.indicatorInstances,
  );
  const chart = cloneChart(seed.chart);
  return {
    ...baseTab,
    timeframe: seed.timeframe,
    seriesType: normalizeChartSeriesType(seed.seriesType, baseTab.seriesType),
    seriesTypeParams: normalizeChartSeriesTypeParams(
      seed.seriesTypeParams ?? baseTab.seriesTypeParams,
    ),
    chart,
    indicatorInstances,
    activeIndicatorTemplateId: seed.activeIndicatorTemplateId ?? null,
    toolbar: seed.toolbar ? { ...seed.toolbar } : undefined,
    pricePanelHeightPct: seed.pricePanelHeightPct,
    drawingsLayerHidden: seed.drawingsLayerHidden,
    drawingsLayerLocked: seed.drawingsLayerLocked,
    drawings: [],
  };
}

export function normalizeChartNewTabSeed(
  raw?: ChartNewTabSeed | null,
): ChartNewTabSeed | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  return {
    timeframe: raw.timeframe,
    seriesType: normalizeChartSeriesType(raw.seriesType),
    seriesTypeParams: raw.seriesTypeParams
      ? normalizeChartSeriesTypeParams(raw.seriesTypeParams)
      : undefined,
    chart: raw.chart,
    indicatorInstances: Array.isArray(raw.indicatorInstances)
      ? raw.indicatorInstances.map((instance) => ({
          ...instance,
          parameters: { ...instance.parameters },
        }))
      : [],
    activeIndicatorTemplateId: raw.activeIndicatorTemplateId ?? null,
    toolbar: raw.toolbar
      ? normalizeChartToolbarChartOverrides(raw.toolbar)
      : undefined,
    pricePanelHeightPct: raw.pricePanelHeightPct,
    drawingsLayerHidden: raw.drawingsLayerHidden,
    drawingsLayerLocked: raw.drawingsLayerLocked,
  };
}
