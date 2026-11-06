/** Columnas del panel hub de listas (pestaña Listas). Distinto de columnas de instrumentos. */
export type ListHubColumnId = "name" | "type" | "count" | "carousel";

export type WatchlistPanelTab = "lists" | "values";

export interface ListHubColumnLayoutItem {
  id: ListHubColumnId;
  width: number;
  visible: boolean;
}

export interface ListHubSortState {
  column: ListHubColumnId;
  direction: "asc" | "desc";
}

export const LIST_HUB_COLUMN_LABELS: Record<ListHubColumnId, string> = {
  name: "Lista",
  type: "Tipo",
  count: "Valores",
  carousel: "Carrusel",
};

export const ALL_LIST_HUB_COLUMNS: ListHubColumnId[] = [
  "name",
  "type",
  "count",
  "carousel",
];

export const DEFAULT_LIST_HUB_COLUMN_WIDTHS: Record<ListHubColumnId, number> = {
  name: 100,
  type: 52,
  count: 64,
  carousel: 40,
};

export const MIN_LIST_HUB_COLUMN_WIDTH = 36;
export const MAX_LIST_HUB_COLUMN_WIDTH = 240;
export const DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH = 100;
/** Hasta 4 iconos de 24 px = 96 px + bordes: el mínimo debe caber sin recortar. */
export const MIN_LIST_HUB_ROW_ACTIONS_WIDTH = 78;

/** Ancho mínimo por columna para que la cabecera siga siendo legible al redimensionar. */
export const MIN_LIST_HUB_COLUMN_WIDTHS: Record<ListHubColumnId, number> = {
  name: 36,
  type: 44,
  count: 52,
  carousel: 36,
};

export function clampListHubColumnWidth(
  width: number,
  columnId?: ListHubColumnId,
): number {
  const min = columnId
    ? MIN_LIST_HUB_COLUMN_WIDTHS[columnId]
    : MIN_LIST_HUB_COLUMN_WIDTH;
  return Math.min(MAX_LIST_HUB_COLUMN_WIDTH, Math.max(min, Math.round(width)));
}

export function buildDefaultListHubColumnLayout(
  columnIds: ListHubColumnId[] = ["name", "type", "count", "carousel"],
): ListHubColumnLayoutItem[] {
  const visibleSet = new Set(columnIds);
  const ordered: ListHubColumnLayoutItem[] = [];

  for (const id of columnIds) {
    ordered.push({
      id,
      width: DEFAULT_LIST_HUB_COLUMN_WIDTHS[id],
      visible: true,
    });
  }

  for (const id of ALL_LIST_HUB_COLUMNS) {
    if (!visibleSet.has(id)) {
      ordered.push({
        id,
        width: DEFAULT_LIST_HUB_COLUMN_WIDTHS[id],
        visible: false,
      });
    }
  }

  return ordered;
}

export function visibleListHubColumns(
  layout: ListHubColumnLayoutItem[],
): ListHubColumnId[] {
  return layout.filter((column) => column.visible).map((column) => column.id);
}

export function normalizeListHubColumnLayout(
  stored: ListHubColumnLayoutItem[] | undefined,
): ListHubColumnLayoutItem[] {
  if (!stored?.length) return buildDefaultListHubColumnLayout();

  const byId = new Map<ListHubColumnId, ListHubColumnLayoutItem>();
  for (const item of stored) {
    if (!ALL_LIST_HUB_COLUMNS.includes(item.id)) continue;
    byId.set(item.id, {
      id: item.id,
      width: clampListHubColumnWidth(
        item.width ?? DEFAULT_LIST_HUB_COLUMN_WIDTHS[item.id],
        item.id,
      ),
      visible: item.visible ?? true,
    });
  }
  if (byId.size === 0) return buildDefaultListHubColumnLayout();

  // Se preserva el orden guardado (el usuario puede reordenar arrastrando);
  // las columnas nuevas del producto se añaden al final con su ancho por defecto.
  const defaults = buildDefaultListHubColumnLayout();
  const ordered: ListHubColumnLayoutItem[] = [];
  for (const item of stored) {
    const column = byId.get(item.id);
    if (!column) continue;
    ordered.push(column);
    byId.delete(item.id);
  }
  for (const column of defaults) {
    const pending = byId.get(column.id);
    if (pending) ordered.push(pending);
    else if (!ordered.some((existing) => existing.id === column.id))
      ordered.push(column);
  }
  return ordered;
}
