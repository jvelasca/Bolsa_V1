import type { Time } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';

import type { ChartMainPriceSeries } from '@/features/charts/chart-main-series';

export type ChartPriceSeries = ChartMainPriceSeries;
import {
  FIBONACCI_LEVELS,
  FIBONACCI_TREND_EXT_LEVELS,
  FIBONACCI_TIME_ZONE_MULTIPLIERS,
  GANN_GRID_DIVISIONS,
  type ChartDrawing,
  type ChartDrawingChannel,
  type ChartDrawingFibonacci,
  type ChartDrawingFibTrendExt,
  type ChartDrawingFibTimeZone,
  type ChartDrawingGannFan,
  type ChartDrawingGannGrid,
  type ChartDrawingGannSquare,
  type ChartDrawingPitchfork,
  type ChartDrawingBrushStroke,
  type ChartDrawingPoint,
  type ChartDrawingVertexPatch,
  type ChartLineStyle,
  type ChartMarkerDirection,
  isDrawingVisible,
} from '@bolsa/shared';
import { barTimeToChartTime } from '@/features/charts/chart-utils';

export function drawingPointToChartTime(time: string): Time {
  return barTimeToChartTime(time);
}

export function timeToPixelX(chart: IChartApi, time: string): number | null {
  const x = chart.timeScale().timeToCoordinate(drawingPointToChartTime(time));
  return x ?? null;
}

export function priceToPixelY(series: ChartPriceSeries, price: number): number | null {
  const y = series.priceToCoordinate(price);
  return y ?? null;
}

