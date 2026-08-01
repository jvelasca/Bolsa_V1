import type {
  IChartApi,
  ISeriesApi,
  LogicalRange,
  MouseEventParams,
  SeriesType,
  Time,
} from 'lightweight-charts';
import { MismatchDirection } from 'lightweight-charts';
import { PRICE_SCALE_HIT_WIDTH_PX } from '@/features/charts/chart-scale-utils';
import { CHART_ZOOM_EVENT, type ChartZoomAction } from '@/features/charts/chart-utils';

export type ChartSyncPaneKind = 'main' | 'sub';

export interface ChartSyncPane {
  id: string;
  chart: IChartApi;
  kind: ChartSyncPaneKind;
  /** Serie para `setCrosshairPosition` / lookup de precio en sync. */
  series: ISeriesApi<SeriesType>;
}

function logicalRangesEqual(a: LogicalRange, b: LogicalRange): boolean {
  return Math.abs(a.from - b.from) < 0.001 && Math.abs(a.to - b.to) < 0.001;
}

export { logicalRangesEqual };

/** Factor de zoom horizontal por tick de rueda / botón (+/−). */
export const CHART_HORIZONTAL_ZOOM_FACTOR = 0.7;

/**
 * Zoom horizontal manteniendo `anchorLogical` fijo en pantalla.
 * Sin ancla → centro del rango visible (comportamiento clásico).
 */
export function zoomLogicalRange(
  range: LogicalRange,
  action: Exclude<ChartZoomAction, 'reset'>,
  anchorLogical?: number | null,
): LogicalRange {
  const span = range.to - range.from;
  if (span <= 0) return range;
  const factor = action === 'in' ? CHART_HORIZONTAL_ZOOM_FACTOR : 1 / CHART_HORIZONTAL_ZOOM_FACTOR;
  const newSpan = span * factor;
  const anchor =
    anchorLogical != null && Number.isFinite(anchorLogical)
      ? anchorLogical
      : (range.from + range.to) / 2;
  const ratio = Math.min(1, Math.max(0, (anchor - range.from) / span));
  return {
    from: (anchor - ratio * newSpan) as LogicalRange['from'],
    to: (anchor + (1 - ratio) * newSpan) as LogicalRange['to'],
  };
}

function seriesPriceAtTime(
  chart: IChartApi,
  series: ISeriesApi<SeriesType>,
  time: Time,
): number | null {
  const index = chart.timeScale().timeToIndex(time, true);
  if (index == null) return null;
  const point = series.dataByIndex(index, MismatchDirection.NearestLeft);
  if (!point) return null;
  if ('close' in point && typeof point.close === 'number') return point.close;
  if ('value' in point && typeof point.value === 'number') return point.value;
  return null;
}

class ChartSyncHub {
  private panes = new Map<string, ChartSyncPane>();
  private cleanups = new Map<string, () => void>();
  private applying = false;
  private applyingCrosshair = false;
  private lastLogicalRange: LogicalRange | null = null;

  register(pane: ChartSyncPane): () => void {
    this.cleanups.get(pane.id)?.();

    const onLogicalChange = (range: LogicalRange | null) => {
      if (this.applying || !range) return;
      if (this.lastLogicalRange && logicalRangesEqual(this.lastLogicalRange, range)) return;
      this.applyLogicalRange(range, pane.id);
    };

    const onCrosshairMove = (param: MouseEventParams) => {
      if (this.applyingCrosshair) return;
      if (param.time === undefined) {
        this.clearCrosshair(pane.id);
        return;
      }
      this.applyCrosshair(param.time, pane.id);
    };

    pane.chart.timeScale().subscribeVisibleLogicalRangeChange(onLogicalChange);
    pane.chart.subscribeCrosshairMove(onCrosshairMove);

    const cleanup = () => {
      pane.chart.timeScale().unsubscribeVisibleLogicalRangeChange(onLogicalChange);
      pane.chart.unsubscribeCrosshairMove(onCrosshairMove);
      this.panes.delete(pane.id);
      this.cleanups.delete(pane.id);
    };

    this.panes.set(pane.id, pane);
    this.cleanups.set(pane.id, cleanup);

    const main = this.panes.get('main');
    const range =
      this.lastLogicalRange ??
      main?.chart.timeScale().getVisibleLogicalRange() ??
      pane.chart.timeScale().getVisibleLogicalRange();
    if (range) {
      requestAnimationFrame(() => {
        this.applyLogicalRange(range, main?.id ?? pane.id);
      });
    }

    return cleanup;
  }

  applyLogicalRange(range: LogicalRange, sourceId: string) {
    this.lastLogicalRange = range;
    this.applying = true;
    try {
      for (const [id, entry] of this.panes) {
        if (id === sourceId) continue;
        const current = entry.chart.timeScale().getVisibleLogicalRange();
        if (current && logicalRangesEqual(current, range)) continue;
        entry.chart.timeScale().setVisibleLogicalRange(range);
      }
    } finally {
      this.applying = false;
    }
  }

