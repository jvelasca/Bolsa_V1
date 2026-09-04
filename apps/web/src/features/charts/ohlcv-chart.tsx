import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type {
  ChartDrawTool,
  ChartDrawing,
  ChartIndicatorInstance,
  ChartInstanceConfig,
  IndicatorPointDto,
  OhlcvBarDto,
} from "@bolsa/shared";
import {
  chartSeriesUsesSyntheticTime,
  colorForInstance,
  DEFAULT_CHART_DRAW_COLOR,
  isIntradayChartTimeframe,
  normalizeChartSeriesType,
  normalizeChartSeriesTypeParams,
  resolveDrawToolStyle,
  type ChartSeriesType,
  type ChartSeriesTypeParams,
  type ChartTimeframe,
} from "@bolsa/shared";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  formatSyncError,
  useInstrumentSync,
} from "@/features/instruments/use-instrument-sync";
import { ChartDrawingsLayer } from "@/features/charts/chart-drawings-layer";
import { ChartCrosshairMeasure } from "@/features/charts/chart-crosshair-measure";
import { ChartCursorStyleOverlay } from "@/features/charts/chart-cursor-style-overlay";
import { ChartF3OrderProjectionLayer } from "@/features/charts/chart-f3-order-projection-layer";
import { ChartOperationalPlanLevelsLayer } from "@/features/charts/chart-operational-plan-levels-layer";
import { ChartDecisionSurfaceHud } from "@/features/charts/chart-decision-surface-hud";
import { ChartFocusToggle } from "@/features/charts/chart-focus-toggle";
import { ChartPlanContextStrip } from "@/features/charts/chart-plan-context-strip";
import type { DecisionSurfacePlacementV1 } from "@/features/trading/mercado-decision-surface-prefs";
import { ChartTimeAxisLabel } from "@/features/charts/chart-time-axis-label";
import {
  blocksChartPan,
  blocksChartPointerPan,
  canInteractWithDrawings,
  shouldHideNativeCrosshair,
  usesCustomChartCursor,
} from "@/features/charts/chart-draw-tool-utils";
import {
  hasVolumeInstance,
  overlayTrendInstances,
  resolveOverlayRenderSeries,
} from "@/features/charts/indicator-compute";
import {
  findOverlayInstanceAtPixel,
  type OverlaySeriesHitEntry,
} from "@/features/charts/chart-indicator-hit";
import {
  barsToVolumeSeries,
  barTimeToChartTime,
  CHART_REFLOW_EVENT,
  formatChartTimeAxisLabel,
  hasChartData,
  indicatorToLineSeries,
} from "./chart-utils";
import {
  applyMainPriceSeriesColors,
  createMainPriceSeries,
  resolveMainSeriesEngine,
  setMainPriceSeriesData,
  type ChartMainPriceSeries,
  type MainSeriesEngineKind,
} from "@/features/charts/chart-main-series";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  clampPricePanOffset,
  priceMarginsForZoom,
  PRICE_SCALE_MIN_WIDTH_PX,
  stepScaleZoom,
  volumeMarginsForZoom,
} from "@/features/charts/chart-scale-utils";
import {
  attachChartPricePan,
  type ChartPricePanHandlers,
} from "@/features/charts/chart-price-pan";
import {
  attachChartScaleInteraction,
  type ChartScaleZoomHandlers,
} from "@/features/charts/chart-scale-wheel";
import { observeStableSize } from "@/features/charts/chart-stable-resize";
import {
  attachChartHorizontalWheel,
  getChartSyncHub,
} from "@/features/charts/chart-time-sync";
import { useChartCursorStore } from "@/stores/chart-cursor-store";

