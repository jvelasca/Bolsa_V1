import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts';
import type { IndicatorLinePoint } from '@/features/charts/indicator-compute';

const HIT_THRESHOLD_PX = 10;

function timeToSortable(time: Time): number {
  if (typeof time === 'number') return time;
  if (typeof time === 'string') return Date.parse(time) / 1000;
  const { year, month, day } = time;
  return Date.UTC(year, month - 1, day) / 1000;
}

function interpolateValueAtTime(points: IndicatorLinePoint[], target: Time): number | null {
  if (points.length === 0) return null;
  const t = timeToSortable(target);
  const first = timeToSortable(points[0]!.time);
  const last = timeToSortable(points[points.length - 1]!.time);
  if (t < first || t > last) return null;

  for (let i = 0; i < points.length - 1; i += 1) {
    const t0 = timeToSortable(points[i]!.time);
    const t1 = timeToSortable(points[i + 1]!.time);
    if (t >= t0 && t <= t1) {
      if (t1 === t0) return points[i]!.value;
      const ratio = (t - t0) / (t1 - t0);
      return points[i]!.value + ratio * (points[i + 1]!.value - points[i]!.value);
    }
  }
  return points[points.length - 1]!.value;
}

export interface OverlaySeriesHitEntry {
  series: ISeriesApi<'Line'>;
  points: IndicatorLinePoint[];
}

/** Devuelve el `instanceId` del overlay más cercano al clic (píxeles), o null. */
export function findOverlayInstanceAtPixel(
  chart: IChartApi,
  container: HTMLElement,
  clientX: number,
  clientY: number,
  seriesMap: Map<string, OverlaySeriesHitEntry>,
): string | null {
  const rect = container.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const time = chart.timeScale().coordinateToTime(x);
  if (time == null) return null;

  let best: { instanceId: string; dist: number } | null = null;

  for (const [seriesKey, { series, points }] of seriesMap) {
    const value = interpolateValueAtTime(points, time);
    if (value == null) continue;
    const lineY = series.priceToCoordinate(value);
    if (lineY == null) continue;
    const dist = Math.abs(y - lineY);
    if (dist > HIT_THRESHOLD_PX) continue;
    const instanceId = seriesKey.split(':')[0]!;
    if (!best || dist < best.dist) {
      best = { instanceId, dist };
    }
  }

  return best?.instanceId ?? null;
}