export function horzTimeToString(time: Time): string {
  if (typeof time === 'number') {
    const ms = time * 1000;
    const d = new Date(ms);
    if (d.getUTCHours() === 0 && d.getUTCMinutes() === 0 && d.getUTCSeconds() === 0) {
      return d.toISOString().slice(0, 10);
    }
    return d.toISOString().replace('+00:00', 'Z');
  }
  if (typeof time === 'string') return time;
  const { year, month, day } = time;
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function shiftPointInPixels(
  point: ChartDrawingPoint,
  dx: number,
  dy: number,
  chart: IChartApi,
  series: ChartPriceSeries,
  toPx: (point: ChartDrawingPoint) => { x: number; y: number } | null,
): ChartDrawingPoint | null {
  const pixel = toPx(point);
  if (!pixel) return null;
  const price = series.coordinateToPrice(pixel.y + dy);
  const time = chart.timeScale().coordinateToTime(pixel.x + dx);
  if (price == null || time == null) return null;
  return { time: horzTimeToString(time), price };
}

export function wholeDrawingPatch(
  drawing: ChartDrawing,
  anchor: ChartDrawingPoint,
  current: ChartDrawingPoint,
  chart: IChartApi,
  series: ChartPriceSeries,
  toPx: (point: ChartDrawingPoint) => { x: number; y: number } | null,
): ChartDrawingVertexPatch {
  const a = toPx(anchor);
  const c = toPx(current);
  if (!a || !c) return {};
  const dx = c.x - a.x;
  const dy = c.y - a.y;

  if (drawing.type === 'hline') {
    const shifted = shiftPointInPixels(
      { time: anchor.time, price: drawing.price },
      dx,
      dy,
      chart,
      series,
      toPx,
    );
    return shifted ? { price: shifted.price } : {};
  }
  if (drawing.type === 'vline') {
    const shifted = shiftPointInPixels(
      { time: drawing.time, price: anchor.price },
      dx,
      dy,
      chart,
      series,
      toPx,
    );
    return shifted ? { time: shifted.time } : {};
  }
  if (drawing.type === 'hray' || drawing.type === 'cross-marker' || drawing.type === 'dot-marker' || drawing.type === 'dot-halo-marker' || drawing.type === 'arrow-marker' || drawing.type === 'arrow-circle-marker' || drawing.type === 'text-label') {
    const shifted = shiftPointInPixels(drawing.point, dx, dy, chart, series, toPx);
    return shifted ? { point: shifted } : {};
  }
  if (drawing.type === 'brush-stroke') {
    const points = drawing.points
      .map((p) => shiftPointInPixels(p, dx, dy, chart, series, toPx))
      .filter((p): p is ChartDrawingPoint => p != null);
    return points.length === drawing.points.length ? { points } : {};
  }
  if ('p1' in drawing && 'p2' in drawing && drawing.p1 && drawing.p2) {
    const p1 = shiftPointInPixels(drawing.p1, dx, dy, chart, series, toPx);
    const p2 = shiftPointInPixels(drawing.p2, dx, dy, chart, series, toPx);
    const patch: ChartDrawingVertexPatch = {};
    if (p1) patch.p1 = p1;
    if (p2) patch.p2 = p2;
    if (drawing.type === 'channel' && drawing.p3) {
      const p3 = shiftPointInPixels(drawing.p3, dx, dy, chart, series, toPx);
      if (p3) patch.p3 = p3;
    }
    if (drawing.type === 'pitchfork' && drawing.p3) {
      const p3 = shiftPointInPixels(drawing.p3, dx, dy, chart, series, toPx);
      if (p3) patch.p3 = p3;
    }
    return patch;
  }
  return {};
}

export function normalizeRect(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
): { p1: ChartDrawingPoint; p2: ChartDrawingPoint } {
  const t1 = p1.time <= p2.time ? p1.time : p2.time;
  const t2 = p1.time <= p2.time ? p2.time : p1.time;
  const hi = Math.max(p1.price, p2.price);
  const lo = Math.min(p1.price, p2.price);
  return { p1: { time: t1, price: hi }, p2: { time: t2, price: lo } };
}

export function distanceToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

export function fibPriceAtLevel(p1: ChartDrawingPoint, p2: ChartDrawingPoint, level: number): number {
  const low = Math.min(p1.price, p2.price);
  const high = Math.max(p1.price, p2.price);
  return low + (high - low) * level;
}

export function fibTimeSpan(p1: ChartDrawingPoint, p2: ChartDrawingPoint) {
  const t1 = p1.time <= p2.time ? p1.time : p2.time;
  const t2 = p1.time <= p2.time ? p2.time : p1.time;
  return { t1, t2 };
}

export function channelParallelEnd(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  p3: ChartDrawingPoint,
): ChartDrawingPoint {
  return {
    time: p3.time,
    price: p3.price + (p2.price - p1.price),
  };
}

export function midpointChartPoint(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  chart: IChartApi,
  series: ChartPriceSeries,
): ChartDrawingPoint | null {
  const x1 = timeToPixelX(chart, p1.time);
  const y1 = priceToPixelY(series, p1.price);
  const x2 = timeToPixelX(chart, p2.time);
  const y2 = priceToPixelY(series, p2.price);
  if (x1 == null || y1 == null || x2 == null || y2 == null) return null;
  const price = series.coordinateToPrice((y1 + y2) / 2);
  const time = chart.timeScale().coordinateToTime((x1 + x2) / 2);
  if (price == null || time == null) return null;
  return { time: horzTimeToString(time), price };
}

export function parallelRayPixels(
  anchor: ChartDrawingPoint,
  origin: ChartDrawingPoint,
  directionEnd: ChartDrawingPoint,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  extendScale = 3000,
): { x1: number; y1: number; x2: number; y2: number } | null {
  const a = toPixel(anchor);
  const o = toPixel(origin);
  const d = toPixel(directionEnd);
  if (!a || !o || !d) return null;
  const dx = d.x - o.x;
  const dy = d.y - o.y;
  const len = Math.hypot(dx, dy) || 1;
  const scale = extendScale / len;
  return { x1: a.x, y1: a.y, x2: a.x + dx * scale, y2: a.y + dy * scale };
}

export function pitchforkRays(
  drawing: ChartDrawingPitchfork,
  chart: IChartApi,
  series: ChartPriceSeries,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  const mid = midpointChartPoint(drawing.p1, drawing.p2, chart, series);
  if (!mid) return [];
  const median = parallelRayPixels(mid, mid, drawing.p3, toPixel);
  const upper = parallelRayPixels(drawing.p1, mid, drawing.p3, toPixel);
  const lower = parallelRayPixels(drawing.p2, mid, drawing.p3, toPixel);
  return [median, upper, lower].filter((seg): seg is NonNullable<typeof seg> => seg != null);
}

/** Ratios Gann clásicos (precio × tiempo) respecto a la línea 1×1. */
export const GANN_FAN_RATIOS: ReadonlyArray<readonly [priceMult: number, timeMult: number]> = [
  [1, 8],
  [1, 4],
  [1, 3],
  [1, 2],
  [1, 1],
  [2, 1],
  [3, 1],
  [4, 1],
  [8, 1],
];

export function gannFanRays(
  drawing: ChartDrawingGannFan,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  extendScale = 3000,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  const anchor = toPixel(drawing.p1);
  const direction = toPixel(drawing.p2);
  if (!anchor || !direction) return [];

  const dx = direction.x - anchor.x;
  const dy = direction.y - anchor.y;
  if (Math.hypot(dx, dy) < 0.5) return [];

  return GANN_FAN_RATIOS.map(([priceMult, timeMult]) => {
    const rx = dx * timeMult;
    const ry = dy * priceMult;
    const len = Math.hypot(rx, ry) || 1;
    const scale = extendScale / len;
    return {
      x1: anchor.x,
      y1: anchor.y,
      x2: anchor.x + rx * scale,
      y2: anchor.y + ry * scale,
    };
  });
}

export function hitTestGannFan(
  drawing: ChartDrawingGannFan,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  return gannFanRays(drawing, toPixel).some((seg) =>
    distanceToSegment(px, py, seg.x1, seg.y1, seg.x2, seg.y2) <= threshold,
  );
}

export function strokeDasharray(style: ChartLineStyle): string | undefined {
  if (style === 'dashed') return '6 4';
  if (style === 'dotted') return '2 3';
  return undefined;
}

export function extendedLinePixels(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  containerWidth: number,
): { x1: number; y1: number; x2: number; y2: number } | null {
  const a = toPixel(p1);
  const b = toPixel(p2);
  if (!a || !b) return null;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const scale = (containerWidth * 2) / len;
  return {
    x1: a.x - dx * scale,
    y1: a.y - dy * scale,
    x2: a.x + dx * scale,
    y2: a.y + dy * scale,
  };
}

export function rayLinePixels(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  extendScale = 3000,
): { x1: number; y1: number; x2: number; y2: number } | null {
  const a = toPixel(p1);
  const b = toPixel(p2);
  if (!a || !b) return null;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const scale = extendScale / len;
  return { x1: a.x, y1: a.y, x2: a.x + dx * scale, y2: a.y + dy * scale };
}

export function drawingVertices(drawing: ChartDrawing): Array<'p1' | 'p2' | 'p3'> {
  if (drawing.type === 'channel' || drawing.type === 'pitchfork') return ['p1', 'p2', 'p3'];
  if (
    drawing.type === 'hline' ||
    drawing.type === 'hray' ||
    drawing.type === 'vline' ||
    drawing.type === 'cross-marker' ||
    drawing.type === 'dot-marker' ||
    drawing.type === 'dot-halo-marker' ||
    drawing.type === 'arrow-marker' ||
    drawing.type === 'arrow-circle-marker'
  ) {
    return [];
  }
  return ['p1', 'p2'];
}

export function markerDirectionFromDelta(dx: number, dy: number): ChartMarkerDirection {
  if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return 'up';
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? 'right' : 'left';
  return dy < 0 ? 'up' : 'down';
}

export function markerRotation(direction: ChartMarkerDirection): number {
  switch (direction) {
    case 'up':
      return 0;
    case 'right':
      return 90;
    case 'down':
      return 180;
    case 'left':
      return 270;
    default:
      return 0;
  }
}

function hitTestMarkerPoint(
  point: ChartDrawingPoint,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 10,
): boolean {
  const pixel = toPixel(point);
  if (!pixel) return false;
  return Math.hypot(px - pixel.x, py - pixel.y) <= threshold;
}

export function hitTestFibonacci(
  drawing: ChartDrawingFibonacci,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  return hitTestFibLevels(drawing.p1, drawing.p2, FIBONACCI_LEVELS, px, py, toPixel, threshold);
}

export function hitTestFibLevels(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  levels: readonly number[],
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  const a = toPixel(p1);
  const b = toPixel(p2);
  if (!a || !b) return false;
  const left = Math.min(a.x, b.x);
  const right = Math.max(a.x, b.x);

  for (const level of levels) {
    const price = fibPriceAtLevel(p1, p2, level);
    const y = toPixel({ time: p1.time, price })?.y;
    if (y == null) continue;
    if (px >= left - threshold && px <= right + threshold && Math.abs(py - y) <= threshold) {
      return true;
    }
  }
  return false;
}

export function hitTestFibTrendExt(
  drawing: ChartDrawingFibTrendExt,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  return hitTestFibLevels(
    drawing.p1,
    drawing.p2,
    FIBONACCI_TREND_EXT_LEVELS,
    px,
    py,
    toPixel,
    threshold,
  );
}

export function fibTimeZoneLineXs(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
): number[] {
  const a = toPixel(p1);
  const b = toPixel(p2);
  if (!a || !b) return [];
  const unit = b.x - a.x;
  return FIBONACCI_TIME_ZONE_MULTIPLIERS.map((mult) => a.x + unit * mult);
}

export function hitTestFibTimeZone(
  drawing: ChartDrawingFibTimeZone,
  px: number,
  _py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  return fibTimeZoneLineXs(drawing.p1, drawing.p2, toPixel).some((x) => Math.abs(px - x) <= threshold);
}

export function snapGannSquareP2(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  chart: IChartApi,
  series: ChartPriceSeries,
): ChartDrawingPoint {
  const x1 = timeToPixelX(chart, p1.time);
  const y1 = priceToPixelY(series, p1.price);
  const x2 = timeToPixelX(chart, p2.time);
  const y2 = priceToPixelY(series, p2.price);
  if (x1 == null || y1 == null || x2 == null || y2 == null) return p2;
  const size = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1)) || 1;
  const nx = x1 + Math.sign(x2 - x1 || 1) * size;
  const ny = y1 + Math.sign(y2 - y1 || 1) * size;
  const price = series.coordinateToPrice(ny);
  const time = chart.timeScale().coordinateToTime(nx);
  if (price == null || time == null) return p2;
  return { time: horzTimeToString(time), price };
}