interface OhlcvChartProps {
  bars: OhlcvBarDto[];
  indicators?: IndicatorPointDto[];
  /** Si se define, el gráfico renderiza overlays desde instancias (modo workspace). */
  indicatorInstances?: ChartIndicatorInstance[];
  config: ChartInstanceConfig;
  drawings?: ChartDrawing[];
  drawTool?: ChartDrawTool;
  chartTimeframe?: ChartTimeframe;
  seriesType?: ChartSeriesType;
  seriesTypeParams?: ChartSeriesTypeParams;
  selectedDrawingId?: string | null;
  isLoading?: boolean;
  instrumentId?: string;
  symbol?: string;
  /** Rellena el alto del contenedor padre en lugar de usar display.height fijo */
  fillContainer?: boolean;
  /** ID de sincronización temporal (p. ej. tab del gráfico). */
  chartSyncId?: string;
  onPriceScaleZoomChange?: (scaleZoom: number) => void;
  onVolumeScaleZoomChange?: (scaleZoom: number) => void;
  onOpenSyncDialog?: () => void;
  onAddDrawing?: (drawing: ChartDrawing) => void;
  onUpdateDrawing?: (
    drawingId: string,
    patch: import("@bolsa/shared").ChartDrawingVertexPatch,
  ) => void;
  onSelectDrawing?: (id: string | null) => void;
  onDrawingAdded?: (drawingId: string) => void;
  onDrawingDragEnd?: () => void;
  onOpenDrawingEditor?: (drawingId: string | null) => void;
  onConfigureIndicator?: (instanceId: string) => void;
  drawingsLayerHidden?: boolean;
  drawingsLayerLocked?: boolean;
  /** Mercado: pinta los niveles de `OperationalPlanView` del valor activo. */
  showOperationalPlanLevels?: boolean;
  /** V1.63 — ubicación de la Decision Surface (`panel` | `chart`). */
  decisionSurfacePlacement?: DecisionSurfacePlacementV1;
}

function scheduleReflow(callback: () => void) {
  let raf: number | null = null;
  const run = () => {
    if (raf != null) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      raf = null;
      callback();
    });
  };
  run();
  return () => {
    if (raf != null) cancelAnimationFrame(raf);
  };
}

const MIN_CHART_HEIGHT = 160;

