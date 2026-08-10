import type { ChartDrawTool, ChartDrawing, ChartDrawingVertexPatch, ChartLineStyle } from './chart-drawings.js';
import {
  DEFAULT_CHART_DRAW_COLOR,
  DEFAULT_LINE_WIDTH,
  DEFAULT_RECT_FILL_OPACITY,
  drawingAlertPrice,
} from './chart-drawings.js';

export type ChartDrawingPropertiesTab = 'style' | 'text' | 'coordinates' | 'visibility';

export interface ChartDrawingTemplateStyle {
  color: string;
  lineWidth: number;
  lineStyle: ChartLineStyle;
  fillOpacity?: number;
}

export interface ChartDrawingTemplateText {
  /** Nota o texto auxiliar del objeto */
  text?: string;
  /** Etiqueta por defecto (línea info, etc.) */
  label?: string;
}

export interface ChartDrawingTemplateVisibility {
  visible: boolean;
  locked: boolean;
  alertOnCross: boolean;
}

/** En plantillas las coordenadas se fijan al colocar; aquí solo preferencias de presentación. */
export interface ChartDrawingTemplateCoordinates {
  showPriceLabels?: boolean;
  showTimeLabels?: boolean;
}

export interface ChartDrawingTemplate {
  id: string;
  name: string;
  /** Vacío = aplica a cualquier tipo de objeto gráfico */
  drawingTypes: ChartDrawing['type'][];
  style: ChartDrawingTemplateStyle;
  text: ChartDrawingTemplateText;
  coordinates: ChartDrawingTemplateCoordinates;
  visibility: ChartDrawingTemplateVisibility;
  /** Plantilla predefinida del sistema (no eliminable) */
  builtin?: boolean;
}