export function gannSquarePixelBounds(
  drawing: ChartDrawingGannSquare,
  chart: IChartApi,
  series: ChartPriceSeries,
): { x: number; y: number; w: number; h: number } | null {
  const x1 = timeToPixelX(chart, drawing.p1.time);
  const y1 = priceToPixelY(series, drawing.p1.price);
  const x2 = timeToPixelX(chart, drawing.p2.time);
  const y2 = priceToPixelY(series, drawing.p2.price);
  if (x1 == null || y1 == null || x2 == null || y2 == null) return null;
  const size = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1)) || 1;
  const left = x2 >= x1 ? x1 : x1 - size;
  const top = y2 >= y1 ? y1 : y1 - size;
  return { x: left, y: top, w: size, h: size };
}

export function gannGridPixelBounds(
  drawing: Pick<ChartDrawingGannGrid, 'p1' | 'p2'>,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
): { left: number; top: number; right: number; bottom: number } | null {
  const a = toPixel(drawing.p1);
  const b = toPixel(drawing.p2);
  if (!a || !b) return null;
  return {
    left: Math.min(a.x, b.x),
    top: Math.min(a.y, b.y),
    right: Math.max(a.x, b.x),
    bottom: Math.max(a.y, b.y),
  };
}

function hitTestRectBounds(
  left: number,
  top: number,
  right: number,
  bottom: number,
  px: number,
  py: number,
  threshold: number,
): boolean {
  return (
    px >= left - threshold &&
    px <= right + threshold &&
    py >= top - threshold &&
    py <= bottom + threshold
  );
}

