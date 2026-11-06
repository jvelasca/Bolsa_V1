import type {
  ListColumnId,
  ListColumnLayoutItem,
  ListPanelConfig,
} from "@bolsa/shared";
import {
  ALL_LIST_COLUMNS,
  clampListColumnWidth,
  clampListRowActionsWidth,
  MIN_LIST_COLUMN_WIDTH,
  normalizeColumnLayout,
  resolveListRowActionsWidth,
  visibleListColumns,
} from "@bolsa/shared";

export const LIST_ROW_EXPAND_WIDTH_PX = 28;
/** Ancho fijo de la columna de check (cabecera y filas alineadas). */
export const LIST_ROW_SELECT_WIDTH_PX = 18;
export const DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX =
  resolveListRowActionsWidth(undefined);

/** Padding horizontal de la fila (`px-1`): se suma al ancho mínimo de la misma. */
export const LIST_ROW_HORIZONTAL_PADDING_PX = 8;

/** Gutter izquierdo: check opcional + expand/chevron. */
export function listRowLeftGutterWidthPx(selectEnabled: boolean): number {
  return selectEnabled
    ? LIST_ROW_SELECT_WIDTH_PX + LIST_ROW_EXPAND_WIDTH_PX
    : LIST_ROW_EXPAND_WIDTH_PX;
}
/** Espacio reservado para el grip de reordenar en cabecera (alinea texto con filas). */
export const LIST_HEADER_GRIP_INSET_PX = 14;

export function isNumericListColumn(columnId: ListColumnId): boolean {
  return (
    columnId === "lastClose" ||
    columnId === "changePct" ||
    columnId === "ioScore" ||
    columnId === "taScore" ||
    columnId === "faScore" ||
    columnId === "dictamenStars"
  );
}

export function isCenteredListColumn(columnId: ListColumnId): boolean {
  return (
    columnId === "syncStatus" ||
    columnId === "processStatus" ||
    columnId === "dictamenStars"
  );
}

export function listColumnContentClass(
  columnId: ListColumnId,
  variant: "header" | "data",
): string {
  const parts = [listColumnCellClass(columnId), columnAlignClass(columnId)];
  if (!isCenteredListColumn(columnId)) parts.push("pl-4");
  if (isNumericListColumn(columnId)) parts.push("tabular-nums");
  if (variant === "header" && isNumericListColumn(columnId))
    parts.push("font-medium");
  if (variant === "data" && columnId === "symbol")
    parts.push("text-xs font-semibold");
  if (variant === "data" && columnId === "name")
    parts.push("text-muted-foreground");
  if (isCenteredListColumn(columnId)) parts.push("flex justify-center");
  return parts.join(" ");
}

export function getVisibleColumnLayout(
  layout: ListColumnLayoutItem[],
): ListColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

function flexibleColumnId(
  visibleColumns: ListColumnLayoutItem[],
): ListColumnId | null {
  if (visibleColumns.some((column) => column.id === "name")) return "name";
  return visibleColumns.at(-1)?.id ?? null;
}

export function buildListRowDataGridTemplate(
  visibleColumns: ListColumnLayoutItem[],
): string {
  if (visibleColumns.length === 0) return "minmax(0, 1fr)";
  const flexId = flexibleColumnId(visibleColumns);
  // Las pistas no flexibles llevan su ancho exacto: si no caben, la lista scrollea
  // en horizontal en vez de aplastarlas a 0 px (que dejaba la cabecera ilegible).
  return visibleColumns
    .map((column) =>
      column.id === flexId
        ? `minmax(${column.width}px, 1fr)`
        : `${clampListColumnWidth(column.width)}px`,
    )
    .join(" ");
}

/**
 * Ancho mínimo de una fila completa: gutter (check + expand) + columnas + acciones.
 * Se aplica como `minWidth` para que el contenedor `overflow-auto` scrollee.
 */
export function listRowMinWidthPx(
  visibleColumns: ListColumnLayoutItem[],
  rowActionsWidth = DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX,
  selectEnabled = false,
): number {
  const gutters = listRowLeftGutterWidthPx(selectEnabled);
  const actions = clampListRowActionsWidth(rowActionsWidth);
  const columns = visibleColumns.reduce(
    (sum, column) => sum + clampListColumnWidth(column.width),
    0,
  );
  return gutters + columns + actions + LIST_ROW_HORIZONTAL_PADDING_PX;
}

/**
 * Reparte el ancho disponible entre las columnas visibles sin bajar del mínimo
 * (`MIN_LIST_COLUMN_WIDTH`). Si no cabe ni con mínimos, devuelve los mínimos
 * (la lista ya scrollea en horizontal).
 */
