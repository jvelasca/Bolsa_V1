import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { ZoomIn, ZoomOut } from 'lucide-react';
import type { ChartIndicatorInstance, ChartInstanceConfig, IndicatorPointDto, OhlcvBarDto } from '@bolsa/shared';
import { colorForInstance, instanceDisplayName, isAiScoreIndicator } from '@bolsa/shared';
import { resolveSubRenderSeries, buildIndicatorBarsFingerprint } from '@/features/charts/indicator-compute';
import { IndicatorPanelChrome } from '@/features/charts/indicator-panel-chrome';
import {
  clampScaleZoom,
  marginsForZoom,
  PRICE_SCALE_MIN_WIDTH_PX,
  stepScaleZoom,
} from '@/features/charts/chart-scale-utils';
import { attachChartScaleDrag, attachChartScaleInteraction, type ChartScaleZoomHandlers } from '@/features/charts/chart-scale-wheel';
import { observeStableSize } from '@/features/charts/chart-stable-resize';
import { attachChartHorizontalWheel, getChartSyncHub } from '@/features/charts/chart-time-sync';
import { attachChartTimePan } from '@/features/charts/chart-time-pan';
import { barTimeToChartTime } from '@/features/charts/chart-utils';
import { useUiStore } from '@/stores/ui-store';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { cn } from '@/lib/utils';

interface SubIndicatorPanelProps {
  chartSyncId: string;
  instance: ChartIndicatorInstance;
  bars: OhlcvBarDto[];
  apiIndicators: IndicatorPointDto[];
  config: ChartInstanceConfig;
  className?: string;
  /** Si true, el panel ocupa la fila del grid (altura variable). */
  fillHeight?: boolean;
  panelHeight?: number;
  onConfigure: () => void;
  onToggleHidden: () => void;
  onDelete: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  scaleZoom?: number;
  onScaleZoomChange?: (scaleZoom: number) => void;
}

const MIN_HEIGHT = 72;
const COLLAPSED_HEADER_PX = 28;