export function newChartDrawingTemplateId(): string {
  return `dtpl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

export const DEFAULT_DRAWING_TEMPLATES: ChartDrawingTemplate[] = [
  {
    id: 'builtin-hline-support',
    name: 'Soporte H',
    drawingTypes: ['hline', 'hray'],
    builtin: true,
    style: { color: '#22c55e', lineWidth: 1.5, lineStyle: 'dashed' },
    text: { text: 'Soporte' },
    coordinates: { showPriceLabels: true },
    visibility: { visible: true, locked: false, alertOnCross: true },
  },
  {
    id: 'builtin-hline-resistance',
    name: 'Resistencia H',
    drawingTypes: ['hline', 'hray'],
    builtin: true,
    style: { color: '#ef4444', lineWidth: 1.5, lineStyle: 'dashed' },
    text: { text: 'Resistencia' },
    coordinates: { showPriceLabels: true },
    visibility: { visible: true, locked: false, alertOnCross: true },
  },
  {
    id: 'builtin-trend',
    name: 'Tendencia',
    drawingTypes: ['line', 'ray', 'ext-line', 'trend-angle', 'regression'],
    builtin: true,
    style: { color: '#14b8a6', lineWidth: 2, lineStyle: 'solid' },
    text: {},
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
  {
    id: 'builtin-vline',
    name: 'Evento V',
    drawingTypes: ['vline'],
    builtin: true,
    style: { color: '#a78bfa', lineWidth: 1.5, lineStyle: 'dotted' },
    text: { text: 'Evento' },
    coordinates: { showTimeLabels: true },
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
  {
    id: 'builtin-fib',
    name: 'Fibonacci',
    drawingTypes: ['fibonacci'],
    builtin: true,
    style: { color: '#f59e0b', lineWidth: 1.5, lineStyle: 'solid' },
    text: {},
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
  {
    id: 'builtin-zone',
    name: 'Zona',
    drawingTypes: ['rectangle', 'channel'],
    builtin: true,
    style: { color: '#38bdf8', lineWidth: 1.5, lineStyle: 'solid', fillOpacity: 0.15 },
    text: {},
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
  {
    id: 'builtin-marker',
    name: 'Marca',
    drawingTypes: ['cross-marker', 'dot-marker', 'dot-halo-marker', 'arrow-marker', 'arrow-circle-marker'],
    builtin: true,
    style: { color: '#f97316', lineWidth: 2, lineStyle: 'solid' },
    text: {},
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
  {
    id: 'builtin-info',
    name: 'Línea info',
    drawingTypes: ['info-line'],
    builtin: true,
    style: { color: '#14b8a6', lineWidth: 1.5, lineStyle: 'solid' },
    text: { label: 'Δ' },
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  },
];

/** Herramientas de dibujo que usan plantilla al colocar (no puntero/crosshair). */
export const TEMPLATE_ASSIGNABLE_TOOLS: ChartDrawTool[] = [
  'cross',
  'dot',
  'dot-halo',
  'arrow',
  'arrow-circle',
  'arrow-up',
  'arrow-down',
  'line',
  'ray',
  'info-line',
  'ext-line',
  'trend-angle',
  'hline',
  'hray',
  'vline',
  'regression',
  'rectangle',
  'fibonacci',
  'fib-trend-ext',
  'fib-time-zone',
  'gann-fan',
  'gann-grid',
  'gann-square',
  'channel',
  'pitchfork',
  'text',
  'brush',
  'highlighter',
];

export function drawingTypeForTool(tool: ChartDrawTool): ChartDrawing['type'] | null {
  const map: Partial<Record<ChartDrawTool, ChartDrawing['type']>> = {
    cross: 'cross-marker',
    dot: 'dot-marker',
    'dot-halo': 'dot-halo-marker',
    arrow: 'arrow-marker',
    'arrow-circle': 'arrow-circle-marker',
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
    text: 'text-label',
    brush: 'brush-stroke',
    highlighter: 'brush-stroke',
    'arrow-up': 'arrow-marker',
    'arrow-down': 'arrow-marker',
  };
  return map[tool] ?? null;
}

export function templateMatchesDrawingType(
  template: ChartDrawingTemplate,
  type: ChartDrawing['type'],
): boolean {
  if (!template.drawingTypes.length) return true;
  return template.drawingTypes.includes(type);
}

export function normalizeDrawingTemplates(
  raw: ChartDrawingTemplate[] | undefined,
): ChartDrawingTemplate[] {
  if (!raw?.length) return [...DEFAULT_DRAWING_TEMPLATES];
  const merged: ChartDrawingTemplate[] = raw.map((t) => ({
    ...t,
    style: {
      color: t.style?.color ?? DEFAULT_CHART_DRAW_COLOR,
      lineWidth: t.style?.lineWidth ?? DEFAULT_LINE_WIDTH,
      lineStyle: t.style?.lineStyle ?? 'solid',
      ...(t.style?.fillOpacity != null ? { fillOpacity: t.style.fillOpacity } : {}),
    },
    text: t.text ?? {},
    coordinates: t.coordinates ?? {},
    visibility: {
      visible: t.visibility?.visible !== false,
      locked: t.visibility?.locked === true,
      alertOnCross: t.visibility?.alertOnCross === true,
    },
  }));
  for (const builtin of DEFAULT_DRAWING_TEMPLATES) {
    if (!merged.some((t) => t.id === builtin.id)) {
      merged.unshift(builtin);
    }
  }
  return merged;
}

export function createBlankDrawingTemplate(name = 'Nueva plantilla'): ChartDrawingTemplate {
  return {
    id: newChartDrawingTemplateId(),
    name,
    drawingTypes: [],
    style: {
      color: DEFAULT_CHART_DRAW_COLOR,
      lineWidth: DEFAULT_LINE_WIDTH,
      lineStyle: 'solid',
      fillOpacity: DEFAULT_RECT_FILL_OPACITY,
    },
    text: {},
    coordinates: {},
    visibility: { visible: true, locked: false, alertOnCross: false },
  };
}

export type ChartDrawingStyleFromTemplate = Pick<
  ChartDrawing,
  'color' | 'lineWidth' | 'lineStyle' | 'locked' | 'visible' | 'alertOnCross' | 'label' | 'text' | 'templateId'
> & { fillOpacity?: number };

export function stylePatchFromTemplate(template: ChartDrawingTemplate): ChartDrawingStyleFromTemplate {
  const patch: ChartDrawingStyleFromTemplate = {
    templateId: template.id,
    color: template.style.color,
    lineWidth: template.style.lineWidth,
    lineStyle: template.style.lineStyle,
    visible: template.visibility.visible,
    locked: template.visibility.locked,
    alertOnCross: template.visibility.alertOnCross,
  };
  if (template.text.text) patch.text = template.text.text;
  if (template.text.label) patch.label = template.text.label;
  if (template.style.fillOpacity != null) patch.fillOpacity = template.style.fillOpacity;
  return patch;
}

/** Aplica plantilla a un objeto existente (solo campos compatibles con su tipo). */
export function drawingPatchFromTemplate(
  drawing: ChartDrawing,
  template: ChartDrawingTemplate,
): ChartDrawingVertexPatch {
  const patch: ChartDrawingVertexPatch = {
    templateId: template.id,
    color: template.style.color,
    lineWidth: template.style.lineWidth,
    lineStyle: template.style.lineStyle,
    visible: template.visibility.visible,
    locked: template.visibility.locked,
  };

  if (template.text.text) {
    patch.text = template.text.text;
  }

  if (drawing.type === 'info-line' && template.text.label) {
    patch.label = template.text.label;
  }

  if (drawing.type === 'rectangle' && template.style.fillOpacity != null) {
    patch.fillOpacity = template.style.fillOpacity;
  }

  if (drawing.type === 'channel' && template.style.fillOpacity != null) {
    patch.fillOpacity = template.style.fillOpacity;
  }

  if (drawing.type === 'text-label' && template.text.label) {
    patch.label = template.text.label;
  }

  if (drawingAlertPrice(drawing) != null) {
    patch.alertOnCross = template.visibility.alertOnCross;
  }

  return patch;
}
