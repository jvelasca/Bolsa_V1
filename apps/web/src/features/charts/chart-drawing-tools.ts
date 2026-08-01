import type { ChartDrawTool } from '@bolsa/shared';
import {
  DRAWING_TOOL_GROUP_LABELS,
  DRAWING_TOOL_GROUP_ORDER,
  drawToolGroup,
  groupDrawToolFavorites,
  isExtraDrawToolFavorite,
  primaryFavoriteForGroup,
  type DrawingToolGroupId,
} from '@bolsa/shared';
import type { LucideIcon } from 'lucide-react';
import {
  ArrowRight,
  ArrowUpRight,
  BetweenVerticalStart,
  Circle,
  CircleDot,
  Compass,
  Crosshair,
  GitBranch,
  Grid3x3,
  GripVertical,
  Hexagon,
  Highlighter,
  Info,
  Minus,
  MousePointer2,
  MoveUpRight,
  Pencil,
  Ruler,
  Square,
  TrendingUp,
  Type,
  UnfoldHorizontal,
  Waves,
  Waypoints,
} from 'lucide-react';

export type { DrawingToolGroupId };

export const DRAWING_TOOL_GROUPS: {
  id: DrawingToolGroupId;
  label: string;
  icon: LucideIcon;
}[] = DRAWING_TOOL_GROUP_ORDER.map((id) => ({
  id,
  label: DRAWING_TOOL_GROUP_LABELS[id],
  icon:
    id === 'cursor'
      ? MousePointer2
      : id === 'lines'
        ? TrendingUp
        : id === 'channels'
          ? BetweenVerticalStart
          : id === 'pitchforks'
            ? Waypoints
            : id === 'fibonacci'
              ? Waves
              : id === 'gann'
                ? Hexagon
                : id === 'brushes'
                  ? Pencil
                  : id === 'arrows'
                    ? ArrowUpRight
                    : id === 'shapes'
                      ? Square
                      : id === 'text'
                        ? Type
                        : Ruler,
}));

export interface DrawingToolDefinition {
  id: ChartDrawTool | string;
  label: string;
  /** Etiqueta abreviada en el botón de familia (p. ej. Lín, H, Fib). */
  shortLabel: string;
  group: DrawingToolGroupId;
  icon: LucideIcon;
  available: boolean;
  hint?: string;
}

const DRAWING_TOOL_SHORT_LABELS: Record<string, string> = {
  select: 'Sel',
  cross: 'Cru',
  dot: 'Pto',
  'dot-halo': 'Hal',
  arrow: 'Fl',
  line: 'Lín',
  ray: 'Ray',
  'info-line': 'Inf',
  'ext-line': 'Ext',
  'trend-angle': 'Ang',
  hline: 'H',
  hray: 'Hr',
  vline: 'V',
  channel: 'Can',
  regression: 'Reg',
  'channel-flat-top': 'Pln',
  'channel-disjoint': 'Dis',
  pitchfork: 'Tri',
  'pitchfork-schiff': 'Sch',
  'pitchfork-modified-schiff': 'Sm',
  'pitchfork-inside': 'Int',
  fibonacci: 'Fib',
  'fib-trend-ext': 'FEx',
  'fib-time-zone': 'FZi',
  'gann-grid': 'GGr',
  'gann-square': 'GSq',
  'gann-square-fixed': 'GFx',
  'gann-fan': 'GAb',
  brush: 'Pin',
  highlighter: 'Res',
  'arrow-circle': 'Fc',
  'arrow-up': '↑',
  'arrow-down': '↓',
  rectangle: 'Rec',
  'shape-rotated-rect': 'Rr',
  text: 'Txt',
  crosshair: 'Med',
};

function catalogEntry(
  entry: Omit<DrawingToolDefinition, 'shortLabel'>,
): DrawingToolDefinition {
  return {
    ...entry,
    shortLabel: DRAWING_TOOL_SHORT_LABELS[entry.id] ?? entry.label.slice(0, 4),
  };
}

