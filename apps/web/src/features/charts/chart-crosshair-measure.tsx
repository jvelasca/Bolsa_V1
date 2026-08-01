import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import type { IChartApi, Time } from 'lightweight-charts';
import type { OhlcvBarDto } from '@bolsa/shared';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { horzTimeToString, type ChartPriceSeries } from '@/features/charts/chart-drawing-utils';

interface ChartCrosshairMeasureProps {
  chart: IChartApi | null;
  series: ChartPriceSeries | null;
  container: HTMLDivElement | null;
  height: number;
  bars: OhlcvBarDto[];
  active: boolean;
}

type MeasurePoint = { x: number; y: number; time: string; price: number };

function parseBarTime(time: string): number {
  if (time.length === 10) return new Date(`${time}T12:00:00`).getTime();
  return new Date(time).getTime();
}

function countBarsBetween(bars: OhlcvBarDto[], t1: string, t2: string): number {
  const lo = Math.min(parseBarTime(t1), parseBarTime(t2));
  const hi = Math.max(parseBarTime(t1), parseBarTime(t2));
  return bars.filter((bar) => {
    const t = parseBarTime(bar.timestamp);
    return t >= lo && t <= hi;
  }).length;
}

function formatDuration(ms: number): string {
  const minutes = Math.round(ms / 60_000);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h`;
  const days = Math.round(hours / 24);
  return `${days} d`;
}

function estimateVisibleBarCount(chart: IChartApi, bars: OhlcvBarDto[]): number {
  const range = chart.timeScale().getVisibleLogicalRange();
  if (!range) return bars.length;
  return Math.max(1, Math.round(range.to - range.from));
}

function axisLabel(
  x: number,
  y: number,
  lines: string[],
  align: 'left' | 'center' | 'right',
): React.ReactNode {
  const lineHeight = 12;
  const padding = 6;
  const maxLen = Math.max(...lines.map((l) => l.length));
  const boxW = Math.min(180, maxLen * 6.4 + padding * 2);
  const boxH = lines.length * lineHeight + padding * 2;
  const tx =
    align === 'left' ? x + 8 : align === 'right' ? x - boxW - 8 : x - boxW / 2;
  const ty = y - boxH / 2;

  return (
    <foreignObject x={tx} y={ty} width={boxW} height={boxH} className="overflow-visible">
      <div
        className="box-border flex h-full w-full flex-col justify-center rounded px-1.5 py-1 text-[10px] font-medium leading-[12px] shadow-md"
        style={{
          backgroundColor: 'hsl(var(--popover))',
          color: 'hsl(var(--popover-foreground))',
          border: '1px solid hsl(var(--border))',
        }}
      >
        {lines.map((line) => (
          <div key={line} className="whitespace-nowrap">
            {line}
          </div>
        ))}
      </div>
    </foreignObject>
  );
}

export function ChartCrosshairMeasure({
  chart,
  series,
  container,
  height,
  bars,
  active,
}: ChartCrosshairMeasureProps) {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const [anchor, setAnchor] = useState<MeasurePoint | null>(null);
  const [cursor, setCursor] = useState<MeasurePoint | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const measuringRef = useRef(false);
  const layerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) {
      setAnchor(null);
      setCursor(null);
      setHover(null);
      measuringRef.current = false;
    }
  }, [active]);

  useEffect(() => {
    if (!chart || !active) return;
    const redraw = () => bump();
    chart.timeScale().subscribeVisibleLogicalRangeChange(redraw);
    chart.subscribeCrosshairMove(redraw);
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw);
      chart.unsubscribeCrosshairMove(redraw);
    };
  }, [active, chart]);

  useEffect(() => {
    if (!chart || !active) return;
    const handler = (param: { point?: { x: number; y: number } }) => {
      if (!param.point || measuringRef.current) return;
      setHover({ x: param.point.x, y: param.point.y });
    };
    chart.subscribeCrosshairMove(handler);
    return () => chart.unsubscribeCrosshairMove(handler);
  }, [active, chart]);

  const pointerToData = useCallback(
    (clientX: number, clientY: number): MeasurePoint | null => {
      if (!chart || !series) return null;
      const bounds =
        layerRef.current?.getBoundingClientRect() ?? container?.getBoundingClientRect();
      if (!bounds) return null;
      const x = clientX - bounds.left;
      const y = clientY - bounds.top;
      const price = series.coordinateToPrice(y);
      const time = chart.timeScale().coordinateToTime(x);
      if (price == null || time == null) return null;
      return { x, y, time: horzTimeToString(time as Time), price };
    },
    [chart, container, series],
  );

  if (!active || !container) return null;

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const point = pointerToData(event.clientX, event.clientY);
    if (!point) return;

    if (anchor && !measuringRef.current) {
      setAnchor(point);
      setCursor(point);
      measuringRef.current = true;
    } else {
      measuringRef.current = true;
      setAnchor(point);
      setCursor(point);
    }
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!measuringRef.current) return;
    const point = pointerToData(event.clientX, event.clientY);
    if (point) setCursor(point);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!measuringRef.current) return;
    measuringRef.current = false;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const width = container.clientWidth;
  const preview = !anchor && hover;
  const showMeasure = anchor && cursor;

  let measureGraphics: React.ReactNode = null;

  if (showMeasure) {
    const priceDelta = cursor.price - anchor.price;
    const pricePct = anchor.price !== 0 ? (priceDelta / anchor.price) * 100 : 0;
    const barCount = countBarsBetween(bars, anchor.time, cursor.time);
    const visibleBars = chart ? estimateVisibleBarCount(chart, bars) : bars.length;
    const timePct = visibleBars > 0 ? (barCount / visibleBars) * 100 : 0;
    const duration = formatDuration(
      Math.abs(parseBarTime(cursor.time) - parseBarTime(anchor.time)),
    );

    const left = Math.min(anchor.x, cursor.x);
    const right = Math.max(anchor.x, cursor.x);
    const top = Math.min(anchor.y, cursor.y);
    const bottom = Math.max(anchor.y, cursor.y);
    const boxW = Math.max(right - left, 1);
    const boxH = Math.max(bottom - top, 1);
    const midX = (left + right) / 2;
    const midY = (top + bottom) / 2;

    measureGraphics = (
      <>
        <rect
          x={left}
          y={top}
          width={boxW}
          height={boxH}
          fill="rgba(20,184,166,0.08)"
          stroke="#14b8a6"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        <line
          x1={anchor.x}
          y1={anchor.y}
          x2={cursor.x}
          y2={cursor.y}
          stroke="#14b8a6"
          strokeWidth={1.5}
          strokeOpacity={0.9}
        />
        {axisLabel(
          midX,
          Math.max(top - 4, 28),
          [
            `H · ${barCount} velas · ${duration}`,
            `Δt ${timePct.toFixed(1)}% del rango visible`,
          ],
          'center',
        )}
        {axisLabel(
          Math.min(right + 4, width - 8),
          midY,
          [`V · Δ ${formatPrice(priceDelta)}`, `Δ ${formatPct(pricePct)}`],
          'right',
        )}
      </>
    );
  }

  return (
    <div
      ref={layerRef}
      className="absolute inset-0 z-[11] cursor-crosshair"
      style={{ height, pointerEvents: 'auto' }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <svg className="pointer-events-none h-full w-full" width={width} height={height}>
        {preview && (
          <g stroke="#14b8a6" strokeWidth={1} strokeDasharray="5 4" strokeOpacity={0.75}>
            <line x1={hover.x} y1={0} x2={hover.x} y2={height} />
            <line x1={0} y1={hover.y} x2={width} y2={hover.y} />
          </g>
        )}
        {anchor && (
          <g stroke="#14b8a6" strokeWidth={1} strokeOpacity={0.45}>
            <line x1={anchor.x} y1={0} x2={anchor.x} y2={height} />
            <line x1={0} y1={anchor.y} x2={width} y2={anchor.y} />
          </g>
        )}
        {showMeasure && cursor && (
          <g stroke="#14b8a6" strokeWidth={1} strokeDasharray="4 3" strokeOpacity={0.55}>
            <line x1={cursor.x} y1={0} x2={cursor.x} y2={height} />
            <line x1={0} y1={cursor.y} x2={width} y2={cursor.y} />
          </g>
        )}
        {measureGraphics}
      </svg>
    </div>
  );
}
