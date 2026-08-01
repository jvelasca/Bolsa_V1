import type { ChartDrawTool, ChartDrawing } from './chart-drawings.js';

/** Categorías de la barra vertical (orden XTB / plataformas pro). */
export type DrawingToolGroupId =
  | 'cursor'
  | 'lines'
  | 'channels'
  | 'pitchforks'
  | 'fibonacci'
  | 'gann'
  | 'brushes'
  | 'arrows'
  | 'shapes'
  | 'text'
  | 'measure';

export const DRAWING_TOOL_GROUP_ORDER: DrawingToolGroupId[] = [
  'cursor',
  'lines',
  'channels',
  'pitchforks',
  'fibonacci',
  'gann',
  'brushes',
  'arrows',
  'shapes',
  'text',
  'measure',
];

export const DRAWING_TOOL_GROUP_LABELS: Record<DrawingToolGroupId, string> = {
  cursor: 'Cursor',
  lines: 'Líneas',
  channels: 'Canales',
  pitchforks: 'Tridentes',
  fibonacci: 'Fibonacci',
  gann: 'Gann',
  brushes: 'Pinceles',
  arrows: 'Flechas',
  shapes: 'Figuras',
  text: 'Texto',
  measure: 'Medida',
};

/**
 * ID técnico estable del objeto gráfico (órdenes, estudios, reportes).
 * Formato: `categoría.nombre_snake`.
 */
export type DrawingSemanticId = string;

export const DRAWING_SEMANTIC_BY_TYPE: Record<ChartDrawing['type'], DrawingSemanticId> = {
  'cross-marker': 'cursor.cross',
  'dot-marker': 'cursor.dot',
  'dot-halo-marker': 'cursor.dot_halo',
  'arrow-marker': 'arrow.marker',
  'arrow-circle-marker': 'arrow.marker_circle',
  line: 'line.trend',
  ray: 'line.ray',
  'ext-line': 'line.extended',
  'info-line': 'line.info',
  'trend-angle': 'line.trend_angle',
  hline: 'line.horizontal',
  hray: 'line.horizontal_ray',
  vline: 'line.vertical',
  regression: 'channel.regression',
  channel: 'channel.parallel',
  pitchfork: 'pitchfork.standard',
  fibonacci: 'fibonacci.retracement',
  'fib-trend-ext': 'fibonacci.trend_extension',
  'fib-time-zone': 'fibonacci.time_zone',
  'gann-fan': 'gann.fan',
  'gann-grid': 'gann.grid',
  'gann-square': 'gann.square',
  rectangle: 'shape.rectangle',
  'text-label': 'text.plain',
  'brush-stroke': 'brush.stroke',
};

export const DRAWING_SEMANTIC_BY_TOOL: Partial<Record<ChartDrawTool, DrawingSemanticId>> = {
  select: 'nav.pointer',
  crosshair: 'measure.crosshair',
  cross: 'cursor.cross',
  dot: 'cursor.dot',
  'dot-halo': 'cursor.dot_halo',
  arrow: 'arrow.marker',
  'arrow-circle': 'arrow.marker_circle',
  line: 'line.trend',
  ray: 'line.ray',
  'info-line': 'line.info',
  'ext-line': 'line.extended',
  'trend-angle': 'line.trend_angle',
  hline: 'line.horizontal',
  hray: 'line.horizontal_ray',
  vline: 'line.vertical',
  regression: 'channel.regression',
  channel: 'channel.parallel',
  pitchfork: 'pitchfork.standard',
  fibonacci: 'fibonacci.retracement',
  'fib-trend-ext': 'fibonacci.trend_extension',
  'fib-time-zone': 'fibonacci.time_zone',
  'gann-fan': 'gann.fan',
  'gann-grid': 'gann.grid',
  'gann-square': 'gann.square',
  rectangle: 'shape.rectangle',
  text: 'text.plain',
  brush: 'brush.pen',
  highlighter: 'brush.highlighter',
  'arrow-up': 'arrow.up',
  'arrow-down': 'arrow.down',
};

export function semanticIdForDrawingType(type: ChartDrawing['type']): DrawingSemanticId {
  return DRAWING_SEMANTIC_BY_TYPE[type];
}

export function semanticIdForDrawTool(tool: ChartDrawTool): DrawingSemanticId | undefined {
  return DRAWING_SEMANTIC_BY_TOOL[tool];
}

export function resolveDrawingSemanticId(
  drawing: Pick<ChartDrawing, 'type'> & { semanticId?: string },
): DrawingSemanticId {
  if (drawing.semanticId && typeof drawing.semanticId === 'string') {
    return drawing.semanticId;
  }
  return semanticIdForDrawingType(drawing.type);
}