const DRAWING_TOOL_CATALOG_RAW: Omit<DrawingToolDefinition, 'shortLabel'>[] = [
  { id: 'select', label: 'Puntero', group: 'cursor', icon: MousePointer2, available: true },
  {
    id: 'cross',
    label: 'Cruz',
    group: 'cursor',
    icon: Crosshair,
    available: true,
    hint: 'Crosshair en cruz (líneas discontinuas)',
  },
  {
    id: 'dot',
    label: 'Punto',
    group: 'cursor',
    icon: CircleDot,
    available: true,
    hint: 'Crosshair en punto (sin líneas)',
  },
  {
    id: 'dot-halo',
    label: 'Punto resaltado',
    group: 'cursor',
    icon: Circle,
    available: true,
    hint: 'Crosshair en punto grande con halo',
  },
  {
    id: 'arrow',
    label: 'Flecha',
    group: 'cursor',
    icon: ArrowUpRight,
    available: true,
    hint: 'Flecha bajo el ratón; clic deja una flecha fija',
  },
  { id: 'line', label: 'Línea de tendencia', group: 'lines', icon: TrendingUp, available: true },
  { id: 'ray', label: 'Rayo', group: 'lines', icon: MoveUpRight, available: true },
  {
    id: 'info-line',
    label: 'Línea de información',
    group: 'lines',
    icon: Info,
    available: true,
    hint: 'Línea con etiqueta de variación',
  },
  {
    id: 'ext-line',
    label: 'Línea extendida',
    group: 'lines',
    icon: UnfoldHorizontal,
    available: true,
  },
  {
    id: 'trend-angle',
    label: 'Ángulo de tendencia',
    group: 'lines',
    icon: Compass,
    available: true,
  },
  { id: 'hline', label: 'Línea horizontal', group: 'lines', icon: Minus, available: true },
  { id: 'hray', label: 'Rayo horizontal', group: 'lines', icon: ArrowRight, available: true },
  { id: 'vline', label: 'Línea vertical', group: 'lines', icon: GripVertical, available: true },
  {
    id: 'channel',
    label: 'Canal paralelo',
    group: 'channels',
    icon: BetweenVerticalStart,
    available: true,
  },
  {
    id: 'regression',
    label: 'Tendencia de regresión',
    group: 'channels',
    icon: TrendingUp,
    available: true,
  },
  {
    id: 'channel-flat-top',
    label: 'Plano superior / inferior',
    group: 'channels',
    icon: GitBranch,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'channel-disjoint',
    label: 'Canal disjunto',
    group: 'channels',
    icon: GitBranch,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'pitchfork',
    label: 'Tridente',
    group: 'pitchforks',
    icon: Waypoints,
    available: true,
    hint: 'Tres clics: base → base → mediana',
  },
  {
    id: 'pitchfork-schiff',
    label: 'Tridente de Schiff',
    group: 'pitchforks',
    icon: GitBranch,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'pitchfork-modified-schiff',
    label: 'Tridente Schiff modificado',
    group: 'pitchforks',
    icon: GitBranch,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'pitchfork-inside',
    label: 'Tridente interno',
    group: 'pitchforks',
    icon: GitBranch,
    available: false,
    hint: 'Próximamente',
  },
  { id: 'fibonacci', label: 'Retroceso', group: 'fibonacci', icon: Waves, available: true },
  {
    id: 'fib-trend-ext',
    label: 'Extensión basada en tendencias',
    group: 'fibonacci',
    icon: TrendingUp,
    available: true,
    hint: 'Dos clics; niveles de extensión Fibonacci',
  },
  {
    id: 'fib-time-zone',
    label: 'Zona temporal Fibonacci',
    group: 'fibonacci',
    icon: GripVertical,
    available: true,
    hint: 'Dos clics; líneas verticales en secuencia Fibonacci',
  },
  {
    id: 'gann-grid',
    label: 'Cuadrícula Gann',
    group: 'gann',
    icon: Grid3x3,
    available: true,
    hint: 'Dos clics: esquinas del área; rejilla 8×8',
  },
  {
    id: 'gann-square',
    label: 'Cuadrado Gann',
    group: 'gann',
    icon: Square,
    available: true,
    hint: 'Dos clics: origen → esquina (cuadrado 1×1 en pantalla)',
  },
  {
    id: 'gann-square-fixed',
    label: 'Cuadrado fijo',
    group: 'gann',
    icon: Square,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'gann-fan',
    label: 'Abanico Gann',
    group: 'gann',
    icon: Hexagon,
    available: true,
    hint: 'Dos clics: origen → línea 1×1 de referencia',
  },
  {
    id: 'brush',
    label: 'Pincel',
    group: 'brushes',
    icon: Pencil,
    available: true,
    hint: 'Trazo libre a mano alzada',
  },
  {
    id: 'highlighter',
    label: 'Resaltador',
    group: 'brushes',
    icon: Highlighter,
    available: true,
    hint: 'Trazo ancho semitransparente',
  },
  {
    id: 'arrow-circle',
    label: 'Flecha en círculo',
    group: 'arrows',
    icon: CircleDot,
    available: true,
  },
  {
    id: 'arrow-up',
    label: 'Marcador arriba',
    group: 'arrows',
    icon: ArrowUpRight,
    available: true,
  },
  {
    id: 'arrow-down',
    label: 'Marcador abajo',
    group: 'arrows',
    icon: ArrowUpRight,
    available: true,
  },
  { id: 'rectangle', label: 'Rectángulo', group: 'shapes', icon: Square, available: true },
  {
    id: 'shape-rotated-rect',
    label: 'Rectángulo rotado',
    group: 'shapes',
    icon: Square,
    available: false,
    hint: 'Próximamente',
  },
  {
    id: 'text',
    label: 'Texto',
    group: 'text',
    icon: Type,
    available: true,
    hint: 'Clic para anclar texto en el gráfico',
  },
  {
    id: 'crosshair',
    label: 'Regla / medida',
    group: 'measure',
    icon: Ruler,
    available: true,
    hint: 'Medir distancia en precio y tiempo',
  },
];

