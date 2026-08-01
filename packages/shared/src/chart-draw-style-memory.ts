import type { ChartDrawTool, ChartDrawing, ChartLineStyle } from './chart-drawings.js';
import {
  DEFAULT_BRUSH_STROKE_OPACITY,
  DEFAULT_CHANNEL_FILL_OPACITY,
  DEFAULT_CHART_DRAW_COLOR,
  DEFAULT_HIGHLIGHTER_STROKE_OPACITY,
  DEFAULT_LINE_WIDTH,
  DEFAULT_RECT_FILL_OPACITY,
  DEFAULT_TEXT_FONT_SIZE,
} from './chart-drawings.js';
import type { ChartDrawingTemplate } from './chart-drawing-templates.js';

/** Último estilo usado manualmente por herramienta (color, grosor, etc.). */
export interface DrawToolStyleMemory {
  color?: string;
  lineWidth?: number;
  lineStyle?: ChartLineStyle;
  fillOpacity?: number;
  strokeOpacity?: number;
  fontSize?: number;
}

export type DrawToolStyleField =
  | 'color'
  | 'lineWidth'
  | 'lineStyle'
  | 'fillOpacity'
  | 'strokeOpacity'
  | 'fontSize';

const HIGHLIGHTER_LINE_WIDTH_THRESHOLD = 8;

const DRAWING_TYPE_TO_TOOL: Partial<Record<ChartDrawing['type'], ChartDrawTool>> = {
  'cross-marker': 'cross',
  'dot-marker': 'dot',
  'dot-halo-marker': 'dot-halo',
  'arrow-marker': 'arrow',
  'arrow-circle-marker': 'arrow-circle',
  line: 'line',
  ray: 'ray',
  'info-line': 'info-line',
  'ext-line': 'ext-line',
  'trend-angle': 'trend-angle',
  hline: 'hline',
  hray: 'hray',
  vline: 'vline',
  regression: 'regression',
  rectangle: 'rectangle',
  fibonacci: 'fibonacci',
  'fib-trend-ext': 'fib-trend-ext',
  'fib-time-zone': 'fib-time-zone',
  'gann-fan': 'gann-fan',
  'gann-grid': 'gann-grid',
  'gann-square': 'gann-square',
  channel: 'channel',
  pitchfork: 'pitchfork',
  'text-label': 'text',
};

export function brushStrokeDrawTool(
  drawing: Pick<ChartDrawing, 'type'> & { lineWidth?: number; strokeOpacity?: number },
): 'brush' | 'highlighter' {
  const width = drawing.lineWidth ?? DEFAULT_LINE_WIDTH;
  if (width >= HIGHLIGHTER_LINE_WIDTH_THRESHOLD) return 'highlighter';
  const opacity = drawing.strokeOpacity ?? DEFAULT_BRUSH_STROKE_OPACITY;
  if (opacity <= 0.5) return 'highlighter';
  return 'brush';
}

export function drawToolForDrawing(drawing: ChartDrawing): ChartDrawTool | null {
  if (drawing.type === 'brush-stroke') {
    return brushStrokeDrawTool(drawing);
  }
  return DRAWING_TYPE_TO_TOOL[drawing.type] ?? null;
}

export function drawToolForDrawingType(type: ChartDrawing['type']): ChartDrawTool | null {
  if (type === 'brush-stroke') return null;
  return DRAWING_TYPE_TO_TOOL[type] ?? null;
}

export function defaultStyleForDrawTool(tool: ChartDrawTool): DrawToolStyleMemory {
  if (tool === 'highlighter') {
    return {
      color: DEFAULT_CHART_DRAW_COLOR,
      lineWidth: 12,
      strokeOpacity: DEFAULT_HIGHLIGHTER_STROKE_OPACITY,
    };
  }
  if (tool === 'brush') {
    return {
      color: DEFAULT_CHART_DRAW_COLOR,
      lineWidth: DEFAULT_LINE_WIDTH,
      strokeOpacity: DEFAULT_BRUSH_STROKE_OPACITY,
    };
  }
  if (tool === 'text') {
    return {
      color: DEFAULT_CHART_DRAW_COLOR,
      fontSize: DEFAULT_TEXT_FONT_SIZE,
    };
  }
  if (tool === 'channel') {
    return {
      color: DEFAULT_CHART_DRAW_COLOR,
      lineWidth: DEFAULT_LINE_WIDTH,
      lineStyle: 'solid',
      fillOpacity: DEFAULT_CHANNEL_FILL_OPACITY,
    };
  }
  if (tool === 'rectangle') {
    return {
      color: DEFAULT_CHART_DRAW_COLOR,
      lineWidth: DEFAULT_LINE_WIDTH,
      lineStyle: 'solid',
      fillOpacity: DEFAULT_RECT_FILL_OPACITY,
    };
  }
  return {
    color: DEFAULT_CHART_DRAW_COLOR,
    lineWidth: DEFAULT_LINE_WIDTH,
    lineStyle: 'solid',
  };
}

