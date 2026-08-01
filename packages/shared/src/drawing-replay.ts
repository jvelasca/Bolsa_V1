import type { ChartDrawing, ChartDrawingPoint } from './chart-drawings.js';
import { isDrawingVisible } from './chart-drawings.js';
import type { OhlcvBarDto } from './types.js';
import type { DrawingReplayMarkerDto } from './drawing-replay-api.js';

function parseBarTimeMs(timestamp: string): number {
  const normalized = timestamp.includes('T') ? timestamp : `${timestamp}T00:00:00.000Z`;
  return Date.parse(normalized);
}

type TwoPointDrawing = ChartDrawing & { p1: ChartDrawingPoint; p2: ChartDrawingPoint };

function isTwoPointDrawing(drawing: ChartDrawing): drawing is TwoPointDrawing {
  return (
    drawing.type === 'line' ||
    drawing.type === 'ray' ||
    drawing.type === 'ext-line' ||
    drawing.type === 'info-line' ||
    drawing.type === 'trend-angle' ||
    drawing.type === 'regression'
  );
}

/** Tipos con nivel evaluable en replay histórico (subset H0). */
export function drawingSupportsReplay(drawing: ChartDrawing): boolean {
  if (!isDrawingVisible(drawing)) return false;
  return drawing.type === 'hline' || drawing.type === 'hray' || isTwoPointDrawing(drawing);
}

function interpolatePrice(p1: ChartDrawingPoint, p2: ChartDrawingPoint, barTime: string): number {
  const t1 = parseBarTimeMs(p1.time);
  const t2 = parseBarTimeMs(p2.time);
  const t = parseBarTimeMs(barTime);
  if (t1 === t2) return p1.price;
  const ratio = (t - t1) / (t2 - t1);
  return p1.price + ratio * (p2.price - p1.price);
}

/** Precio del dibujo en el instante de la barra (null si fuera de dominio). */
export function drawingLevelAtBar(drawing: ChartDrawing, barTime: string): number | null {
  if (drawing.type === 'hline') return drawing.price;
  if (drawing.type === 'hray') return drawing.point.price;

  if (!isTwoPointDrawing(drawing)) return null;

  const t = parseBarTimeMs(barTime);
  const t1 = parseBarTimeMs(drawing.p1.time);
  const t2 = parseBarTimeMs(drawing.p2.time);
  const minT = Math.min(t1, t2);
  const maxT = Math.max(t1, t2);

  if (drawing.type === 'line' || drawing.type === 'info-line' || drawing.type === 'trend-angle' || drawing.type === 'regression') {
    if (t < minT || t > maxT) return null;
  } else if (drawing.type === 'ray') {
    if (t2 >= t1) {
      if (t < t1) return null;
    } else if (t > t1) {
      return null;
    }
  }

  return interpolatePrice(drawing.p1, drawing.p2, barTime);
}

export interface EvaluateDrawingReplayOptions {
  alertDrawingsOnly?: boolean;
}

/** Detecta cruces barra a barra (paridad con monitor live, pero con nivel temporal). */
export function evaluateDrawingReplay(
  bars: OhlcvBarDto[],
  drawings: ChartDrawing[],
  options: EvaluateDrawingReplayOptions = {},
): DrawingReplayMarkerDto[] {
  const alertOnly = options.alertDrawingsOnly !== false;
  const eligible = drawings.filter((drawing) => {
    if (!drawingSupportsReplay(drawing)) return false;
    if (alertOnly && drawing.alertOnCross !== true) return false;
    return true;
  });

  if (bars.length < 2 || eligible.length === 0) return [];

  const markers: DrawingReplayMarkerDto[] = [];
  const prevSide = new Map<string, 'above' | 'below'>();

  for (const drawing of eligible) {
    const level0 = drawingLevelAtBar(drawing, bars[0]!.timestamp);
    if (level0 == null) continue;
    prevSide.set(
      drawing.id,
      bars[0]!.close >= level0 ? 'above' : 'below',
    );
  }

  for (let index = 1; index < bars.length; index += 1) {
    const prevBar = bars[index - 1]!;
    const bar = bars[index]!;

    for (const drawing of eligible) {
      const levelPrev = drawingLevelAtBar(drawing, prevBar.timestamp);
      const levelCurr = drawingLevelAtBar(drawing, bar.timestamp);
      if (levelCurr == null) continue;

      const sideCurr: 'above' | 'below' = bar.close >= levelCurr ? 'above' : 'below';
      const stored = prevSide.get(drawing.id);

      if (stored == null) {
        prevSide.set(drawing.id, sideCurr);
        continue;
      }

      if (levelPrev == null) {
        prevSide.set(drawing.id, sideCurr);
        continue;
      }

      if (stored !== sideCurr) {
        markers.push({
          id: `${drawing.id}:${bar.timestamp}`,
          drawingId: drawing.id,
          timestamp: bar.timestamp,
          price: bar.close,
          level: levelCurr,
          direction: sideCurr === 'above' ? 'up' : 'down',
          drawingType: drawing.type,
          label: drawing.label ?? drawing.text,
        });
      }

      prevSide.set(drawing.id, sideCurr);
    }
  }

  return markers;
}
