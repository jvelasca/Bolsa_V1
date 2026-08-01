import type { ChartDrawing, ChartDrawingPoint, ChartLineStyle } from './chart-drawings.js';
import { DEFAULT_CHART_DRAW_COLOR, DEFAULT_LINE_WIDTH } from './chart-drawings.js';
import { semanticIdForDrawingType } from './chart-drawing-taxonomy.js';

const DRAWING_TYPES = new Set<ChartDrawing['type']>([
  'line',
  'ray',
  'ext-line',
  'info-line',
  'trend-angle',
  'regression',
  'hline',
  'hray',
  'vline',
  'rectangle',
  'fibonacci',
  'fib-trend-ext',
  'fib-time-zone',
  'gann-fan',
  'gann-grid',
  'gann-square',
  'channel',
  'pitchfork',
  'text-label',
  'brush-stroke',
  'cross-marker',
  'dot-marker',
  'dot-halo-marker',
  'arrow-marker',
  'arrow-circle-marker',
]);

function isPoint(value: unknown): value is ChartDrawingPoint {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ChartDrawingPoint).time === 'string' &&
    typeof (value as ChartDrawingPoint).price === 'number'
  );
}

function parseLineStyle(raw: unknown): ChartLineStyle | undefined {
  if (raw === 'dashed' || raw === 'dotted' || raw === 'solid') return raw;
  return undefined;
}

function baseStyle(raw: Record<string, unknown>) {
  return {
    color: typeof raw.color === 'string' ? raw.color : DEFAULT_CHART_DRAW_COLOR,
    lineWidth: typeof raw.lineWidth === 'number' ? raw.lineWidth : DEFAULT_LINE_WIDTH,
    lineStyle: parseLineStyle(raw.lineStyle),
    locked: raw.locked === true ? true : undefined,
    visible: raw.visible === false ? false : undefined,
    text: typeof raw.text === 'string' ? raw.text : undefined,
    templateId: typeof raw.templateId === 'string' ? raw.templateId : undefined,
    semanticId: typeof raw.semanticId === 'string' ? raw.semanticId : undefined,
    alertOnCross: raw.alertOnCross === true ? true : undefined,
    linkedOrderId: typeof raw.linkedOrderId === 'string' ? raw.linkedOrderId : undefined,
  };
}