export function hitTestGannGrid(
  drawing: ChartDrawingGannGrid,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  const bounds = gannGridPixelBounds(drawing, toPixel);
  if (!bounds) return false;
  const { left, top, right, bottom } = bounds;
  if (hitTestRectBounds(left, top, right, bottom, px, py, threshold)) return true;
  for (let i = 1; i < GANN_GRID_DIVISIONS; i += 1) {
    const t = i / GANN_GRID_DIVISIONS;
    const x = left + (right - left) * t;
    const y = top + (bottom - top) * t;
    if (Math.abs(px - x) <= threshold && py >= top && py <= bottom) return true;
    if (Math.abs(py - y) <= threshold && px >= left && px <= right) return true;
  }
  return false;
}

export function hitTestGannSquare(
  drawing: ChartDrawingGannSquare,
  px: number,
  py: number,
  chart: IChartApi,
  series: ChartPriceSeries,
  threshold = 8,
): boolean {
  const bounds = gannSquarePixelBounds(drawing, chart, series);
  if (!bounds) return false;
  return hitTestRectBounds(
    bounds.x,
    bounds.y,
    bounds.x + bounds.w,
    bounds.y + bounds.h,
    px,
    py,
    threshold,
  );
}

export function hitTestChannel(
  drawing: ChartDrawingChannel,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  const a = toPixel(drawing.p1);
  const b = toPixel(drawing.p2);
  const c = toPixel(drawing.p3);
  if (!a || !b || !c) return false;
  const d = toPixel(channelParallelEnd(drawing.p1, drawing.p2, drawing.p3));
  if (!d) return false;
  if (
    distanceToSegment(px, py, a.x, a.y, b.x, b.y) <= threshold ||
    distanceToSegment(px, py, c.x, c.y, d.x, d.y) <= threshold
  ) {
    return true;
  }
  if (drawing.fillOpacity > 0) {
    const minX = Math.min(a.x, b.x, c.x, d.x);
    const maxX = Math.max(a.x, b.x, c.x, d.x);
    const minY = Math.min(a.y, b.y, c.y, d.y);
    const maxY = Math.max(a.y, b.y, c.y, d.y);
    return px >= minX && px <= maxX && py >= minY && py <= maxY;
  }
  return false;
}