export interface ResolvedDrawToolStyle {
  color: string;
  lineWidth?: number;
  lineStyle?: ChartLineStyle;
  fillOpacity?: number;
  strokeOpacity?: number;
  fontSize?: number;
}

export function resolveDrawToolStyle(
  tool: ChartDrawTool,
  options?: {
    memory?: DrawToolStyleMemory | null;
    templatePatch?: Partial<DrawToolStyleMemory> | null;
  },
): ResolvedDrawToolStyle {
  const merged = {
    ...defaultStyleForDrawTool(tool),
    ...(options?.templatePatch ?? {}),
    ...(options?.memory ?? {}),
  };
  return {
    ...merged,
    color: merged.color ?? DEFAULT_CHART_DRAW_COLOR,
  };
}

export function drawToolStyleFields(tool: ChartDrawTool): DrawToolStyleField[] {
  if (tool === 'text') return ['color', 'fontSize'];
  if (tool === 'brush' || tool === 'highlighter') return ['color', 'lineWidth', 'strokeOpacity'];
  if (tool === 'rectangle' || tool === 'channel') {
    return ['color', 'lineWidth', 'lineStyle', 'fillOpacity'];
  }
  if (tool === 'cross' || tool === 'dot') return ['color'];
  return ['color', 'lineWidth', 'lineStyle'];
}

export function styleMemoryFromDrawing(drawing: ChartDrawing): DrawToolStyleMemory {
  const memory: DrawToolStyleMemory = { color: drawing.color };
  if (drawing.lineWidth != null) memory.lineWidth = drawing.lineWidth;
  if (drawing.lineStyle) memory.lineStyle = drawing.lineStyle;
  if ('fillOpacity' in drawing && drawing.fillOpacity != null) {
    memory.fillOpacity = drawing.fillOpacity;
  }
  if (drawing.type === 'brush-stroke' && drawing.strokeOpacity != null) {
    memory.strokeOpacity = drawing.strokeOpacity;
  }
  if (drawing.type === 'text-label' && drawing.fontSize != null) {
    memory.fontSize = drawing.fontSize;
  }
  return memory;
}

export function styleMemoryFromTemplate(template: ChartDrawingTemplate): DrawToolStyleMemory {
  const memory: DrawToolStyleMemory = {
    color: template.style.color,
    lineWidth: template.style.lineWidth,
    lineStyle: template.style.lineStyle,
  };
  if (template.style.fillOpacity != null) memory.fillOpacity = template.style.fillOpacity;
  return memory;
}

export function mergeDrawToolStyleMemory(
  base: DrawToolStyleMemory | undefined,
  patch: DrawToolStyleMemory,
): DrawToolStyleMemory {
  return { ...base, ...patch };
}

export function stylePatchFromDrawToolMemory(
  memory: DrawToolStyleMemory | undefined | null,
): Partial<DrawToolStyleMemory> | null {
  if (!memory) return null;
  const patch: DrawToolStyleMemory = {};
  if (memory.color) patch.color = memory.color;
  if (memory.lineWidth != null) patch.lineWidth = memory.lineWidth;
  if (memory.lineStyle) patch.lineStyle = memory.lineStyle;
  if (memory.fillOpacity != null) patch.fillOpacity = memory.fillOpacity;
  if (memory.strokeOpacity != null) patch.strokeOpacity = memory.strokeOpacity;
  if (memory.fontSize != null) patch.fontSize = memory.fontSize;
  return Object.keys(patch).length > 0 ? patch : null;
}