export function SubIndicatorPanel({
  chartSyncId,
  instance,
  bars,
  apiIndicators,
  config,
  className,
  fillHeight = false,
  panelHeight = 140,
  onConfigure,
  onToggleHidden,
  onDelete,
  onMoveUp,
  onMoveDown,
  scaleZoom = 1,
  onScaleZoomChange,
}: SubIndicatorPanelProps) {
  const { colors, grid, cursor } = config;
  const containerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const anchorRef = useRef<ISeriesApi<'Line'> | null>(null);
  const extraRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const overboughtRef = useRef<ISeriesApi<'Line'> | null>(null);
  const oversoldRef = useRef<ISeriesApi<'Line'> | null>(null);
  const scaleZoomRef = useRef(scaleZoom);
  const chartHeightRef = useRef(0);
  const layoutReadyRef = useRef(false);

  const setSelectedIndicator = useUiStore((s) => s.setSelectedIndicatorInstanceId);
  const selectedIndicatorId = useUiStore((s) => s.selectedIndicatorInstanceId);
  const indicatorPresets = useWorkspaceStore((s) => s.workspace.indicatorPresets ?? []);

  const [layoutReady, setLayoutReady] = useState(false);
  const [chartHeight, setChartHeight] = useState(
    fillHeight ? MIN_HEIGHT : Math.max(0, panelHeight - COLLAPSED_HEADER_PX),
  );
  const [chartReady, setChartReady] = useState(false);
  const lineColor = colorForInstance(instance);
  const panelTitle = instanceDisplayName(instance, indicatorPresets);
  const lineWidth = instance.lineWidth ?? 2;
  const showChart = instance.visible && (fillHeight || panelHeight > COLLAPSED_HEADER_PX);
  const isSelected = selectedIndicatorId === instance.instanceId;

  const barsFingerprint = useMemo(() => buildIndicatorBarsFingerprint(bars), [bars]);
  const instanceParamsKey = useMemo(
    () => JSON.stringify(instance.parameters),
    [instance.parameters],
  );
  const renderSeries = useMemo(
    () => resolveSubRenderSeries(instance, bars, apiIndicators),
    [
      instance.instanceId,
      instance.definitionId,
      instance.visible,
      instanceParamsKey,
      barsFingerprint,
      apiIndicators,
    ],
  );

  useEffect(() => {
    scaleZoomRef.current = scaleZoom;
  }, [scaleZoom]);

  const setScaleZoom = (next: number) => {
    onScaleZoomChange?.(clampScaleZoom(next));
  };

  const scaleHandlersRef = useRef<ChartScaleZoomHandlers>({ onVerticalZoom: () => {} });
  scaleHandlersRef.current = {
    onVerticalZoom: (direction) => {
      const next = stepScaleZoom(scaleZoomRef.current, direction);
      scaleZoomRef.current = next;
      chartRef.current?.priceScale('right').applyOptions({
        minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
        scaleMargins: marginsForZoom(next),
      });
    },
    onVerticalZoomCommit: () => {
      setScaleZoom(scaleZoomRef.current);
    },
  };

  const applySeriesData = useCallback(() => {
    if (!lineRef.current || !chartRef.current) return;

    anchorRef.current?.setData(
      bars.map((bar) => ({
        time: barTimeToChartTime(bar.timestamp),
        value: bar.close,
      })),
    );

    const specs = renderSeries;
    const main = specs[0];
    lineRef.current.setData(main?.points ?? []);
    if (isAiScoreIndicator(instance.definitionId)) {
      lineRef.current.applyOptions({
        autoscaleInfoProvider: () => ({
          priceRange: { minValue: 0, maxValue: 100 },
        }),
      });
    } else {
      lineRef.current.applyOptions({ autoscaleInfoProvider: undefined });
    }

    const map = extraRefs.current;
    for (const [key, series] of map) {
      if (!specs.some((s, i) => i > 0 && s.key === key)) {
        chartRef.current.removeSeries(series);
        map.delete(key);
      }
    }
    specs.slice(1).forEach((spec) => {
      let series = map.get(spec.key);
      if (!series) {
        series = chartRef.current!.addSeries(LineSeries, {
          color: lineColor,
          lineWidth: 1,
          title: spec.title,
          priceScaleId: 'right',
          lastValueVisible: false,
          priceLineVisible: false,
        });
        map.set(spec.key, series);
      }
      series.setData(spec.points);
    });

    if (main && main.points.length > 0) {
      if (instance.definitionId === 'rsi' || instance.definitionId === 'stoch') {
        const refLines = main.points.map((point) => ({ time: point.time, value: 70 }));
        const refLow = main.points.map((point) => ({ time: point.time, value: 30 }));
        overboughtRef.current?.setData(refLines);
        oversoldRef.current?.setData(refLow);
      } else if (isAiScoreIndicator(instance.definitionId)) {
        const refHigh = main.points.map((point) => ({ time: point.time, value: 75 }));
        const refMid = main.points.map((point) => ({ time: point.time, value: 60 }));
        overboughtRef.current?.setData(refHigh);
        oversoldRef.current?.setData(refMid);
      } else {
        overboughtRef.current?.setData([]);
        oversoldRef.current?.setData([]);
      }
    } else {
      overboughtRef.current?.setData([]);
      oversoldRef.current?.setData([]);
    }

    if (main && main.points.length > 0) {
      requestAnimationFrame(() => {
        getChartSyncHub(chartSyncId).broadcastFrom('main');
      });
    } else if (bars.length > 0) {
      requestAnimationFrame(() => {
        getChartSyncHub(chartSyncId).broadcastFrom('main');
      });
    }
  }, [bars, chartSyncId, instance.definitionId, lineColor, renderSeries]);

  useLayoutEffect(() => {
    if (!showChart) return;
    const container = containerRef.current;
    if (!container) return;

    return observeStableSize(
      container,
      (width, nextHeight) => {
        const height = Math.max(MIN_HEIGHT, nextHeight);
        if (Math.abs(height - chartHeightRef.current) < 2 && layoutReadyRef.current) {
          const chart = chartRef.current;
          if (chart && width > 0) chart.applyOptions({ width });
          return;
        }
        chartHeightRef.current = height;
        const chart = chartRef.current;
        if (chart) {
          chart.applyOptions({ height, width: width > 0 ? width : undefined });
        } else {
          setChartHeight(height);
          const ready = width > 0 && height > 0;
          layoutReadyRef.current = ready;
          setLayoutReady(ready);
        }
      },
      { minDeltaPx: 2, debounceMs: 48 },
    );
  }, [fillHeight, panelHeight, showChart]);

  useEffect(() => {
    if (!showChart || !layoutReady || !containerRef.current || chartHeight <= 0) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: false,
      width: container.clientWidth || undefined,
      height: chartHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { visible: grid.showVertical, color: colors.gridColor },
        horzLines: { visible: grid.showHorizontal, color: colors.gridColor },
      },
      crosshair: {
        mode: cursor.mode === 'magnet' ? CrosshairMode.Magnet : CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: colors.gridColor,
        minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
        scaleMargins: marginsForZoom(scaleZoom),
      },
      timeScale: {
        borderColor: colors.gridColor,
        rightOffset: Math.round(grid.rightMarginPct),
        visible: false,
      },
      handleScroll: false,
      handleScale: false,
    });

    anchorRef.current = chart.addSeries(LineSeries, {
      color: 'transparent',
      lineWidth: 1,
      visible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    lineRef.current = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: lineWidth as 1 | 2 | 3 | 4,
      title: panelTitle,
      priceScaleId: 'right',
      lastValueVisible: instance.showLastValue === true,
      priceLineVisible: false,
    });

    if (instance.definitionId === 'rsi' || instance.definitionId === 'stoch') {
      overboughtRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(239, 68, 68, 0.45)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceScaleId: 'right',
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      oversoldRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(34, 197, 94, 0.45)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceScaleId: 'right',
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      });
    } else if (isAiScoreIndicator(instance.definitionId)) {
      overboughtRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(16, 185, 129, 0.45)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceScaleId: 'right',
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      oversoldRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(245, 158, 11, 0.45)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceScaleId: 'right',
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      });
    }

    chartRef.current = chart;
    chartHeightRef.current = chartHeight;
    layoutReadyRef.current = true;
    setChartReady(true);
    applySeriesData();

    return () => {
      chart.remove();
      chartRef.current = null;
      anchorRef.current = null;
      lineRef.current = null;
      overboughtRef.current = null;
      oversoldRef.current = null;
      extraRefs.current.clear();
      layoutReadyRef.current = false;
      setChartReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutReady, instance.instanceId, showChart]);

  useEffect(() => {
    if (!chartReady || !chartRef.current || !lineRef.current) return;
    return getChartSyncHub(chartSyncId).register({
      id: instance.instanceId,
      chart: chartRef.current,
      kind: 'sub',
      series: lineRef.current,
    });
  }, [chartReady, chartSyncId, instance.instanceId]);

  useEffect(() => {
    if (!showChart || !chartReady || !panelRef.current || !containerRef.current) return;

    const plotWidth = () =>
      Math.max(1, containerRef.current!.clientWidth - PRICE_SCALE_MIN_WIDTH_PX);

    const cancelScaleDrag = attachChartScaleDrag({
      hitTarget: containerRef.current,
      captureTarget: panelRef.current,
      handlers: scaleHandlersRef,
    });

    const cancelScaleWheel = attachChartScaleInteraction({
      hitTarget: containerRef.current,
      captureTarget: panelRef.current,
      handlers: scaleHandlersRef,
    });

    const cancelTimeWheel = attachChartHorizontalWheel(containerRef.current, chartSyncId, {
      sourcePaneId: instance.instanceId,
      getAnchorLogical: (clientX) => {
        const chart = chartRef.current;
        const el = containerRef.current;
        if (!chart || !el) return null;
        const x = clientX - el.getBoundingClientRect().left;
        return chart.timeScale().coordinateToLogical(x);
      },
    });

    const cancelTimePan = attachChartTimePan({
      hitTarget: containerRef.current,
      captureTarget: panelRef.current,
      onHorizontalPan: (deltaPx) => {
        getChartSyncHub(chartSyncId).applyHorizontalPanPixels(
          deltaPx,
          plotWidth(),
          instance.instanceId,
        );
      },
    });

    return () => {
      cancelScaleDrag();
      cancelScaleWheel();
      cancelTimeWheel();
      cancelTimePan();
    };
  }, [chartReady, chartSyncId, instance.instanceId, showChart]);

  useEffect(() => {
    if (!showChart) return;
    applySeriesData();
  }, [applySeriesData, showChart]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !showChart) return;
    chart.applyOptions({
      timeScale: {
        borderColor: colors.gridColor,
        rightOffset: Math.round(grid.rightMarginPct),
      },
    });
    chart.priceScale('right').applyOptions({
      minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
      scaleMargins: marginsForZoom(scaleZoom),
    });
    lineRef.current?.applyOptions({
      color: lineColor,
      lineWidth: lineWidth as 1 | 2 | 3 | 4,
      title: panelTitle,
      lastValueVisible: instance.showLastValue === true,
    });
  }, [colors.gridColor, grid.rightMarginPct, instance, lineColor, lineWidth, panelTitle, scaleZoom, showChart]);

  const zoomControls = showChart ? (
    <div className="flex items-center gap-0.5 border-l border-border/50 pl-1">
      <button
        type="button"
        title="Alejar eje Y (pulsar en la escala derecha y arrastrar, o rueda con botón pulsado)"
        onClick={() => setScaleZoom(stepScaleZoom(scaleZoom, 'out'))}
        className="rounded p-0.5 hover:bg-accent"
      >
        <ZoomOut className="h-3 w-3" />
      </button>
      <span className="w-7 text-center text-[9px] tabular-nums text-muted-foreground">
        {Math.round(scaleZoom * 100)}%
      </span>
      <button
        type="button"
        title="Acercar eje Y (pulsar en la escala derecha y arrastrar, o rueda con botón pulsado)"
        onClick={() => setScaleZoom(stepScaleZoom(scaleZoom, 'in'))}
        className="rounded p-0.5 hover:bg-accent"
      >
        <ZoomIn className="h-3 w-3" />
      </button>
    </div>
  ) : null;

  return (
    <div
      ref={panelRef}
      className={cn(
        'flex flex-col border-b border-border bg-muted/5',
        fillHeight || !instance.visible ? 'min-h-0 h-full overflow-hidden' : 'shrink-0',
        isSelected && 'outline outline-1 -outline-offset-1 outline-primary/40',
        className,
      )}
      style={
        !fillHeight && instance.visible
          ? { minHeight: panelHeight, height: panelHeight }
          : undefined
      }
      onClick={() => setSelectedIndicator(instance.instanceId)}
    >
      <IndicatorPanelChrome
        title={panelTitle}
        hidden={!instance.visible}
        onConfigure={onConfigure}
        onToggleHidden={onToggleHidden}
        onDelete={onDelete}
        onMoveUp={onMoveUp}
        onMoveDown={onMoveDown}
        extra={zoomControls}
      />
      {showChart && (
        <div
          ref={containerRef}
          className="min-h-[72px] w-full flex-1"
          title="Doble clic para configurar el indicador"
          onDoubleClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setSelectedIndicator(instance.instanceId);
            onConfigure();
          }}
        />
      )}
    </div>
  );
}
