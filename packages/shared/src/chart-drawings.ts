export type ChartDrawTool =

  | 'select'

  | 'crosshair'

  | 'cross'

  | 'dot'

  | 'dot-halo'

  | 'arrow'

  | 'arrow-circle'

  | 'line'

  | 'ray'

  | 'info-line'

  | 'ext-line'

  | 'trend-angle'

  | 'hline'

  | 'hray'

  | 'vline'

  | 'regression'

  | 'rectangle'

  | 'fibonacci'

  | 'fib-trend-ext'

  | 'fib-time-zone'

  | 'gann-fan'

  | 'gann-grid'

  | 'gann-square'

  | 'channel'

  | 'text'

  | 'pitchfork'

  | 'brush'

  | 'highlighter'

  | 'arrow-up'

  | 'arrow-down';



export type ChartMarkerDirection = 'up' | 'down' | 'left' | 'right';



export type ChartLineStyle = 'solid' | 'dashed' | 'dotted';



export interface ChartDrawingPoint {

  time: string;

  price: number;

}



export interface ChartDrawingStyle {

  color: string;

  lineWidth?: number;

  lineStyle?: ChartLineStyle;

  locked?: boolean;

  visible?: boolean;

  /** Etiqueta visible (línea info y similares). */

  label?: string;

  /** ID técnico estable (`cursor.dot`, `line.trend`…). Ver chart-drawing-taxonomy. */
  semanticId?: string;

  /** Nota o texto auxiliar del objeto gráfico. */
  text?: string;

  /** Plantilla de estilos aplicada. */
  templateId?: string;

  /** Dispara alerta toast cuando el precio cruza la línea (fase P4e). */

  alertOnCross?: boolean;

  /** Orden pendiente vinculada a este objeto gráfico (gestión de órdenes). */
  linkedOrderId?: string;

}



export interface ChartDrawingLine extends ChartDrawingStyle {

  id: string;