export const DEFAULT_GROUP_PRIMARY_FAVORITE: Partial<Record<DrawingToolGroupId, ChartDrawTool>> = {
  cursor: 'select',
  lines: 'line',
  channels: 'channel',
  pitchforks: 'pitchfork',
  fibonacci: 'fibonacci',
  gann: 'gann-fan',
  brushes: 'brush',
  arrows: 'arrow-circle',
  shapes: 'rectangle',
  text: 'text',
  measure: 'crosshair',
};

export const DRAW_TOOL_TO_GROUP: Partial<Record<ChartDrawTool, DrawingToolGroupId>> = {
  select: 'cursor',
  cross: 'cursor',
  dot: 'cursor',
  'dot-halo': 'cursor',
  arrow: 'cursor',
  line: 'lines',
  ray: 'lines',
  'info-line': 'lines',
  'ext-line': 'lines',
  'trend-angle': 'lines',
  hline: 'lines',
  hray: 'lines',
  vline: 'lines',
  channel: 'channels',
  regression: 'channels',
  pitchfork: 'pitchforks',
  fibonacci: 'fibonacci',
  'fib-trend-ext': 'fibonacci',
  'fib-time-zone': 'fibonacci',
  'gann-fan': 'gann',
  'gann-grid': 'gann',
  'gann-square': 'gann',
  brush: 'brushes',
  highlighter: 'brushes',
  'arrow-circle': 'arrows',
  'arrow-up': 'arrows',
  'arrow-down': 'arrows',
  rectangle: 'shapes',
  text: 'text',
  crosshair: 'measure',
};

export const DEFAULT_DRAW_TOOL_FAVORITES: ChartDrawTool[] = [];

/** Orden canónico de herramientas dentro de cada familia (barra y favoritos). */
export const GROUP_TOOL_ORDER: Partial<Record<DrawingToolGroupId, ChartDrawTool[]>> = {
  cursor: ['select', 'cross', 'dot', 'dot-halo', 'arrow'],
  lines: ['line', 'ray', 'info-line', 'ext-line', 'trend-angle', 'hline', 'hray', 'vline'],
  channels: ['channel', 'regression'],
  pitchforks: ['pitchfork'],
  fibonacci: ['fibonacci', 'fib-trend-ext', 'fib-time-zone'],
  gann: ['gann-fan', 'gann-grid', 'gann-square'],
  brushes: ['brush', 'highlighter'],
  arrows: ['arrow-circle', 'arrow-up', 'arrow-down'],
  shapes: ['rectangle'],
  text: ['text'],
  measure: ['crosshair'],
};

