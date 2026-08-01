import type { OhlcvBarDto } from '@bolsa/shared';
import type { ChartDrawingPoint } from '@bolsa/shared';

function parseBarTime(time: string): number {
  if (time.length === 10) return new Date(`${time}T12:00:00`).getTime();
  return new Date(time).getTime();
}

/** Regresión lineal OLS: y = slope * x + intercept (x = índice temporal). */
export function computeRegressionLine(
  bars: OhlcvBarDto[],
  p1: ChartDrawingPoint,
  p2: ChartDrawingPoint,
): { p1: ChartDrawingPoint; p2: ChartDrawingPoint } | null {
  if (bars.length < 2) return null;

  const t1 = parseBarTime(p1.time);
  const t2 = parseBarTime(p2.time);
  const lo = Math.min(t1, t2);
  const hi = Math.max(t1, t2);

  const subset = bars.filter((bar) => {
    const t = parseBarTime(bar.timestamp);
    return t >= lo && t <= hi;
  });

  if (subset.length < 2) return null;

  const n = subset.length;
  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumXX = 0;

  subset.forEach((bar, index) => {
    const x = index;
    const y = bar.close;
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumXX += x * x;
  });

  const denom = n * sumXX - sumX * sumX;
  if (Math.abs(denom) < 1e-12) return null;

  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;

  const priceAt = (index: number) => slope * index + intercept;

  return {
    p1: { time: subset[0]!.timestamp, price: priceAt(0) },
    p2: { time: subset[n - 1]!.timestamp, price: priceAt(n - 1) },
  };
}

export function defaultInfoLineLabel(p1: ChartDrawingPoint, p2: ChartDrawingPoint): string {
  const delta = p2.price - p1.price;
  const pct = p1.price !== 0 ? (delta / p1.price) * 100 : 0;
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(2)} (${sign}${pct.toFixed(2)}%)`;
}

export function lineAngleDegrees(p1: ChartDrawingPoint, p2: ChartDrawingPoint): number {
  const t1 = parseBarTime(p1.time);
  const t2 = parseBarTime(p2.time);
  const dx = t2 - t1 || 1;
  const dy = p2.price - p1.price;
  return (Math.atan2(dy, dx) * 180) / Math.PI;
}