export function OhlcvChart({
  bars,
  indicators = [],
  indicatorInstances,
  config,
  drawings = [],
  drawTool = "select",
  chartTimeframe = "1d",
  seriesType: seriesTypeProp = "candles",
  seriesTypeParams: seriesTypeParamsProp,
  selectedDrawingId = null,
  isLoading = false,
  instrumentId,
  symbol,
  fillContainer = false,
  chartSyncId,
  onPriceScaleZoomChange,
  onVolumeScaleZoomChange,
  onOpenSyncDialog,
  onAddDrawing,
  onUpdateDrawing,
  onSelectDrawing,
  onDrawingAdded,
  onDrawingDragEnd,
  onOpenDrawingEditor,
  onConfigureIndicator,
  drawingsLayerHidden = false,
  drawingsLayerLocked = false,
  showOperationalPlanLevels = false,
  decisionSurfacePlacement = "panel",
}: OhlcvChartProps) {
  const { colors, display, grid, cursor } = config;
  const configuredHeight = display.height;
  const instanceMode = indicatorInstances !== undefined;
  const overlayRenderByInstance = useMemo(() => {
    if (!instanceMode)
      return new Map<string, ReturnType<typeof resolveOverlayRenderSeries>>();
    const map = new Map<
      string,
      ReturnType<typeof resolveOverlayRenderSeries>
    >();
    for (const instance of overlayTrendInstances(indicatorInstances ?? [])) {
      map.set(
        instance.instanceId,
        resolveOverlayRenderSeries(instance, bars, indicators),
      );
    }
    return map;
  }, [instanceMode, indicators, bars, indicatorInstances]);
  const showVolume = instanceMode
    ? hasVolumeInstance(indicatorInstances ?? [])
    : display.showVolume;
  const seriesType = normalizeChartSeriesType(seriesTypeProp);
  const seriesTypeParams = normalizeChartSeriesTypeParams(seriesTypeParamsProp);
  const usesSyntheticTime = chartSeriesUsesSyntheticTime(seriesType);
  const mainSeriesEngine = resolveMainSeriesEngine(seriesType);
  const drawingEnabled = Boolean(
    onAddDrawing && onSelectDrawing && onUpdateDrawing,
  );
  const isDrawingMode = blocksChartPan(drawTool);
  const crosshairMagnet = drawTool === "crosshair" || cursor.mode === "magnet";
  const hideNativeCrosshair = shouldHideNativeCrosshair(drawTool);
  const showTimeAxisLabel = config.cursor.showTimeAxisLabel ?? true;
  const drawingCapturesPointerRef = useRef(false);
  const isIntraday = isIntradayChartTimeframe(chartTimeframe);
  const syncMutation = useInstrumentSync(instrumentId);
  const lastDrawStyleMemory = useWorkspaceStore(
    (s) => s.workspace.chartToolbarGlobal?.lastDrawStyleByTool?.[drawTool],
  );
  const drawToolColor = useMemo(
    () =>
      resolveDrawToolStyle(drawTool, { memory: lastDrawStyleMemory }).color ??
      DEFAULT_CHART_DRAW_COLOR,
    [drawTool, lastDrawStyleMemory],
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const [chartContainer, setChartContainer] = useState<HTMLDivElement | null>(
    null,
  );
  const bindChartContainer = useCallback((node: HTMLDivElement | null) => {
    containerRef.current = node;
    setChartContainer(node);
  }, []);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainSeriesRef = useRef<ChartMainPriceSeries | null>(null);
  const mainSeriesEngineRef = useRef<MainSeriesEngineKind>("candlestick");
  const seriesTypeParamsRef = useRef(seriesTypeParams);
  seriesTypeParamsRef.current = seriesTypeParams;
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const sma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const overlaySeriesRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const overlaySeriesDataRef = useRef(new Map<string, OverlaySeriesHitEntry>());
  const priceScaleZoomRef = useRef(config.grid.priceScaleZoom ?? 1);
  const volumeScaleZoomRef = useRef(1);
  const pricePanOffsetRef = useRef(0);
  const shouldFitContentRef = useRef(true);

  useEffect(() => {
    shouldFitContentRef.current = true;
    pricePanOffsetRef.current = 0;
  }, [instrumentId, chartTimeframe]);

  useEffect(() => {
    shouldFitContentRef.current = true;
  }, [seriesType, seriesTypeParams]);

  const volumeInstance = indicatorInstances?.find(
    (item) => item.definitionId === "volume",
  );
  const priceScaleZoom = config.grid.priceScaleZoom ?? 1;
  const volumeScaleZoom = volumeInstance?.scaleZoom ?? 1;

  useEffect(() => {
    priceScaleZoomRef.current = priceScaleZoom;
  }, [priceScaleZoom]);

  useEffect(() => {
    volumeScaleZoomRef.current = volumeScaleZoom;
  }, [volumeScaleZoom]);

  const showVolumeRef = useRef(showVolume);
  const topMarginPctRef = useRef(grid.topMarginPct);
  useEffect(() => {
    showVolumeRef.current = showVolume;
  }, [showVolume]);
  useEffect(() => {
    topMarginPctRef.current = grid.topMarginPct;
  }, [grid.topMarginPct]);

  const scaleHandlersRef = useRef<ChartScaleZoomHandlers>({
    onVerticalZoom: () => {},
  });
  scaleHandlersRef.current = {
    onVerticalZoom: (direction) => {
      const next = stepScaleZoom(priceScaleZoomRef.current, direction);
      priceScaleZoomRef.current = next;
      chartRef.current?.priceScale("right").applyOptions({
        scaleMargins: priceMarginsForZoom(
          next,
          showVolumeRef.current,
          topMarginPctRef.current,
          pricePanOffsetRef.current,
        ),
      });
    },
    onVerticalZoomCommit: () => {
      onPriceScaleZoomChange?.(priceScaleZoomRef.current);
    },
    onVolumeZoom:
      volumeInstance && onVolumeScaleZoomChange
        ? (direction) => {
            const next = stepScaleZoom(volumeScaleZoomRef.current, direction);
            volumeScaleZoomRef.current = next;
            chartRef.current?.priceScale("volume").applyOptions({
              scaleMargins: volumeMarginsForZoom(next),
            });
          }
        : undefined,
    onVolumeZoomCommit:
      volumeInstance && onVolumeScaleZoomChange
        ? () => {
            onVolumeScaleZoomChange(volumeScaleZoomRef.current);
          }
        : undefined,
  };

  const panHandlersRef = useRef<ChartPricePanHandlers>({
    onHorizontalPan: () => {},
    onPriceVerticalPan: () => {},
  });
  panHandlersRef.current = {
    onHorizontalPan: (deltaPx) => {
      if (!chartSyncId || !containerRef.current) return;
      const plotWidth = Math.max(
        1,
        containerRef.current.clientWidth - PRICE_SCALE_MIN_WIDTH_PX,
      );
      getChartSyncHub(chartSyncId).applyHorizontalPanPixels(deltaPx, plotWidth);
    },
    onPriceVerticalPan: (deltaPx, height) => {
      const delta = deltaPx / Math.max(height, 1);
      pricePanOffsetRef.current = clampPricePanOffset(
        pricePanOffsetRef.current + delta * 0.85,
      );
      chartRef.current?.priceScale("right").applyOptions({
        scaleMargins: priceMarginsForZoom(
          priceScaleZoomRef.current,
          showVolumeRef.current,
          topMarginPctRef.current,
          pricePanOffsetRef.current,
        ),
      });
    },
  };

  const [layoutReady, setLayoutReady] = useState(false);
  const [chartReady, setChartReady] = useState(false);
  const chartHeightRef = useRef(
    fillContainer ? 0 : Math.max(MIN_CHART_HEIGHT, configuredHeight),
  );
  const layoutReadyRef = useRef(false);

  const resolvedHeight = fillContainer
    ? Math.max(MIN_CHART_HEIGHT, chartHeightRef.current)
    : Math.max(MIN_CHART_HEIGHT, configuredHeight);

  const applySeriesData = useCallback(() => {
    if (!chartReady || !mainSeriesRef.current || !chartRef.current) return;

    if (!hasChartData(bars)) {
      mainSeriesRef.current.setData([]);
      volumeRef.current?.setData([]);
      sma20Ref.current?.setData([]);
      sma50Ref.current?.setData([]);
      ema20Ref.current?.setData([]);
      return;
    }

    setMainPriceSeriesData(
      mainSeriesRef.current,
      mainSeriesEngineRef.current,
      bars,
      {
        upColor: colors.upColor,
        downColor: colors.downColor,
      },
      seriesTypeParamsRef.current,
    );
    if (usesSyntheticTime) {
      volumeRef.current?.setData([]);
    } else {
      volumeRef.current?.setData(
        barsToVolumeSeries(bars, colors.volumeUpColor, colors.volumeDownColor),
      );
    }

    if (instanceMode) {
      sma20Ref.current?.setData([]);
      sma50Ref.current?.setData([]);
      ema20Ref.current?.setData([]);
    } else if (indicators.length > 0) {
      sma20Ref.current?.setData(
        display.showSma20 ? indicatorToLineSeries(indicators, "sma20") : [],
      );
      sma50Ref.current?.setData(
        display.showSma50 ? indicatorToLineSeries(indicators, "sma50") : [],
      );
      ema20Ref.current?.setData(
        display.showEma20 ? indicatorToLineSeries(indicators, "ema20") : [],
      );
    } else {
      sma20Ref.current?.setData([]);
      sma50Ref.current?.setData([]);
      ema20Ref.current?.setData([]);
    }

    if (instanceMode && chartRef.current) {
      const overlays = overlayTrendInstances(indicatorInstances ?? []);
      const map = overlaySeriesRef.current;
      const dataMap = overlaySeriesDataRef.current;
      for (const [id, series] of map) {
        if (!overlays.some((item) => id.startsWith(`${item.instanceId}:`))) {
          chartRef.current.removeSeries(series);
          map.delete(id);
          dataMap.delete(id);
        }
      }
      overlays.forEach((instance, index) => {
        const renderSeries =
          overlayRenderByInstance.get(instance.instanceId) ?? [];
        for (const spec of renderSeries) {
          const seriesKey = `${instance.instanceId}:${spec.key}`;
          let series = map.get(seriesKey);
          if (!series) {
            series = chartRef.current!.addSeries(LineSeries, {
              color: colorForInstance(instance, index),
              lineWidth: (instance.lineWidth ??
                (spec.key === "mid" || spec.key === "main" ? 2 : 1)) as
                | 1
                | 2
                | 3
                | 4,
              lineStyle: spec.dashed ? LineStyle.Dashed : LineStyle.Solid,
              title: spec.title,
              lastValueVisible: instance.showLastValue === true,
              priceLineVisible: false,
            });
            map.set(seriesKey, series);
          }
          series.applyOptions({
            color: colorForInstance(instance, index),
            lineWidth: (instance.lineWidth ?? 2) as 1 | 2 | 3 | 4,
            title: spec.title,
            visible: instance.visible,
            lastValueVisible: instance.showLastValue === true,
            priceLineVisible: false,
          });
          series.setData(spec.points);
          dataMap.set(seriesKey, { series, points: spec.points });
        }
      });
    }

    if (shouldFitContentRef.current && hasChartData(bars)) {
      chartRef.current.timeScale().fitContent();
      shouldFitContentRef.current = false;
      if (chartSyncId) {
        requestAnimationFrame(() => {
          getChartSyncHub(chartSyncId).broadcastFrom("main");
        });
      }
    }
  }, [
    bars,
    chartReady,
    chartSyncId,
    colors.downColor,
    colors.upColor,
    colors.volumeDownColor,
    colors.volumeUpColor,
    display.showEma20,
    display.showSma20,
    display.showSma50,
    indicatorInstances,
    indicators,
    instanceMode,
    overlayRenderByInstance,
    usesSyntheticTime,
  ]);

  const applySeriesDataRef = useRef(applySeriesData);
  applySeriesDataRef.current = applySeriesData;

  const fitChartLayout = useCallback(() => {
    const chart = chartRef.current;
    const container = containerRef.current;
    if (!chart || !container) return;

    const width = container.clientWidth;
    const height = fillContainer
      ? Math.max(MIN_CHART_HEIGHT, chartHeightRef.current)
      : resolvedHeight;
    if (width > 0) {
      chart.applyOptions({ width, height });
    }

    applySeriesDataRef.current();
  }, [fillContainer, resolvedHeight]);

  const syncChartSize = useCallback(() => {
    const chart = chartRef.current;
    const container = containerRef.current;
    if (!chart || !container) return;

    const width = container.clientWidth;
    const height = fillContainer
      ? Math.max(MIN_CHART_HEIGHT, chartHeightRef.current)
      : resolvedHeight;
    if (width > 0) {
      chart.applyOptions({ width, height });
    }
  }, [fillContainer, resolvedHeight]);

  const fitChartLayoutRef = useRef(fitChartLayout);
  fitChartLayoutRef.current = fitChartLayout;
  const syncChartSizeRef = useRef(syncChartSize);
  syncChartSizeRef.current = syncChartSize;

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    return observeStableSize(
      container,
      (width, nextHeight) => {
        const height = Math.max(MIN_CHART_HEIGHT, nextHeight);
        chartHeightRef.current = height;

        const chart = chartRef.current;
        if (chart && width > 0) {
          chart.applyOptions({ width, height });
        }

        const ready =
          width > 0 && (fillContainer ? height > 0 : nextHeight > 0);
        if (fillContainer) {
          if (ready && !layoutReadyRef.current) {
            layoutReadyRef.current = true;
            setLayoutReady(true);
          }
          return;
        }

        if (ready !== layoutReadyRef.current) {
          layoutReadyRef.current = ready;
          setLayoutReady(ready);
        }
      },
      { minDeltaPx: 2, debounceMs: 48 },
    );
  }, [fillContainer]);

  useEffect(() => {
    if (!layoutReady || !containerRef.current || resolvedHeight <= 0) return;

    const overlaySeries = overlaySeriesRef.current;
    const overlaySeriesData = overlaySeriesDataRef.current;

    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: false,
      width: container.clientWidth || undefined,
      height: Math.max(
        MIN_CHART_HEIGHT,
        chartHeightRef.current || resolvedHeight,
      ),
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { visible: grid.showVertical, color: colors.gridColor },
        horzLines: { visible: grid.showHorizontal, color: colors.gridColor },
      },
      crosshair: {
        mode: crosshairMagnet ? CrosshairMode.Magnet : CrosshairMode.Normal,
        vertLine: {
          visible: !hideNativeCrosshair,
          labelVisible: false,
        },
        horzLine: { visible: !hideNativeCrosshair, labelVisible: false },
      },
      localization: {
        locale: "es-ES",
        timeFormatter: (time: Time) =>
          formatChartTimeAxisLabel(time, isIntraday),
      },
      rightPriceScale: {
        borderColor: colors.gridColor,
        minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
        scaleMargins: priceMarginsForZoom(
          priceScaleZoom,
          showVolume,
          grid.topMarginPct,
          pricePanOffsetRef.current,
        ),
      },
      timeScale: {
        borderColor: colors.gridColor,
        rightOffset: Math.round(grid.rightMarginPct),
        timeVisible: true,
        secondsVisible: isIntraday,
      },
      handleScroll: isDrawingMode
        ? false
        : {
            mouseWheel: false,
            pressedMouseMove: false,
            horzTouchDrag: true,
            vertTouchDrag: false,
          },
      handleScale: isDrawingMode
        ? false
        : {
            mouseWheel: false,
            pinch: false,
            axisPressedMouseMove: { price: false, time: false },
          },
    });

    const mainSeries = createMainPriceSeries(chart, mainSeriesEngine, {
      upColor: colors.upColor,
      downColor: colors.downColor,
    });
    mainSeriesRef.current = mainSeries;
    mainSeriesEngineRef.current = mainSeriesEngine;

    if (showVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: volumeMarginsForZoom(volumeScaleZoom),
      });
      volumeRef.current = volume;
    }

    if (!instanceMode) {
      sma20Ref.current = chart.addSeries(LineSeries, {
        color: colors.sma20Color,
        lineWidth: 2,
        title: "SMA20",
        visible: display.showSma20,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      sma50Ref.current = chart.addSeries(LineSeries, {
        color: colors.sma50Color,
        lineWidth: 2,
        title: "SMA50",
        visible: display.showSma50,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      ema20Ref.current = chart.addSeries(LineSeries, {
        color: colors.ema20Color,
        lineWidth: 2,
        title: "EMA20",
        visible: display.showEma20,
        lastValueVisible: false,
        priceLineVisible: false,
      });
    }

    chartRef.current = chart;
    setChartReady(true);

    const cancelReflow = scheduleReflow(() => fitChartLayoutRef.current());

    return () => {
      cancelReflow();
      chart.remove();
      chartRef.current = null;
      mainSeriesRef.current = null;
      mainSeriesEngineRef.current = "candlestick";
      volumeRef.current = null;
      sma20Ref.current = null;
      sma50Ref.current = null;
      ema20Ref.current = null;
      overlaySeries.clear();
      overlaySeriesData.clear();
      setChartReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutReady, showVolume, instanceMode, mainSeriesEngine, seriesType]);

  useEffect(() => {
    if (!chartReady) return;
    return scheduleReflow(applySeriesData);
  }, [applySeriesData, chartReady]);

  useEffect(() => {
    if (!chartReady) return;
    fitChartLayoutRef.current();
  }, [chartReady, resolvedHeight]);

  useEffect(() => {
    const onReflow = () => {
      syncChartSizeRef.current();
      applySeriesDataRef.current();
    };
    window.addEventListener(CHART_REFLOW_EVENT, onReflow);
    return () => window.removeEventListener(CHART_REFLOW_EVENT, onReflow);
  }, []);

  useEffect(() => {
    if (
      !chartReady ||
      !chartRef.current ||
      !mainSeriesRef.current ||
      !chartSyncId
    )
      return;
    return getChartSyncHub(chartSyncId).register({
      id: "main",
      chart: chartRef.current,
      kind: "main",
      series: mainSeriesRef.current,
    });
  }, [chartReady, chartSyncId]);

  useEffect(() => {
    if (!chartReady || !containerRef.current || !chartSyncId || isDrawingMode)
      return;
    return attachChartHorizontalWheel(containerRef.current, chartSyncId, {
      isDisabled: () => isDrawingMode,
      sourcePaneId: "main",
      getAnchorLogical: (clientX) => {
        const chart = chartRef.current;
        const el = containerRef.current;
        if (!chart || !el) return null;
        const x = clientX - el.getBoundingClientRect().left;
        return chart.timeScale().coordinateToLogical(x);
      },
    });
  }, [chartReady, chartSyncId, isDrawingMode]);

  const handleConfigureIndicatorAtPoint = useCallback(
    (clientX: number, clientY: number) => {
      if (
        !onConfigureIndicator ||
        !instanceMode ||
        !chartRef.current ||
        !chartContainer
      )
        return;
      const instanceId = findOverlayInstanceAtPixel(
        chartRef.current,
        chartContainer,
        clientX,
        clientY,
        overlaySeriesDataRef.current,
      );
      if (instanceId) onConfigureIndicator(instanceId);
    },
    [chartContainer, instanceMode, onConfigureIndicator],
  );

  useEffect(() => {
    if (!chartContainer || !onConfigureIndicator || !instanceMode) return;
    if (drawingEnabled && canInteractWithDrawings(drawTool)) return;

    const onDblClick = (event: MouseEvent) => {
      handleConfigureIndicatorAtPoint(event.clientX, event.clientY);
    };
    chartContainer.addEventListener("dblclick", onDblClick);
    return () => chartContainer.removeEventListener("dblclick", onDblClick);
  }, [
    chartContainer,
    drawTool,
    drawingEnabled,
    handleConfigureIndicatorAtPoint,
    instanceMode,
    onConfigureIndicator,
  ]);

  const panInteractionDisabled =
    blocksChartPan(drawTool) || drawTool === "crosshair";

  useEffect(() => {
    if (
      !chartReady ||
      !wrapperRef.current ||
      !containerRef.current ||
      panInteractionDisabled
    )
      return;

    const cancelPan = attachChartPricePan({
      hitTarget: containerRef.current,
      captureTarget: wrapperRef.current,
      panHandlers: panHandlersRef,
      scaleHandlers: scaleHandlersRef,
      volumeBandPct: showVolume && volumeInstance?.instanceId ? 0.28 : 0,
      isDisabled: () =>
        blocksChartPointerPan(drawTool, selectedDrawingId ?? null) ||
        drawingCapturesPointerRef.current,
    });

    const cancelScaleWheel = attachChartScaleInteraction({
      hitTarget: containerRef.current,
      captureTarget: wrapperRef.current,
      handlers: scaleHandlersRef,
      volumeBandPct: showVolume && volumeInstance?.instanceId ? 0.28 : 0,
    });

    return () => {
      cancelPan();
      cancelScaleWheel();
    };
  }, [
    chartReady,
    panInteractionDisabled,
    drawTool,
    selectedDrawingId,
    showVolume,
    volumeInstance?.instanceId,
  ]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !chartReady || !instrumentId) return;

    const handler = (param: { time?: unknown }) => {
      if (!param.time) {
        useChartCursorStore.getState().clearHoveredBar(instrumentId);
        return;
      }
      const bar =
        bars.find(
          (item) => barTimeToChartTime(item.timestamp) === param.time,
        ) ?? null;
      useChartCursorStore.getState().setHoveredBar(instrumentId, bar);
    };

    chart.subscribeCrosshairMove(handler);
    return () => chart.unsubscribeCrosshairMove(handler);
  }, [bars, chartReady, instrumentId]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    chart.applyOptions({
      height: resolvedHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { visible: grid.showVertical, color: colors.gridColor },
        horzLines: { visible: grid.showHorizontal, color: colors.gridColor },
      },
      crosshair: {
        mode: crosshairMagnet ? CrosshairMode.Magnet : CrosshairMode.Normal,
        vertLine: {
          visible: !hideNativeCrosshair,
          labelVisible: false,
        },
        horzLine: { visible: !hideNativeCrosshair, labelVisible: false },
      },
      localization: {
        locale: "es-ES",
        timeFormatter: (time: Time) =>
          formatChartTimeAxisLabel(time, isIntraday),
      },
      rightPriceScale: {
        borderColor: colors.gridColor,
        minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
        scaleMargins: priceMarginsForZoom(
          priceScaleZoom,
          showVolume,
          grid.topMarginPct,
          pricePanOffsetRef.current,
        ),
      },
      timeScale: {
        borderColor: colors.gridColor,
        rightOffset: Math.round(grid.rightMarginPct),
        timeVisible: true,
        secondsVisible: isIntraday,
      },
      handleScroll: isDrawingMode
        ? false
        : {
            mouseWheel: false,
            pressedMouseMove: false,
            horzTouchDrag: true,
            vertTouchDrag: false,
          },
      handleScale: isDrawingMode
        ? false
        : {
            mouseWheel: false,
            pinch: false,
            axisPressedMouseMove: { price: false, time: false },
          },
    });

    if (showVolume && volumeRef.current) {
      chart.priceScale("volume").applyOptions({
        scaleMargins: volumeMarginsForZoom(volumeScaleZoom),
      });
    }

    if (mainSeriesRef.current) {
      applyMainPriceSeriesColors(
        mainSeriesRef.current,
        mainSeriesEngineRef.current,
        {
          upColor: colors.upColor,
          downColor: colors.downColor,
        },
      );
    }

    sma20Ref.current?.applyOptions({
      color: colors.sma20Color,
      visible: display.showSma20,
    });
    sma50Ref.current?.applyOptions({
      color: colors.sma50Color,
      visible: display.showSma50,
    });
    ema20Ref.current?.applyOptions({
      color: colors.ema20Color,
      visible: display.showEma20,
    });

    volumeRef.current?.applyOptions({
      color: colors.volumeUpColor,
    });
  }, [
    resolvedHeight,
    colors,
    grid,
    cursor.mode,
    drawTool,
    crosshairMagnet,
    display.showSma20,
    display.showSma50,
    display.showEma20,
    showVolume,
    isDrawingMode,
    isIntraday,
    priceScaleZoom,
    volumeScaleZoom,
    showTimeAxisLabel,
    hideNativeCrosshair,
  ]);

  const showEmptyMessage = !isLoading && !hasChartData(bars);

  return (
    <div
      ref={wrapperRef}
      className={cn(
        "relative w-full",
        fillContainer && "h-full min-h-0",
        drawTool === "crosshair" && "cursor-crosshair",
      )}
      style={fillContainer ? undefined : { height: resolvedHeight }}
    >
      <div ref={bindChartContainer} className="h-full w-full" />
      {isLoading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-lg bg-background/60 text-sm text-muted-foreground">
          Cargando histórico…
        </div>
      )}
      {showEmptyMessage && (
        <div className="pointer-events-auto absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-background/90 p-4 text-center text-sm text-muted-foreground">
          <p>
            Sin datos OHLCV{symbol ? ` para ${symbol}` : ""}. Sincroniza el
            instrumento para cargar histórico.
          </p>
          {instrumentId && (
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button
                type="button"
                size="sm"
                disabled={syncMutation.isPending}
                onClick={() => void syncMutation.mutate()}
              >
                <RefreshCw
                  className={cn(
                    "mr-1 h-4 w-4",
                    syncMutation.isPending && "animate-spin",
                  )}
                />
                {syncMutation.isPending
                  ? "Sincronizando…"
                  : "Sincronizar Yahoo"}
              </Button>
              {onOpenSyncDialog && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={onOpenSyncDialog}
                >
                  Más opciones…
                </Button>
              )}
            </div>
          )}
          {syncMutation.isError && (
            <p className="text-xs text-destructive">
              {formatSyncError(syncMutation.error)}
            </p>
          )}
        </div>
      )}
      {chartReady && hasChartData(bars) && (
        <ChartTimeAxisLabel
          chart={chartRef.current}
          container={chartContainer}
          enabled={showTimeAxisLabel}
          showTime={isIntraday}
        />
      )}
      {drawingEnabled &&
        chartReady &&
        hasChartData(bars) &&
        usesCustomChartCursor(drawTool) && (
          <ChartCursorStyleOverlay
            chart={chartRef.current}
            series={mainSeriesRef.current}
            container={chartContainer}
            height={resolvedHeight}
            tool={drawTool}
            color={drawToolColor}
            onPlaceArrowMarker={drawTool === "arrow" ? onAddDrawing : undefined}
          />
        )}
      {drawingEnabled &&
        chartReady &&
        hasChartData(bars) &&
        drawTool === "crosshair" && (
          <ChartCrosshairMeasure
            chart={chartRef.current}
            series={mainSeriesRef.current}
            container={chartContainer}
            height={resolvedHeight}
            bars={bars}
            active
          />
        )}
      {drawingEnabled && chartReady && hasChartData(bars) && (
        <ChartDrawingsLayer
          chart={chartRef.current}
          series={mainSeriesRef.current}
          container={chartContainer}
          height={resolvedHeight}
          bars={bars}
          drawings={drawings}
          tool={drawTool}
          selectedId={selectedDrawingId}
          onAdd={onAddDrawing!}
          onUpdate={onUpdateDrawing!}
          onSelect={onSelectDrawing!}
          onDrawingAdded={onDrawingAdded}
          onDrawingDragEnd={onDrawingDragEnd}
          onOpenDrawingEditor={onOpenDrawingEditor}
          onBackgroundDoubleClick={
            onConfigureIndicator && instanceMode
              ? handleConfigureIndicatorAtPoint
              : undefined
          }
          onInteractionCaptureChange={(captures) => {
            drawingCapturesPointerRef.current = captures;
          }}
          layerHidden={drawingsLayerHidden}
          layerLocked={drawingsLayerLocked}
        />
      )}
      {chartReady && hasChartData(bars) && instrumentId ? (
        <ChartF3OrderProjectionLayer
          series={mainSeriesRef.current}
          instrumentId={instrumentId}
          chartReady={chartReady}
        />
      ) : null}
      {showOperationalPlanLevels &&
      chartReady &&
      hasChartData(bars) &&
      instrumentId ? (
        <ChartOperationalPlanLevelsLayer
          series={mainSeriesRef.current}
          instrumentId={instrumentId}
          chartReady={chartReady}
        />
      ) : null}
      {showOperationalPlanLevels && chartReady && hasChartData(bars) ? (
        <>
          <ChartFocusToggle className="absolute bottom-2 left-2 z-20" />
          <ChartPlanContextStrip />
        </>
      ) : null}
      {showOperationalPlanLevels &&
      decisionSurfacePlacement === "chart" &&
      chartReady &&
      hasChartData(bars) &&
      instrumentId &&
      symbol ? (
        <ChartDecisionSurfaceHud instrumentId={instrumentId} symbol={symbol} />
      ) : null}
    </div>
  );
}