  type: 'line';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingRay extends ChartDrawingStyle {

  id: string;

  type: 'ray';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingExtLine extends ChartDrawingStyle {

  id: string;

  type: 'ext-line';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingInfoLine extends ChartDrawingStyle {

  id: string;

  type: 'info-line';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  label: string;

}



export interface ChartDrawingTrendAngle extends ChartDrawingStyle {

  id: string;

  type: 'trend-angle';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingRegression extends ChartDrawingStyle {

  id: string;

  type: 'regression';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingHLine extends ChartDrawingStyle {

  id: string;

  type: 'hline';

  price: number;

}



export interface ChartDrawingHRay extends ChartDrawingStyle {

  id: string;

  type: 'hray';

  point: ChartDrawingPoint;

}



export interface ChartDrawingVLine extends ChartDrawingStyle {

  id: string;

  type: 'vline';

  time: string;

}



export interface ChartDrawingRectangle extends ChartDrawingStyle {

  id: string;

  type: 'rectangle';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  fillOpacity: number;

}



export interface ChartDrawingFibonacci extends ChartDrawingStyle {

  id: string;

  type: 'fibonacci';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingGannFan extends ChartDrawingStyle {

  id: string;

  type: 'gann-fan';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingFibTrendExt extends ChartDrawingStyle {

  id: string;

  type: 'fib-trend-ext';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingFibTimeZone extends ChartDrawingStyle {

  id: string;

  type: 'fib-time-zone';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

}



export interface ChartDrawingGannGrid extends ChartDrawingStyle {

  id: string;

  type: 'gann-grid';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  fillOpacity?: number;

}



export interface ChartDrawingGannSquare extends ChartDrawingStyle {

  id: string;

  type: 'gann-square';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  fillOpacity?: number;

}



export interface ChartDrawingChannel extends ChartDrawingStyle {

  id: string;

  type: 'channel';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  p3: ChartDrawingPoint;

  fillOpacity: number;

}



export interface ChartDrawingTextLabel extends ChartDrawingStyle {

  id: string;

  type: 'text-label';

  point: ChartDrawingPoint;

  label: string;

  fontSize?: number;

}



export interface ChartDrawingPitchfork extends ChartDrawingStyle {

  id: string;

  type: 'pitchfork';

  p1: ChartDrawingPoint;

  p2: ChartDrawingPoint;

  p3: ChartDrawingPoint;

}



export interface ChartDrawingBrushStroke extends ChartDrawingStyle {

  id: string;

  type: 'brush-stroke';

  points: ChartDrawingPoint[];

  strokeOpacity?: number;

}



export interface ChartDrawingCrossMarker extends ChartDrawingStyle {

  id: string;

  type: 'cross-marker';

  point: ChartDrawingPoint;

}



export interface ChartDrawingDotMarker extends ChartDrawingStyle {

  id: string;

  type: 'dot-marker';

  point: ChartDrawingPoint;

}



export interface ChartDrawingDotHaloMarker extends ChartDrawingStyle {

  id: string;

  type: 'dot-halo-marker';

  point: ChartDrawingPoint;

  /** Radio del halo en px de pantalla (default 14). */
  haloRadius?: number;

}



export interface ChartDrawingArrowMarker extends ChartDrawingStyle {

  id: string;

  type: 'arrow-marker';

  point: ChartDrawingPoint;

  direction: ChartMarkerDirection;

}



export interface ChartDrawingArrowCircleMarker extends ChartDrawingStyle {

  id: string;

  type: 'arrow-circle-marker';

  point: ChartDrawingPoint;

  direction: ChartMarkerDirection;

}



export type ChartDrawing =

  | ChartDrawingLine

  | ChartDrawingRay

  | ChartDrawingExtLine

  | ChartDrawingInfoLine

  | ChartDrawingTrendAngle

  | ChartDrawingRegression

  | ChartDrawingHLine

  | ChartDrawingHRay

  | ChartDrawingVLine

  | ChartDrawingRectangle

  | ChartDrawingFibonacci

  | ChartDrawingGannFan

  | ChartDrawingFibTrendExt

  | ChartDrawingFibTimeZone

  | ChartDrawingGannGrid

  | ChartDrawingGannSquare

  | ChartDrawingChannel

  | ChartDrawingTextLabel

  | ChartDrawingPitchfork

  | ChartDrawingBrushStroke

  | ChartDrawingCrossMarker

  | ChartDrawingDotMarker

  | ChartDrawingDotHaloMarker

  | ChartDrawingArrowMarker

  | ChartDrawingArrowCircleMarker;



export type ChartDrawingVertexPatch = {

  p1?: ChartDrawingPoint;

  p2?: ChartDrawingPoint;

  p3?: ChartDrawingPoint;

  point?: ChartDrawingPoint;

  price?: number;

  time?: string;

  direction?: ChartMarkerDirection;

  color?: string;

  lineWidth?: number;

  lineStyle?: ChartLineStyle;

  locked?: boolean;

  visible?: boolean;

  label?: string;

  text?: string;

  templateId?: string;

  fillOpacity?: number;

  fontSize?: number;

  strokeOpacity?: number;

  points?: ChartDrawingPoint[];

  alertOnCross?: boolean;

  semanticId?: string;

};



export const DEFAULT_DOT_HALO_RADIUS = 14;

export const DEFAULT_CHART_DRAW_COLOR = '#14b8a6';

export const DEFAULT_CHANNEL_FILL_OPACITY = 0.12;

export const DEFAULT_RECT_FILL_OPACITY = 0.12;

export const DEFAULT_BRUSH_STROKE_OPACITY = 1;

export const DEFAULT_HIGHLIGHTER_STROKE_OPACITY = 0.35;

export const DEFAULT_TEXT_LABEL = 'Texto';

export const DEFAULT_TEXT_FONT_SIZE = 13;

export const DEFAULT_LINE_WIDTH = 1.5;



/** Niveles estándar de retroceso de Fibonacci (0 = extremo inferior, 1 = superior). */

export const FIBONACCI_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const;

/** Retroceso + extensiones clásicas (127.2 % … 261.8 %). */
export const FIBONACCI_TREND_EXT_LEVELS = [
  0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618, 2, 2.618,
] as const;

/** Multiplicadores de periodo base para zonas temporales Fibonacci. */
export const FIBONACCI_TIME_ZONE_MULTIPLIERS = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34] as const;

export const GANN_GRID_DIVISIONS = 8;



export function newChartDrawingId(): string {

  return `draw-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

}



export function drawingLineWidth(drawing: ChartDrawing): number {

  return drawing.lineWidth ?? DEFAULT_LINE_WIDTH;

}



export function drawingLineStyle(drawing: ChartDrawing): ChartLineStyle {

  return drawing.lineStyle ?? 'solid';

}



export function isDrawingVisible(drawing: ChartDrawing): boolean {

  return drawing.visible !== false;

}



export function isPointLineDrawing(

  drawing: ChartDrawing,

): drawing is

  | ChartDrawingLine

  | ChartDrawingRay

  | ChartDrawingExtLine

  | ChartDrawingInfoLine

  | ChartDrawingTrendAngle

  | ChartDrawingRegression

  | ChartDrawingFibonacci

  | ChartDrawingGannFan

  | ChartDrawingFibTrendExt

  | ChartDrawingFibTimeZone

  | ChartDrawingGannGrid

  | ChartDrawingGannSquare

  | ChartDrawingChannel

  | ChartDrawingRectangle {

  return (

    drawing.type === 'line' ||

    drawing.type === 'ray' ||

    drawing.type === 'ext-line' ||

    drawing.type === 'info-line' ||

    drawing.type === 'trend-angle' ||

    drawing.type === 'regression' ||

    drawing.type === 'fibonacci' ||

    drawing.type === 'fib-trend-ext' ||

    drawing.type === 'fib-time-zone' ||

    drawing.type === 'gann-fan' ||

    drawing.type === 'gann-grid' ||

    drawing.type === 'gann-square' ||

    drawing.type === 'channel' ||

    drawing.type === 'pitchfork' ||

    drawing.type === 'rectangle'

  );

}



export function isLineLikeDrawing(

  drawing: ChartDrawing,

): drawing is ChartDrawingLine | ChartDrawingRay {

  return drawing.type === 'line' || drawing.type === 'ray';

}



export function drawingAlertPrice(drawing: ChartDrawing): number | null {

  if (drawing.type === 'hline' || drawing.type === 'hray') {

    return drawing.type === 'hline' ? drawing.price : drawing.point.price;

  }

  if (isLineLikeDrawing(drawing)) {

    return (drawing.p1.price + drawing.p2.price) / 2;

  }

  if (

    drawing.type === 'ext-line' ||

    drawing.type === 'info-line' ||

    drawing.type === 'trend-angle' ||

    drawing.type === 'regression'

  ) {

    return (drawing.p1.price + drawing.p2.price) / 2;

  }

  return null;

}



export function drawingHasLinkedOrder(drawing: ChartDrawing): boolean {
  return typeof drawing.linkedOrderId === 'string' && drawing.linkedOrderId.length > 0;
}



export function formatDrawingLabel(drawing: ChartDrawing): string {

  if (drawing.type === 'info-line') return drawing.label;

  if (drawing.type === 'text-label') return drawing.label;

  return drawing.label ?? '';

}