/** Valida y normaliza un dibujo persistido (workspace JSON). */
export function sanitizeChartDrawing(raw: unknown): ChartDrawing | null {
  if (!raw || typeof raw !== 'object') return null;
  const d = raw as Record<string, unknown>;
  if (typeof d.id !== 'string' || typeof d.type !== 'string') return null;
  if (!DRAWING_TYPES.has(d.type as ChartDrawing['type'])) return null;

  const type = d.type as ChartDrawing['type'];

  const style = {
    ...baseStyle(d),
    semanticId:
      typeof d.semanticId === 'string' ? d.semanticId : semanticIdForDrawingType(type),
  };

  switch (type) {
    case 'hline':
      return typeof d.price === 'number'
        ? { id: d.id, type: 'hline', price: d.price, ...style }
        : null;
    case 'vline':
      return typeof d.time === 'string' ? { id: d.id, type: 'vline', time: d.time, ...style } : null;
    case 'hray':
      return isPoint(d.point) ? { id: d.id, type: 'hray', point: d.point, ...style } : null;
    case 'cross-marker':
      return isPoint(d.point) ? { id: d.id, type: 'cross-marker', point: d.point, ...style } : null;
    case 'dot-marker':
      return isPoint(d.point) ? { id: d.id, type: 'dot-marker', point: d.point, ...style } : null;
    case 'dot-halo-marker':
      return isPoint(d.point)
        ? {
            id: d.id,
            type: 'dot-halo-marker',
            point: d.point,
            haloRadius: typeof d.haloRadius === 'number' ? d.haloRadius : undefined,
            ...style,
          }
        : null;
    case 'arrow-marker':
      if (!isPoint(d.point)) return null;
      if (d.direction !== 'up' && d.direction !== 'down' && d.direction !== 'left' && d.direction !== 'right') {
        return null;
      }
      return { id: d.id, type: 'arrow-marker', point: d.point, direction: d.direction, ...style };
    case 'arrow-circle-marker':
      if (!isPoint(d.point)) return null;
      if (d.direction !== 'up' && d.direction !== 'down' && d.direction !== 'left' && d.direction !== 'right') {
        return null;
      }
      return { id: d.id, type: 'arrow-circle-marker', point: d.point, direction: d.direction, ...style };
    case 'rectangle':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return {
        id: d.id,
        type: 'rectangle',
        p1: d.p1,
        p2: d.p2,
        fillOpacity: typeof d.fillOpacity === 'number' ? d.fillOpacity : 0.12,
        ...style,
      };
    case 'channel':
      if (!isPoint(d.p1) || !isPoint(d.p2) || !isPoint(d.p3)) return null;
      return {
        id: d.id,
        type: 'channel',
        p1: d.p1,
        p2: d.p2,
        p3: d.p3,
        fillOpacity: typeof d.fillOpacity === 'number' ? d.fillOpacity : 0.12,
        ...style,
      };
    case 'pitchfork':
      if (!isPoint(d.p1) || !isPoint(d.p2) || !isPoint(d.p3)) return null;
      return { id: d.id, type: 'pitchfork', p1: d.p1, p2: d.p2, p3: d.p3, ...style };
    case 'text-label':
      if (!isPoint(d.point)) return null;
      return {
        id: d.id,
        type: 'text-label',
        point: d.point,
        label: typeof d.label === 'string' ? d.label : 'Texto',
        fontSize: typeof d.fontSize === 'number' ? d.fontSize : undefined,
        ...style,
      };
    case 'brush-stroke':
      if (!Array.isArray(d.points) || d.points.length < 2) return null;
      if (!d.points.every(isPoint)) return null;
      return {
        id: d.id,
        type: 'brush-stroke',
        points: d.points,
        strokeOpacity: typeof d.strokeOpacity === 'number' ? d.strokeOpacity : undefined,
        ...style,
      };
    case 'info-line':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return {
        id: d.id,
        type: 'info-line',
        p1: d.p1,
        p2: d.p2,
        label: typeof d.label === 'string' ? d.label : '',
        ...style,
      };
    case 'line':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'line', p1: d.p1, p2: d.p2, ...style };
    case 'ray':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'ray', p1: d.p1, p2: d.p2, ...style };
    case 'ext-line':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'ext-line', p1: d.p1, p2: d.p2, ...style };
    case 'trend-angle':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'trend-angle', p1: d.p1, p2: d.p2, ...style };
    case 'regression':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'regression', p1: d.p1, p2: d.p2, ...style };
    case 'fibonacci':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'fibonacci', p1: d.p1, p2: d.p2, ...style };
    case 'gann-fan':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'gann-fan', p1: d.p1, p2: d.p2, ...style };
    case 'fib-trend-ext':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'fib-trend-ext', p1: d.p1, p2: d.p2, ...style };
    case 'fib-time-zone':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return { id: d.id, type: 'fib-time-zone', p1: d.p1, p2: d.p2, ...style };
    case 'gann-grid':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return {
        id: d.id,
        type: 'gann-grid',
        p1: d.p1,
        p2: d.p2,
        fillOpacity: typeof d.fillOpacity === 'number' ? d.fillOpacity : 0.08,
        ...style,
      };
    case 'gann-square':
      if (!isPoint(d.p1) || !isPoint(d.p2)) return null;
      return {
        id: d.id,
        type: 'gann-square',
        p1: d.p1,
        p2: d.p2,
        fillOpacity: typeof d.fillOpacity === 'number' ? d.fillOpacity : 0.08,
        ...style,
      };
    default:
      return null;
  }
}

export function sanitizeChartDrawings(raw: unknown): ChartDrawing[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(sanitizeChartDrawing).filter((d): d is ChartDrawing => d !== null);
}
