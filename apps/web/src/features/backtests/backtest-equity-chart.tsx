import { useEffect, useRef, useState } from 'react';
import {
  AreaSeries,
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import type { BacktestEquityPointDto, BacktestTradeDto } from '@bolsa/shared';
import { barTimeToChartTime } from '@/features/charts/chart-utils';
import { observeStableSize } from '@/features/charts/chart-stable-resize';
import {
  marginsForZoom,
  PRICE_SCALE_MIN_WIDTH_PX,
  stepScaleZoom,
} from '@/features/charts/chart-scale-utils';
import {
  attachChartScaleDrag,
  attachChartScaleInteraction,
  type ChartScaleZoomHandlers,
} from '@/features/charts/chart-scale-wheel';
import { cn } from '@/lib/utils';

interface BacktestEquityChartProps {
  points: BacktestEquityPointDto[];
  trades?: BacktestTradeDto[];
  initialCash: number;
  /** Highlight / crosshair on this timestamp (trade ↔ chart sync). */
  focusTimestamp?: string | null;
  /** Movie sync: only draw equity up to this bar (inclusive). */
  untilTimestamp?: string | null;
  /** Fixed px height, or fill the parent (ResizeObserver). */
  height?: number | 'fill';
  className?: string;
}

function chartTimeKey(time: Time): string {
  return typeof time === 'object' ? `${time.year}-${time.month}-${time.day}` : String(time);
}

/** lightweight-charts requires strictly ascending unique times. */
function toOrderedLineData(
  points: BacktestEquityPointDto[],
): Array<{ time: Time; value: number; timestamp: string }> {
  const byTime = new Map<string, { time: Time; value: number; timestamp: string }>();
  for (const point of points) {
    const time = barTimeToChartTime(point.timestamp) as Time;
    byTime.set(chartTimeKey(time), { time, value: point.equity, timestamp: point.timestamp });
  }
  return [...byTime.values()].sort((a, b) => {
    const ka = chartTimeKey(a.time);
    const kb = chartTimeKey(b.time);
    if (ka === kb) return 0;
    if (typeof a.time === 'number' && typeof b.time === 'number') return a.time - b.time;
    return ka < kb ? -1 : 1;
  });
}

/** Drawdown underwater % desde peak (≤ 0). */
export function toUnderwaterDrawdownData(
  ordered: Array<{ time: Time; value: number }>,
  initialCash: number,
): Array<{ time: Time; value: number }> {
  let peak = initialCash;
  const out: Array<{ time: Time; value: number }> = [];
  for (const point of ordered) {
    peak = Math.max(peak, point.value);
    const ddPct = peak > 0 ? ((point.value - peak) / peak) * 100 : 0;
    out.push({ time: point.time, value: ddPct });
  }
  return out;
}

export function BacktestEquityChart({
  points,
  trades = [],
  initialCash,
  focusTimestamp = null,
  untilTimestamp = null,
  height = 220,
  className,
}: BacktestEquityChartProps) {
  const fillParent = height === 'fill';
  const shellRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const baselineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ddRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [measuredHeight, setMeasuredHeight] = useState(200);
  const chartHeight = fillParent ? measuredHeight : height;
  const scaleZoomRef = useRef(1);
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
  };

  useEffect(() => {
    if (!fillParent) return undefined;
    const shell = shellRef.current;
    if (!shell) return undefined;
    const apply = () => {
      const next = Math.max(120, Math.floor(shell.clientHeight));
      setMeasuredHeight((prev) => (Math.abs(prev - next) < 2 ? prev : next));
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(shell);
    return () => ro.disconnect();
  }, [fillParent]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || points.length === 0) return undefined;

    const chart = createChart(container, {
      width: Math.max(1, container.clientWidth),
      height: Math.max(120, chartHeight),
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.12)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.12)' },
      },
      rightPriceScale: {
        borderVisible: false,
        minimumWidth: PRICE_SCALE_MIN_WIDTH_PX,
        scaleMargins: marginsForZoom(scaleZoomRef.current),
      },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { mode: CrosshairMode.Magnet },
      handleScroll: false,
      handleScale: {
        mouseWheel: false,
        pinch: false,
        axisPressedMouseMove: { time: false, price: false },
        axisDoubleClickReset: { time: true, price: true },
      },
    });

    const line = chart.addSeries(LineSeries, {
      color: '#38bdf8',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    const baseline = chart.addSeries(LineSeries, {
      color: 'rgba(148, 163, 184, 0.45)',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const dd = chart.addSeries(AreaSeries, {
      topColor: 'rgba(239, 68, 68, 0.28)',
      bottomColor: 'rgba(239, 68, 68, 0.02)',
      lineColor: '#f87171',
      lineWidth: 1,
      priceScaleId: 'dd',
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    });
    chart.priceScale('right').applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.32 },
    });
    chart.priceScale('dd').applyOptions({
      scaleMargins: { top: 0.72, bottom: 0.02 },
      borderVisible: false,
    });

    chartRef.current = chart;
    lineRef.current = line;
    baselineRef.current = baseline;
    ddRef.current = dd;

    const cancelWheel = attachChartScaleInteraction({
      hitTarget: container,
      captureTarget: container,
      handlers: scaleHandlersRef,
    });
    const cancelDrag = attachChartScaleDrag({
      hitTarget: container,
      captureTarget: container,
      handlers: scaleHandlersRef,
    });

    return () => {
      cancelWheel();
      cancelDrag();
      chart.remove();
      chartRef.current = null;
      lineRef.current = null;
      baselineRef.current = null;
      ddRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- remount on data identity only
  }, [points.length]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.applyOptions({ height: Math.max(120, chartHeight) });
  }, [chartHeight]);

  useEffect(() => {
    const chart = chartRef.current;
    const line = lineRef.current;
    const baseline = baselineRef.current;
    const dd = ddRef.current;
    if (!chart || !line || !baseline || !dd || points.length === 0) return;

    const visiblePoints =
      untilTimestamp == null
        ? points
        : points.filter((point) => point.timestamp <= untilTimestamp);
    if (visiblePoints.length === 0) {
      line.setData([]);
      baseline.setData([]);
      dd.setData([]);
      return;
    }

    const lineData = toOrderedLineData(visiblePoints);
    line.setData(lineData.map(({ time, value }) => ({ time, value })));
    dd.setData(toUnderwaterDrawdownData(lineData, initialCash));

    const firstTime = lineData[0]?.time;
    const lastTime = lineData[lineData.length - 1]?.time;
    // Same timestamp twice crashes LWC ("data must be asc ordered by time").
    if (firstTime != null && lastTime != null && chartTimeKey(firstTime) !== chartTimeKey(lastTime)) {
      baseline.setData([
        { time: firstTime, value: initialCash },
        { time: lastTime, value: initialCash },
      ]);
    } else if (firstTime != null) {
      baseline.setData([{ time: firstTime, value: initialCash }]);
    } else {
      baseline.setData([]);
    }

    const tradeByTime = new Map(trades.map((trade) => [trade.timestamp, trade]));
    const markers: SeriesMarker<Time>[] = [];
    const markerTimes = new Set<string>();
    for (const point of lineData) {
      const trade = tradeByTime.get(point.timestamp);
      if (!trade) continue;
      const key = chartTimeKey(point.time);
      if (markerTimes.has(key)) continue;
      markerTimes.add(key);
      const focused = focusTimestamp === point.timestamp;
      markers.push({
        time: point.time,
        position: trade.type === 'buy' ? 'belowBar' : 'aboveBar',
        color: focused ? '#fbbf24' : trade.type === 'buy' ? '#22c55e' : '#ef4444',
        shape: trade.type === 'buy' ? 'arrowUp' : 'arrowDown',
        text: focused ? (trade.type === 'buy' ? 'B★' : 'S★') : trade.type === 'buy' ? 'B' : 'S',
      });
    }
    createSeriesMarkers(line, markers);

    chart.timeScale().setVisibleLogicalRange({
      from: -0.5,
      to: Math.max(lineData.length - 0.5, 0.5),
    });

    if (focusTimestamp) {
      const focusedPoint =
        lineData.find((point) => point.timestamp === focusTimestamp) ??
        [...lineData].reverse().find((point) => point.timestamp <= focusTimestamp);
      if (focusedPoint) {
        chart.setCrosshairPosition(focusedPoint.value, focusedPoint.time, line);
      }
    } else {
      chart.clearCrosshairPosition();
    }
  }, [focusTimestamp, initialCash, points, trades, untilTimestamp]);

  useEffect(() => {
    const container = containerRef.current;
    const chart = chartRef.current;
    if (!container || !chart) return undefined;
    return observeStableSize(container, (width, nextHeight) => {
      chart.applyOptions({
        width: Math.max(1, width),
        height: Math.max(120, nextHeight),
      });
    });
  }, [points.length]);

  if (points.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Curva de patrimonio no disponible (run anterior a BT-4). Ejecuta una simulación nueva.
      </p>
    );
  }

  const surface = (
    <div
      ref={containerRef}
      className={cn(
        'w-full overflow-hidden rounded-lg border border-border bg-card/40',
        fillParent && 'h-full min-h-0',
        className,
      )}
      style={fillParent ? undefined : { height }}
      aria-label="Curva de patrimonio del backtest"
      title="Escala derecha: rueda con botón pulsado o arrastre para zoom vertical (como en indicadores)"
    />
  );

  if (fillParent) {
    return (
      <div ref={shellRef} className="h-full min-h-0 w-full">
        {surface}
      </div>
    );
  }

  return surface;
}
