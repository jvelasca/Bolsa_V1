import type { ListColumnId, ListColumnLayoutItem, ListPanelConfig } from '@bolsa/shared';
import {
  ALL_LIST_COLUMNS,
  clampListColumnWidth,
  clampListRowActionsWidth,
  normalizeColumnLayout,
  resolveListRowActionsWidth,
  visibleListColumns,
} from '@bolsa/shared';

export const LIST_ROW_EXPAND_WIDTH_PX = 28;
export const DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX = resolveListRowActionsWidth(undefined);
/** Espacio reservado para el grip de reordenar en cabecera (alinea texto con filas). */
export const LIST_HEADER_GRIP_INSET_PX = 14;

export function isNumericListColumn(columnId: ListColumnId): boolean {
  return columnId === 'lastClose' || columnId === 'changePct';
}

export function isCenteredListColumn(columnId: ListColumnId): boolean {
  return columnId === 'syncStatus';
}

export function listColumnContentClass(
  columnId: ListColumnId,
  variant: 'header' | 'data',
): string {
  const parts = [listColumnCellClass(columnId), columnAlignClass(columnId)];
  if (!isCenteredListColumn(columnId)) parts.push('pl-4');
  if (isNumericListColumn(columnId)) parts.push('tabular-nums');
  if (variant === 'header' && isNumericListColumn(columnId)) parts.push('font-medium');
  if (variant === 'data' && columnId === 'symbol') parts.push('text-xs font-semibold');
  if (variant === 'data' && columnId === 'name') parts.push('text-muted-foreground');
  if (isCenteredListColumn(columnId)) parts.push('flex justify-center');
  return parts.join(' ');
}

export function getVisibleColumnLayout(layout: ListColumnLayoutItem[]): ListColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

function flexibleColumnId(visibleColumns: ListColumnLayoutItem[]): ListColumnId | null {
  if (visibleColumns.some((column) => column.id === 'name')) return 'name';
  return visibleColumns.at(-1)?.id ?? null;
}

export function buildListRowDataGridTemplate(visibleColumns: ListColumnLayoutItem[]): string {
  if (visibleColumns.length === 0) return 'minmax(0, 1fr)';
  const flexId = flexibleColumnId(visibleColumns);
  return visibleColumns
    .map((column) =>
      column.id === flexId
        ? `minmax(${column.width}px, 1fr)`
        : `minmax(0, ${column.width}px)`,
    )
    .join(' ');
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

export function resolveListRowActionsWidthFromConfig(listConfig: ListPanelConfig): number {
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
    column.id === columnId ? { ...column, width: clampListColumnWidth(width) } : column,
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
  if (columnId === 'syncStatus') return 'text-center';
  if (columnId === 'symbol' || columnId === 'name') return 'text-left';
  return 'text-right';
}

/** Padding horizontal por columna para separar etiquetas (p. ej. nombre ↔ barras). */
export function listColumnCellClass(columnId: ListColumnId): string {
  switch (columnId) {
    case 'symbol':
      return 'px-1.5';
    case 'name':
      return 'px-2 pr-3';
    case 'syncStatus':
      return 'px-1 text-center';
    default:
      return 'px-2';
  }
}

export function resolveListFavoriteColumnIds(
  listConfig: ListPanelConfig,
  listId: string,
): ListColumnId[] {
  return listConfig.favoriteColumnIdsByListId?.[listId] ?? ['symbol', 'lastClose'];
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
