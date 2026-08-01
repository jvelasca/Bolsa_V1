/** Pestañas del inspector (Config) que pueden fijarse en la barra de datos del gráfico. */
export type ChartInspectorBarShortcutId =
  | 'layers'
  | 'series'
  | 'objects'
  | 'styles'
  | 'context';

export const CHART_INSPECTOR_BAR_SHORTCUT_IDS: ChartInspectorBarShortcutId[] = [
  'layers',
  'series',
  'objects',
  'styles',
  'context',
];

/** Orden de iconos en la barra (de izquierda a derecha). */
export const CHART_INSPECTOR_BAR_SHORTCUT_ORDER: ChartInspectorBarShortcutId[] = [
  ...CHART_INSPECTOR_BAR_SHORTCUT_IDS,
];

export const CHART_INSPECTOR_BAR_SHORTCUT_LABELS: Record<ChartInspectorBarShortcutId, string> = {
  layers: 'Capas',
  series: 'Estilo de barra',
  objects: 'Objetos',
  styles: 'Canvas',
  context: 'Selección',
};

export const CHART_INSPECTOR_BAR_SHORTCUT_BAR_TITLES: Record<ChartInspectorBarShortcutId, string> = {
  layers: 'Capas (indicadores) — inspector Config → Capas',
  series: 'Estilo de barra — inspector Config → Estilo',
  objects: 'Objetos gráficos — inspector Config → Objetos',
  styles: 'Estilos del canvas (rejilla, colores) — inspector Config → Canvas',
  context: 'Selección bajo el cursor — inspector Config → Selección',
};

/** Por defecto la barra queda limpia; el usuario fija atajos con estrella en el inspector. */
export const DEFAULT_CHART_INSPECTOR_BAR_SHORTCUT_FAVORITES: ChartInspectorBarShortcutId[] = [];

const SHORTCUT_ID_SET = new Set<string>(CHART_INSPECTOR_BAR_SHORTCUT_IDS);

export function isChartInspectorBarShortcutId(
  value: string,
): value is ChartInspectorBarShortcutId {
  return SHORTCUT_ID_SET.has(value);
}

export function normalizeInspectorBarShortcutFavorites(
  raw?: ChartInspectorBarShortcutId[] | null,
): ChartInspectorBarShortcutId[] {
  if (raw == null) return [];
  const seen = new Set<ChartInspectorBarShortcutId>();
  const ordered: ChartInspectorBarShortcutId[] = [];
  for (const id of CHART_INSPECTOR_BAR_SHORTCUT_ORDER) {
    if (raw.includes(id) && !seen.has(id)) {
      seen.add(id);
      ordered.push(id);
    }
  }
  return ordered;
}

export function toggleInspectorBarShortcutFavoriteList(
  favorites: ChartInspectorBarShortcutId[],
  shortcutId: ChartInspectorBarShortcutId,
): ChartInspectorBarShortcutId[] {
  if (favorites.includes(shortcutId)) {
    return favorites.filter((id) => id !== shortcutId);
  }
  const next = [...favorites, shortcutId];
  return CHART_INSPECTOR_BAR_SHORTCUT_ORDER.filter((id) => next.includes(id));
}

export function orderInspectorBarShortcutFavorites(
  favorites: ChartInspectorBarShortcutId[],
): ChartInspectorBarShortcutId[] {
  const set = new Set(favorites);
  return CHART_INSPECTOR_BAR_SHORTCUT_ORDER.filter((id) => set.has(id));
}