export const DRAWING_TOOL_CATALOG: DrawingToolDefinition[] =
  DRAWING_TOOL_CATALOG_RAW.map(catalogEntry);

export const THREE_POINT_DRAW_TOOLS: ChartDrawTool[] = ['channel', 'pitchfork'];

export const TWO_POINT_DRAW_TOOLS: ChartDrawTool[] = [
  'line',
  'ray',
  'ext-line',
  'info-line',
  'trend-angle',
  'regression',
  'fibonacci',
  'fib-trend-ext',
  'fib-time-zone',
  'gann-fan',
  'gann-grid',
  'gann-square',
];

export function isActiveDrawTool(id: string): id is ChartDrawTool {
  return DRAWING_TOOL_CATALOG.some((item) => item.id === id && item.available);
}

export function findDrawingToolDefinition(id: string): DrawingToolDefinition | undefined {
  return DRAWING_TOOL_CATALOG.find((item) => item.id === id);
}

export function drawingToolShortLabel(id: string): string {
  return findDrawingToolDefinition(id)?.shortLabel ?? id;
}

export function activeToolInGroup(
  group: DrawingToolGroupId,
  tool: ChartDrawTool,
): DrawingToolDefinition | undefined {
  return DRAWING_TOOL_CATALOG.find((item) => item.id === tool && item.group === group);
}

export function toolBelongsToGroup(tool: ChartDrawTool | string, group: DrawingToolGroupId): boolean {
  return DRAWING_TOOL_CATALOG.some((item) => item.id === tool && item.group === group);
}

export function availableToolsInGroup(group: DrawingToolGroupId): DrawingToolDefinition[] {
  return DRAWING_TOOL_CATALOG.filter((item) => item.group === group && item.available && isActiveDrawTool(item.id));
}

export function groupForDrawTool(tool: ChartDrawTool | string): DrawingToolGroupId | null {
  return DRAWING_TOOL_CATALOG.find((item) => item.id === tool)?.group ?? null;
}

/** Grupos de la barra sin Cursor (Cursor va fijado arriba). */
export const DRAWING_TOOL_GROUPS_WITHOUT_CURSOR = DRAWING_TOOL_GROUPS.filter((g) => g.id !== 'cursor');

/** Herramienta a activar/mostrar en un grupo según favoritos y último uso. */
export function resolvePreferredToolForGroup(
  groupId: DrawingToolGroupId,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  const groupFavs = groupDrawToolFavorites(favorites, groupId).filter((tool) =>
    isActiveDrawTool(tool),
  );

  if (groupFavs.length === 1) {
    return groupFavs[0]!;
  }

  const last = lastByGroup[groupId];
  if (last && toolBelongsToGroup(last, groupId) && isActiveDrawTool(last)) {
    return last;
  }

  if (groupFavs.length > 1) {
    return groupFavs[0]!;
  }

  const fallback = availableToolsInGroup(groupId)[0]?.id;
  return fallback ? (fallback as ChartDrawTool) : null;
}

function isToolRepresentedOnGroupRail(
  tool: ChartDrawTool,
  groupId: DrawingToolGroupId,
  favorites: ChartDrawTool[],
): boolean {
  return (
    toolBelongsToGroup(tool, groupId) &&
    isActiveDrawTool(tool) &&
    !isExtraDrawToolFavorite(tool, favorites)
  );
}

/** Icono del botón de grupo: nunca duplica un favorito extra de la barra. */
export function resolveGroupRailIconTool(
  groupId: DrawingToolGroupId,
  activeTool: ChartDrawTool,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  if (isToolRepresentedOnGroupRail(activeTool, groupId, favorites)) {
    return activeTool;
  }

  const last = lastByGroup[groupId];
  if (last && isToolRepresentedOnGroupRail(last, groupId, favorites)) {
    return last;
  }

  const primary = primaryFavoriteForGroup(groupId, favorites);
  if (primary && isActiveDrawTool(primary)) {
    return primary;
  }

  return availableToolsInGroup(groupId)[0]?.id as ChartDrawTool | undefined ?? null;
}