export function hitTestPitchfork(
  drawing: ChartDrawingPitchfork,
  px: number,
  py: number,
  chart: IChartApi,
  series: ChartPriceSeries,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  return pitchforkRays(drawing, chart, series, toPixel).some((seg) =>
    distanceToSegment(px, py, seg.x1, seg.y1, seg.x2, seg.y2) <= threshold,
  );
}

export function hitTestBrushStroke(
  drawing: ChartDrawingBrushStroke,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
): boolean {
  const width = drawing.lineWidth ?? 1.5;
  const hitThreshold = Math.max(threshold, width / 2 + 2);
  for (let i = 1; i < drawing.points.length; i += 1) {
    const a = toPixel(drawing.points[i - 1]!);
    const b = toPixel(drawing.points[i]!);
    if (!a || !b) continue;
    if (distanceToSegment(px, py, a.x, a.y, b.x, b.y) <= hitThreshold) return true;
  }
  return false;
}

export function hitTestTextLabel(
  point: ChartDrawingPoint,
  label: string,
  fontSize: number,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 6,
): boolean {
  const anchor = toPixel(point);
  if (!anchor) return false;
  const width = Math.max(24, label.length * fontSize * 0.55);
  const height = fontSize + 4;
  return (
    px >= anchor.x - threshold &&
    px <= anchor.x + width + threshold &&
    py >= anchor.y - threshold &&
    py <= anchor.y + height + threshold
  );
}