  applyCrosshair(time: Time, sourceId: string) {
    this.applyingCrosshair = true;
    try {
      for (const [id, entry] of this.panes) {
        if (id === sourceId) continue;
        const price = seriesPriceAtTime(entry.chart, entry.series, time);
        if (price == null) {
          entry.chart.clearCrosshairPosition();
          continue;
        }
        entry.chart.setCrosshairPosition(price, time, entry.series);
      }
    } finally {
      this.applyingCrosshair = false;
    }
  }

  clearCrosshair(sourceId: string) {
    this.applyingCrosshair = true;
    try {
      for (const [id, entry] of this.panes) {
        if (id === sourceId) continue;
        entry.chart.clearCrosshairPosition();
      }
    } finally {
      this.applyingCrosshair = false;
    }
  }

  broadcastFrom(sourceId: string) {
    const pane = this.panes.get(sourceId);
    if (!pane) return;
    const range = pane.chart.timeScale().getVisibleLogicalRange();
    if (!range) return;
    this.applyLogicalRange(range, sourceId);
  }

  applyHorizontalPanPixels(deltaPx: number, plotWidthPx: number, sourceId?: string) {
    const leader =
      (sourceId ? this.panes.get(sourceId) : undefined) ??
      this.panes.get('main') ??
      this.panes.values().next().value;
    if (!leader || plotWidthPx <= 0 || deltaPx === 0) return;

    const timeScale = leader.chart.timeScale();
    const range = timeScale.getVisibleLogicalRange();
    if (!range) return;

    const span = range.to - range.from;
    const shift = (deltaPx / plotWidthPx) * span;
    const next: LogicalRange = {
      from: (range.from - shift) as LogicalRange['from'],
      to: (range.to - shift) as LogicalRange['to'],
    };

    timeScale.setVisibleLogicalRange(next);
    this.applyLogicalRange(next, leader.id);
  }

  applyZoomAction(
    action: ChartZoomAction,
    sourceId?: string,
    anchorLogical?: number | null,
  ) {
    const leader =
      (sourceId ? this.panes.get(sourceId) : undefined) ??
      this.panes.get('main') ??
      this.panes.values().next().value;
    if (!leader) return;

    const timeScale = leader.chart.timeScale();
    if (action === 'reset') {
      timeScale.fitContent();
      const range = timeScale.getVisibleLogicalRange();
      if (range) this.applyLogicalRange(range, leader.id);
      return;
    }

    const range = timeScale.getVisibleLogicalRange();
    if (!range) return;

    const next = zoomLogicalRange(range, action, anchorLogical);
    timeScale.setVisibleLogicalRange(next);
    this.applyLogicalRange(next, leader.id);
  }
}

const hubs = new Map<string, ChartSyncHub>();

export function getChartSyncHub(groupId: string): ChartSyncHub {
  let hub = hubs.get(groupId);
  if (!hub) {
    hub = new ChartSyncHub();
    hubs.set(groupId, hub);
  }
  return hub;
}

export function disposeChartSyncHub(groupId: string) {
  hubs.delete(groupId);
}

let zoomBridgeInstalled = false;

export function ensureChartZoomBridge() {
  if (zoomBridgeInstalled) return;
  zoomBridgeInstalled = true;

  window.addEventListener(CHART_ZOOM_EVENT, (event) => {
    const detail = (event as CustomEvent<{ action: ChartZoomAction; chartSyncId?: string }>).detail;
    if (!detail?.action) return;
    if (detail.chartSyncId) {
      getChartSyncHub(detail.chartSyncId).applyZoomAction(detail.action);
      return;
    }
    for (const hub of hubs.values()) {
      hub.applyZoomAction(detail.action);
    }
  });
}

/** Zoom horizontal con rueda (cualquier panel del grupo; sincroniza todos). */
export function attachChartHorizontalWheel(
  container: HTMLElement,
  chartSyncId: string,
  options?: {
    isDisabled?: () => boolean;
    sourcePaneId?: string;
    /** Índice lógico bajo el cursor (zoom anclado). */
    getAnchorLogical?: (clientX: number) => number | null;
  },
): () => void {
  const onWheel = (event: WheelEvent) => {
    if (options?.isDisabled?.()) return;

    const rect = container.getBoundingClientRect();
    const onScale = event.clientX >= rect.right - PRICE_SCALE_HIT_WIDTH_PX;
    // Zoom vertical en escala con botón pulsado lo gestiona attachChartScaleInteraction.
    if (onScale && (event.buttons & 1)) return;

    if (Math.abs(event.deltaY) < 0.5) return;

    event.preventDefault();
    event.stopPropagation();
    const anchor = options?.getAnchorLogical?.(event.clientX) ?? null;
    getChartSyncHub(chartSyncId).applyZoomAction(
      event.deltaY < 0 ? 'in' : 'out',
      options?.sourcePaneId,
      anchor,
    );
  };

  container.addEventListener('wheel', onWheel, { passive: false });
  return () => container.removeEventListener('wheel', onWheel);
}

/** @deprecated Usar attachChartHorizontalWheel */
export function attachChartTimeWheelSync(
  container: HTMLElement,
  chartSyncId: string,
  sourcePaneId = 'main',
): () => void {
  void sourcePaneId;
  return attachChartHorizontalWheel(container, chartSyncId);
}
