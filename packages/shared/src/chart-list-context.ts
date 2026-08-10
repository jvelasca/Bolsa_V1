import type { ChartDrawing } from './chart-drawings.js';
import type { ChartInstanceConfig, ChartTabState } from './chart-defaults.js';
import type { ChartTimeframe } from './chart-timeframes.js';
import type { ChartSeriesType, ChartSeriesTypeParams } from './chart-series-type.js';
import type { ChartToolbarChartOverrides } from './chart-toolbar.js';
import { normalizeChartToolbarChartOverrides } from './chart-toolbar.js';
import type { ChartIndicatorInstance } from './indicators-catalog.js';

/** Estado derivado del gráfico mientras la pestaña está abierta (no persiste tras cerrar). */
export interface ChartInstrumentSnapshot {
  timeframe: ChartTimeframe;
  seriesType: ChartSeriesType;
  seriesTypeParams?: ChartSeriesTypeParams;
  chart: ChartInstanceConfig;
  indicatorInstances: ChartIndicatorInstance[];
  drawings: ChartDrawing[];
  openDrawingEditorId?: string | null;
  activeIndicatorTemplateId?: string | null;
  toolbar?: ChartToolbarChartOverrides;
  pricePanelHeightPct?: number;
  drawingsLayerHidden?: boolean;
  drawingsLayerLocked?: boolean;
}

export interface ChartListContext {
  listId: string;
  instrumentId: string;
}

export function chartListStateKey(listId: string, instrumentId: string): string {
  return `${listId}::${instrumentId}`;
}

export function snapshotFromChartTab(
  tab: ChartTabState,
  openDrawingEditorId: string | null = null,
): ChartInstrumentSnapshot {
  return {
    timeframe: tab.timeframe,
    seriesType: tab.seriesType,
    seriesTypeParams: tab.seriesTypeParams ? { ...tab.seriesTypeParams } : undefined,
    chart: tab.chart,
    indicatorInstances: tab.indicatorInstances.map((instance) => ({
      ...instance,
      parameters: { ...instance.parameters },
    })),
    drawings: tab.drawings.map((drawing) => ({ ...drawing })),
    openDrawingEditorId,
    activeIndicatorTemplateId: tab.activeIndicatorTemplateId ?? null,
    toolbar: tab.toolbar ? normalizeChartToolbarChartOverrides(tab.toolbar) : undefined,
    pricePanelHeightPct: tab.pricePanelHeightPct,
    drawingsLayerHidden: tab.drawingsLayerHidden,
    drawingsLayerLocked: tab.drawingsLayerLocked,
  };
}