function hitTestSegmentLine(
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold: number,
  mode: 'segment' | 'ray' | 'extended',
  containerWidth = 2000,
): boolean {
  let seg: { x1: number; y1: number; x2: number; y2: number } | null;
  if (mode === 'extended') {
    seg = extendedLinePixels(p1, p2, toPixel, containerWidth);
  } else if (mode === 'ray') {
    seg = rayLinePixels(p1, p2, toPixel);
  } else {
    const a = toPixel(p1);
    const b = toPixel(p2);
    seg = a && b ? { x1: a.x, y1: a.y, x2: b.x, y2: b.y } : null;
  }
  if (!seg) return false;
  return distanceToSegment(px, py, seg.x1, seg.y1, seg.x2, seg.y2) <= threshold;
}

export function hitTestDrawing(
  drawing: ChartDrawing,
  px: number,
  py: number,
  toPixel: (point: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 8,
  containerWidth = 2000,
  chart: IChartApi | null = null,
  series: ChartPriceSeries | null = null,
): boolean {
  if (
    drawing.type === 'cross-marker' ||
    drawing.type === 'dot-marker' ||
    drawing.type === 'dot-halo-marker' ||
    drawing.type === 'arrow-marker' ||
    drawing.type === 'arrow-circle-marker'
  ) {
    const radius =
      drawing.type === 'dot-halo-marker' ? (drawing.haloRadius ?? 14) : threshold;
    return hitTestMarkerPoint(drawing.point, px, py, toPixel, radius);
  }

  if (drawing.type === 'hline') {
    if (series) {
      const y = priceToPixelY(series, drawing.price);
      if (y != null) return Math.abs(py - y) <= threshold;
    }
    const y = toPixel({ time: '2000-01-01', price: drawing.price })?.y;
    if (y == null) return false;
    return Math.abs(py - y) <= threshold;
  }

  if (drawing.type === 'hray') {
    const anchor = toPixel(drawing.point);
    if (!anchor) return false;
    if (Math.abs(py - anchor.y) > threshold) return false;
    return px >= anchor.x - threshold;
  }

  if (drawing.type === 'vline') {
    if (chart) {
      const x = timeToPixelX(chart, drawing.time);
      if (x != null) return Math.abs(px - x) <= threshold;
    }
    const x = toPixel({ time: drawing.time, price: 0 })?.x;
    if (x == null) return false;
    return Math.abs(px - x) <= threshold;
  }

  if (
    drawing.type === 'line' ||
    drawing.type === 'info-line' ||
    drawing.type === 'trend-angle' ||
    drawing.type === 'regression'
  ) {
    const lineHit = Math.max(threshold, (drawing.lineWidth ?? 1.5) / 2 + 6);
    return hitTestSegmentLine(drawing.p1, drawing.p2, px, py, toPixel, lineHit, 'segment');
  }

  if (drawing.type === 'ext-line') {
    return hitTestSegmentLine(
      drawing.p1,
      drawing.p2,
      px,
      py,
      toPixel,
      threshold,
      'extended',
      containerWidth,
    );
  }

  if (drawing.type === 'ray') {
    return hitTestSegmentLine(drawing.p1, drawing.p2, px, py, toPixel, threshold, 'ray');
  }

  if (drawing.type === 'fibonacci') {
    return hitTestFibonacci(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'gann-fan') {
    return hitTestGannFan(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'fib-trend-ext') {
    return hitTestFibTrendExt(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'fib-time-zone') {
    return hitTestFibTimeZone(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'gann-grid') {
    return hitTestGannGrid(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'gann-square' && chart && series) {
    return hitTestGannSquare(drawing, px, py, chart, series, threshold);
  }

  if (drawing.type === 'channel') {
    return hitTestChannel(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'pitchfork' && chart && series) {
    return hitTestPitchfork(drawing, px, py, chart, series, toPixel, threshold);
  }

  if (drawing.type === 'brush-stroke') {
    return hitTestBrushStroke(drawing, px, py, toPixel, threshold);
  }

  if (drawing.type === 'text-label') {
    const content =
      drawing.label?.trim() || drawing.text?.trim() || 'Texto';
    return hitTestTextLabel(
      drawing.point,
      content,
      drawing.fontSize ?? 13,
      px,
      py,
      toPixel,
      threshold,
    );
  }

  if (drawing.type === 'rectangle') {
    const a = toPixel(drawing.p1);
    const b = toPixel(drawing.p2);
    if (!a || !b) return false;
    const left = Math.min(a.x, b.x);
    const right = Math.max(a.x, b.x);
    const top = Math.min(a.y, b.y);
    const bottom = Math.max(a.y, b.y);
    return px >= left - threshold && px <= right + threshold && py >= top - threshold && py <= bottom + threshold;
  }

  if (!('p1' in drawing) || !('p2' in drawing)) return false;
  const a = toPixel(drawing.p1);
  const b = toPixel(drawing.p2);
  if (!a || !b) return false;

  const left = Math.min(a.x, b.x);
  const right = Math.max(a.x, b.x);
  const top = Math.min(a.y, b.y);
  const bottom = Math.max(a.y, b.y);
  return px >= left - threshold && px <= right + threshold && py >= top - threshold && py <= bottom + threshold;
}

export function hitTestVertex(
  px: number,
  py: number,
  point: ChartDrawingPoint,
  toPixel: (p: ChartDrawingPoint) => { x: number; y: number } | null,
  threshold = 10,
): boolean {
  const pixel = toPixel(point);
  if (!pixel) return false;
  return Math.hypot(px - pixel.x, py - pixel.y) <= threshold;
}

export type DrawingVertexHit =
  | { kind: 'vertex'; drawingId: string; key: 'p1' | 'p2' | 'p3' }
  | { kind: 'hline'; drawingId: string }
  | { kind: 'vline'; drawingId: string };

function vertexPointForKey(
  drawing: ChartDrawing,
  key: 'p1' | 'p2' | 'p3',
): ChartDrawingPoint | undefined {
  if (key === 'p3') {
    return drawing.type === 'channel' || drawing.type === 'pitchfork' ? drawing.p3 : undefined;
  }
  if (!('p1' in drawing) || !('p2' in drawing)) return undefined;
  return drawing[key];
}

/** Prioriza el dibujo ya seleccionado; detecta anclajes antes que el cuerpo. */
export function findDrawingVertexHit(
  drawings: ChartDrawing[],
  px: number,
  py: number,
  toPixel: (p: ChartDrawingPoint) => { x: number; y: number } | null,
  options: {
    threshold?: number;
    chart: import('lightweight-charts').IChartApi | null;
    series: ChartPriceSeries | null;
    containerWidth: number;
    priorityDrawingId?: string | null;
  },
): DrawingVertexHit | null {
  const threshold = options.threshold ?? 16;

  const testDrawing = (drawing: ChartDrawing): DrawingVertexHit | null => {
    if (!isDrawingVisible(drawing)) return null;

    if (drawing.type === 'hline' && options.series) {
      const y = priceToPixelY(options.series, drawing.price);
      if (y != null && Math.abs(py - y) <= threshold) {
        return { kind: 'hline', drawingId: drawing.id };
      }
    }

    if (drawing.type === 'vline' && options.chart) {
      const x = timeToPixelX(options.chart, drawing.time);
      if (x != null && Math.abs(px - x) <= threshold) {
        return { kind: 'vline', drawingId: drawing.id };
      }
    }

    for (const key of drawingVertices(drawing)) {
      const point = vertexPointForKey(drawing, key);
      if (point && hitTestVertex(px, py, point, toPixel, threshold)) {
        return { kind: 'vertex', drawingId: drawing.id, key };
      }
    }

    return null;
  };

  if (options.priorityDrawingId) {
    const preferred = drawings.find((drawing) => drawing.id === options.priorityDrawingId);
    if (preferred) {
      const hit = testDrawing(preferred);
      if (hit) return hit;
    }
  }

  for (let i = drawings.length - 1; i >= 0; i -= 1) {
    const hit = testDrawing(drawings[i]!);
    if (hit) return hit;
  }

  return null;
}