/** Clic en botón de grupo: activa la herramienta del slot del grupo, no un favorito extra. */
export function resolveGroupRailActivateTool(
  groupId: DrawingToolGroupId,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  const last = lastByGroup[groupId];
  if (last && isToolRepresentedOnGroupRail(last, groupId, favorites)) {
    return last;
  }

  const primary = primaryFavoriteForGroup(groupId, favorites);
  if (primary && isActiveDrawTool(primary)) {
    return primary;
  }

  return availableToolsInGroup(groupId)[0]?.id as ChartDrawTool | undefined ?? null;
}

/** Resaltado del botón de grupo: solo si la herramienta activa no tiene botón propio en extras. */
export function isGroupRailToolActive(
  groupId: DrawingToolGroupId,
  activeTool: ChartDrawTool,
  favorites: ChartDrawTool[],
): boolean {
  return isToolRepresentedOnGroupRail(activeTool, groupId, favorites);
}

/** @deprecated Use resolveGroupRailIconTool */
export function resolveDisplayToolForGroup(
  groupId: DrawingToolGroupId,
  activeTool: ChartDrawTool,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  return resolveGroupRailIconTool(groupId, activeTool, lastByGroup, favorites);
}

/** @deprecated Use resolveGroupRailActivateTool */
export function resolveActivateToolForGroup(
  groupId: DrawingToolGroupId,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  return resolveGroupRailActivateTool(groupId, lastByGroup, favorites);
}

export function groupButtonIconTool(
  groupId: DrawingToolGroupId,
  activeTool: ChartDrawTool,
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>,
  favorites: ChartDrawTool[],
): ChartDrawTool | null {
  return resolveGroupRailIconTool(groupId, activeTool, lastByGroup, favorites);
}

/** Favoritos adicionales (más de uno por grupo) → acceso directo en la barra vertical. */
export function extraFavoriteToolsForRail(favorites: ChartDrawTool[]): ChartDrawTool[] {
  const seen = new Set<ChartDrawTool>();
  const result: ChartDrawTool[] = [];
  for (const tool of favorites) {
    if (!isActiveDrawTool(tool)) continue;
    if (!isExtraDrawToolFavorite(tool, favorites)) continue;
    if (seen.has(tool)) continue;
    seen.add(tool);
    result.push(tool);
  }
  return result;
}

export interface DrawingRailFamilyBlock {
  groupId: DrawingToolGroupId;
  extraTools: ChartDrawTool[];
  /** Principal + extras visibles en barra. */
  slotCount: number;
  /** Acotar familia cuando hay 2+ slots (incluye botón principal). */
  bracketed: boolean;
  /** Menú desplegable solo si la familia tiene más de una herramienta. */
  showMenu: boolean;
}

/** Bloques unificados por familia: slot principal + favoritos extra. */
export function drawingRailFamilyBlocks(favorites: ChartDrawTool[]): DrawingRailFamilyBlock[] {
  const extrasByGroup = new Map<DrawingToolGroupId, ChartDrawTool[]>();

  for (const tool of extraFavoriteToolsForRail(favorites)) {
    const groupId = drawToolGroup(tool) ?? groupForDrawTool(tool);
    if (!groupId) continue;
    const list = extrasByGroup.get(groupId) ?? [];
    if (!list.includes(tool)) list.push(tool);
    extrasByGroup.set(groupId, list);
  }

  for (const [groupId, tools] of extrasByGroup) {
    extrasByGroup.set(
      groupId,
      favorites.filter((tool) => tools.includes(tool)),
    );
  }

  return DRAWING_TOOL_GROUP_ORDER.map((groupId) => {
    const extraTools = extrasByGroup.get(groupId) ?? [];
    const slotCount = 1 + extraTools.length;
    return {
      groupId,
      extraTools,
      slotCount,
      bracketed: slotCount >= 2,
      showMenu: availableToolsInGroup(groupId).length > 1,
    };
  });
}

/** @deprecated Use drawingRailFamilyBlocks */
export interface ExtraFavoriteRailBlock {
  groupId: DrawingToolGroupId;
  tools: ChartDrawTool[];
  bracketed: boolean;
}

/** @deprecated Use drawingRailFamilyBlocks */
export function extraFavoriteRailBlocks(favorites: ChartDrawTool[]): ExtraFavoriteRailBlock[] {
  return drawingRailFamilyBlocks(favorites)
    .filter((block) => block.extraTools.length > 0)
    .map((block) => ({
      groupId: block.groupId,
      tools: block.extraTools,
      bracketed: block.bracketed,
    }));
}