export function compareDrawToolsInGroup(a: ChartDrawTool, b: ChartDrawTool): number {
  const group = drawToolGroup(a);
  if (!group || drawToolGroup(b) !== group) return 0;
  const order = GROUP_TOOL_ORDER[group] ?? [];
  const ia = order.indexOf(a);
  const ib = order.indexOf(b);
  if (ia === -1 && ib === -1) return 0;
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

const DRAW_TOOL_SET = new Set<string>();

export function drawToolGroup(tool: ChartDrawTool): DrawingToolGroupId | null {
  return DRAW_TOOL_TO_GROUP[tool] ?? null;
}

export function groupDrawToolFavorites(
  favorites: ChartDrawTool[],
  groupId: DrawingToolGroupId,
): ChartDrawTool[] {
  return favorites.filter((tool) => drawToolGroup(tool) === groupId);
}

export function primaryFavoriteForGroup(
  groupId: DrawingToolGroupId,
  favorites: ChartDrawTool[],
  knownTools?: readonly ChartDrawTool[],
): ChartDrawTool | null {
  const known = knownTools ? new Set(knownTools) : null;
  for (const tool of favorites) {
    if (drawToolGroup(tool) !== groupId) continue;
    if (known && !known.has(tool)) continue;
    return tool;
  }
  const fallback = DEFAULT_GROUP_PRIMARY_FAVORITE[groupId];
  if (!fallback) return null;
  if (known && !known.has(fallback)) return null;
  return fallback;
}

export function isPrimaryDrawToolFavorite(
  tool: ChartDrawTool,
  favorites: ChartDrawTool[],
  knownTools?: readonly ChartDrawTool[],
): boolean {
  const group = drawToolGroup(tool);
  if (!group) return false;
  return primaryFavoriteForGroup(group, favorites, knownTools) === tool;
}

export function isExtraDrawToolFavorite(
  tool: ChartDrawTool,
  favorites: ChartDrawTool[],
): boolean {
  return favorites.includes(tool) && !isPrimaryDrawToolFavorite(tool, favorites);
}

export function registerKnownDrawTools(tools: readonly string[]) {
  for (const t of tools) DRAW_TOOL_SET.add(t);
}

function dedupeFavorites(favorites: ChartDrawTool[]): ChartDrawTool[] {
  const seen = new Set<ChartDrawTool>();
  const valid: ChartDrawTool[] = [];
  for (const tool of favorites) {
    if (seen.has(tool)) continue;
    seen.add(tool);
    valid.push(tool);
  }
  return valid;
}

/** Reordena favoritos por familia (orden de barra) y hermanos (orden de catálogo). */
export function organizeDrawToolFavorites(
  favorites: ChartDrawTool[],
  knownTools?: readonly ChartDrawTool[],
): ChartDrawTool[] {
  const known = knownTools ? new Set(knownTools) : null;
  const unique = dedupeFavorites(favorites);
  const groupEntries = new Map<
    DrawingToolGroupId,
    { primary: ChartDrawTool; tools: ChartDrawTool[] }
  >();

  for (const tool of unique) {
    if (known && !known.has(tool)) continue;
    const group = drawToolGroup(tool);
    if (!group) continue;
    let entry = groupEntries.get(group);
    if (!entry) {
      entry = { primary: tool, tools: [tool] };
      groupEntries.set(group, entry);
    } else if (!entry.tools.includes(tool)) {
      entry.tools.push(tool);
    }
  }

  const result: ChartDrawTool[] = [];
  for (const groupId of DRAWING_TOOL_GROUP_ORDER) {
    const entry = groupEntries.get(groupId);
    if (!entry) continue;
    const extras = entry.tools
      .filter((tool) => tool !== entry.primary)
      .sort(compareDrawToolsInGroup);
    result.push(entry.primary, ...extras);
  }
  return result;
}

/** Inserta un favorito junto a los de su familia, no al final de la lista. */
export function insertDrawToolFavorite(
  favorites: ChartDrawTool[],
  tool: ChartDrawTool,
): ChartDrawTool[] {
  const group = drawToolGroup(tool);
  if (!group) return favorites;
  const without = dedupeFavorites(favorites.filter((item) => item !== tool));

  let insertAt = -1;
  for (let i = without.length - 1; i >= 0; i -= 1) {
    if (drawToolGroup(without[i]!) === group) {
      insertAt = i + 1;
      break;
    }
  }

  if (insertAt < 0) {
    const groupIdx = DRAWING_TOOL_GROUP_ORDER.indexOf(group);
    insertAt = without.length;
    for (let i = 0; i < without.length; i += 1) {
      const itemGroup = drawToolGroup(without[i]!);
      if (!itemGroup) continue;
      if (DRAWING_TOOL_GROUP_ORDER.indexOf(itemGroup) > groupIdx) {
        insertAt = i;
        break;
      }
    }
  }

  const next = [...without];
  next.splice(insertAt, 0, tool);
  return next;
}

export function normalizeDrawToolFavorites(
  raw: ChartDrawTool[] | undefined | null,
  knownTools: readonly ChartDrawTool[],
): ChartDrawTool[] {
  const known = new Set(knownTools);
  if (raw == null) {
    return [...DEFAULT_DRAW_TOOL_FAVORITES];
  }
  const filtered = dedupeFavorites(raw.filter((tool) => known.has(tool)));
  return organizeDrawToolFavorites(filtered, knownTools);
}

export function toggleDrawToolFavoriteList(
  favorites: ChartDrawTool[],
  tool: ChartDrawTool,
): ChartDrawTool[] {
  const group = drawToolGroup(tool);
  if (!group) return favorites;
  const unique = dedupeFavorites(favorites);
  if (unique.includes(tool)) {
    return organizeDrawToolFavorites(unique.filter((item) => item !== tool));
  }
  return organizeDrawToolFavorites(insertDrawToolFavorite(unique, tool));
}

/** Herramientas implementadas en el motor (fase 1–2). */
export const IMPLEMENTED_DRAW_TOOLS: ChartDrawTool[] = [
  'select',
  'crosshair',
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
  'channel',
  'pitchfork',
  'fibonacci',
  'fib-trend-ext',
  'fib-time-zone',
  'gann-fan',
  'gann-grid',
  'gann-square',
  'rectangle',
  'text',
  'brush',
  'highlighter',
];

registerKnownDrawTools(IMPLEMENTED_DRAW_TOOLS);