export function fitColumnWidthsToAvailable(
  visibleColumns: ListColumnLayoutItem[],
  availablePx: number,
): ListColumnLayoutItem[] {
  const count = visibleColumns.length;
  if (count === 0) return visibleColumns;

  const widths = visibleColumns.map((column) =>
    clampListColumnWidth(column.width),
  );
  const currentTotal = widths.reduce((sum, width) => sum + width, 0);
  const target = Math.floor(availablePx);
  if (target <= 0 || target >= currentTotal) return visibleColumns;

  const floorTotal = MIN_LIST_COLUMN_WIDTH * count;
  if (target <= floorTotal) {
    return visibleColumns.map((column) => ({
      ...column,
      width: MIN_LIST_COLUMN_WIDTH,
    }));
  }

  // Reparto proporcional del excedente sobre el mínimo: garantiza el suelo por columna.
  const caps = widths.map((width) =>
    Math.max(0, width - MIN_LIST_COLUMN_WIDTH),
  );
  const capTotal = caps.reduce((sum, cap) => sum + cap, 0);
  const remaining = target - floorTotal;

  return visibleColumns.map((column, index) => {
    const extra =
      capTotal > 0 ? Math.floor((caps[index]! / capTotal) * remaining) : 0;
    return {
      ...column,
      width: clampListColumnWidth(MIN_LIST_COLUMN_WIDTH + extra),
    };
  });
}

export function buildListRowGridTemplate(
  visibleColumns: ListColumnLayoutItem[],
  rowActionsWidth = DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX,
): string {
  const actionsWidth = clampListRowActionsWidth(rowActionsWidth);
  if (visibleColumns.length === 0) {
    return `${LIST_ROW_EXPAND_WIDTH_PX}px minmax(0, 1fr) ${actionsWidth}px`;
  }
  return `${LIST_ROW_EXPAND_WIDTH_PX}px ${buildListRowDataGridTemplate(visibleColumns)} ${actionsWidth}px`;
}

export function resolveListRowActionsWidthFromConfig(
  listConfig: ListPanelConfig,
): number {
  return resolveListRowActionsWidth(listConfig.rowActionsWidth);
}

/** Layout del documento (orden / visibilidad). Anchos de UI: `list-chrome-layout-store`. */
export function resolveListColumnLayout(
  listConfig: ListPanelConfig,
  listId: string,
): ListColumnLayoutItem[] {
  const stored = listConfig.columnLayoutsByListId?.[listId];
  const legacy =
    listConfig.apiListId === listId ? listConfig.columnLayout : undefined;
  return normalizeColumnLayout(stored ?? legacy, listConfig.columns);
}

export function patchListColumnLayout(
  listConfig: ListPanelConfig,
  listId: string,
  layout: ListColumnLayoutItem[],
): Partial<ListPanelConfig> {
  const columnLayoutsByListId = {
    ...(listConfig.columnLayoutsByListId ?? {}),
    [listId]: layout,
  };
  const patch: Partial<ListPanelConfig> = { columnLayoutsByListId };
  if (listConfig.apiListId === listId) {
    patch.columnLayout = layout;
    patch.columns = visibleListColumns(layout);
  }
  return patch;
}

export function resizeColumnInLayout(
  layout: ListColumnLayoutItem[],
  columnId: ListColumnId,
  width: number,
): ListColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampListColumnWidth(width) }
      : column,
  );
}

export function reorderColumnsInLayout(
  layout: ListColumnLayoutItem[],
  fromId: ListColumnId,
  toId: ListColumnId,
): ListColumnLayoutItem[] {
  const fromIndex = layout.findIndex((column) => column.id === fromId);
  const toIndex = layout.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  const next = [...layout];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved!);
  return next;
}

export function toggleColumnInLayout(
  layout: ListColumnLayoutItem[],
  columnId: ListColumnId,
): ListColumnLayoutItem[] {
  const next = layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
  if (!next.some((column) => column.visible)) return layout;
  return next;
}

export function columnAlignClass(columnId: ListColumnId): string {
  if (
    columnId === "syncStatus" ||
    columnId === "processStatus" ||
    columnId === "dictamenStars"
  ) {
    return "text-center";
  }
  if (
    columnId === "symbol" ||
    columnId === "name" ||
    columnId === "recStance"
  ) {
    return "text-left";
  }
  return "text-right";
}

/** Padding horizontal por columna para separar etiquetas (p. ej. nombre ↔ barras). */
export function listColumnCellClass(columnId: ListColumnId): string {
  switch (columnId) {
    case "symbol":
      return "px-1.5";
    case "name":
      return "px-2 pr-3";
    case "syncStatus":
    case "processStatus":
      return "px-1 text-center";
    case "lastLabAt":
    case "lastCoreRAt":
      return "px-1.5";
    default:
      return "px-2";
  }
}

export function resolveListFavoriteColumnIds(
  listConfig: ListPanelConfig,
  listId: string,
): ListColumnId[] {
  return (
    listConfig.favoriteColumnIdsByListId?.[listId] ?? ["symbol", "lastClose"]
  );
}

export function patchListFavoriteColumn(
  listConfig: ListPanelConfig,
  listId: string,
  columnId: ListColumnId,
): Partial<ListPanelConfig> {
  const current = new Set(resolveListFavoriteColumnIds(listConfig, listId));
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);

  const favorites = ALL_LIST_COLUMNS.filter((id) => current.has(id));
  return {
    favoriteColumnIdsByListId: {
      ...(listConfig.favoriteColumnIdsByListId ?? {}),
      [listId]: favorites,
    },
  };
}
