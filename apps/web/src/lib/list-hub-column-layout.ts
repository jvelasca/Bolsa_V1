import type {
  InstrumentListSummaryDto,
  ListHubColumnId,
  ListHubColumnLayoutItem,
  ListHubSortState,
  ListPanelConfig,
} from '@bolsa/shared';
import {
  ALL_LIST_HUB_COLUMNS,
  clampListHubColumnWidth,
  DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH,
  normalizeListHubColumnLayout,
} from '@bolsa/shared';

export const LIST_HUB_ROW_EXPAND_WIDTH_PX = 28;
export const LIST_HUB_ROW_CHART_MEMBERSHIP_WIDTH_PX = 18;
export const LIST_HUB_HEADER_GRIP_INSET_PX = 14;

/** Layout del documento (orden / visibilidad). Anchos de UI: `list-chrome-layout-store`. */
export function resolveListHubColumnLayout(listConfig: ListPanelConfig): ListHubColumnLayoutItem[] {
  return normalizeListHubColumnLayout(listConfig.hubColumnLayout);
}

export function resolveListHubRowActionsWidth(listConfig: ListPanelConfig): number {
  return clampListHubRowActionsWidth(listConfig.hubRowActionsWidth ?? DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH);
}

export function resolveListHubSort(listConfig: ListPanelConfig): ListHubSortState {
  return listConfig.hubSort ?? { column: 'name', direction: 'asc' };
}

export function patchListHubColumnLayout(
  _listConfig: ListPanelConfig,
  layout: ListHubColumnLayoutItem[],
): Partial<ListPanelConfig> {
  return { hubColumnLayout: layout };
}

export function toggleListHubColumnInLayout(
  layout: ListHubColumnLayoutItem[],
  columnId: ListHubColumnId,
): ListHubColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
}

export function reorderListHubColumns(
  layout: ListHubColumnLayoutItem[],
  fromIndex: number,
  toIndex: number,
): ListHubColumnLayoutItem[] {
  const visible = layout.filter((column) => column.visible);
  const hidden = layout.filter((column) => !column.visible);
  const next = [...visible];
  const [moved] = next.splice(fromIndex, 1);
  if (!moved) return layout;
  next.splice(toIndex, 0, moved);
  return [...next, ...hidden];
}

export function reorderListHubColumnsById(
  layout: ListHubColumnLayoutItem[],
  fromId: ListHubColumnId,
  toId: ListHubColumnId,
): ListHubColumnLayoutItem[] {
  const visible = layout.filter((column) => column.visible);
  const fromIndex = visible.findIndex((column) => column.id === fromId);
  const toIndex = visible.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  return reorderListHubColumns(layout, fromIndex, toIndex);
}

export function clampListHubRowActionsWidth(width: number): number {
  return Math.min(140, Math.max(72, Math.round(width)));
}

export function resizeListHubColumn(
  layout: ListHubColumnLayoutItem[],
  columnId: ListHubColumnId,
  width: number,
): ListHubColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampListHubColumnWidth(width, columnId) }
      : column,
  );
}

export function getVisibleListHubColumnLayout(
  layout: ListHubColumnLayoutItem[],
): ListHubColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

function flexibleHubColumnId(visibleColumns: ListHubColumnLayoutItem[]): ListHubColumnId | null {
  if (visibleColumns.some((column) => column.id === 'name')) return 'name';
  return visibleColumns.at(-1)?.id ?? null;
}

function hubColumnGridTrack(
  column: ListHubColumnLayoutItem,
  flexId: ListHubColumnId | null,
): string {
  if (column.id === flexId) {
    return `minmax(${column.width}px, 1fr)`;
  }
  return `minmax(${column.width}px, ${column.width}px)`;
}

export function buildListHubDataGridTemplate(visibleColumns: ListHubColumnLayoutItem[]): string {
  if (visibleColumns.length === 0) return 'minmax(0, 1fr)';
  const flexId = flexibleHubColumnId(visibleColumns);
  return visibleColumns.map((column) => hubColumnGridTrack(column, flexId)).join(' ');
}

export function buildListHubRowGridTemplate(
  visibleColumns: ListHubColumnLayoutItem[],
  rowActionsWidth: number,
): string {
  if (visibleColumns.length === 0) {
    return `${LIST_HUB_ROW_EXPAND_WIDTH_PX}px minmax(0, 1fr) ${rowActionsWidth}px`;
  }
  return `${LIST_HUB_ROW_EXPAND_WIDTH_PX}px ${buildListHubDataGridTemplate(visibleColumns)} ${rowActionsWidth}px`;
}

export function isNumericListHubColumn(columnId: ListHubColumnId): boolean {
  return columnId === 'count';
}

export function isCenteredListHubColumn(columnId: ListHubColumnId): boolean {
  return columnId === 'count' || columnId === 'carousel';
}

export function isSortableListHubColumn(_columnId: ListHubColumnId): boolean {
  return true;
}

export function listHubColumnContentClass(
  columnId: ListHubColumnId,
  variant: 'header' | 'data',
): string {
  const parts = ['min-w-0 text-[10px]'];
  if (columnId === 'name') parts.push('truncate font-medium');
  if (columnId === 'type') parts.push('truncate text-muted-foreground');
  if (columnId === 'count') parts.push('tabular-nums text-muted-foreground');
  if (columnId === 'carousel') parts.push('text-muted-foreground');
  if (variant === 'header') parts.push('text-muted-foreground');
  return parts.join(' ');
}

export function sortListSummaries(
  lists: InstrumentListSummaryDto[],
  sort: ListHubSortState,
  metaById: Record<string, { typeLabel: string; carouselPinned?: boolean }>,
): InstrumentListSummaryDto[] {
  const factor = sort.direction === 'asc' ? 1 : -1;
  return [...lists].sort((a, b) => {
    if (sort.column === 'count') {
      const byCount = (a.itemCount - b.itemCount) * factor;
      if (byCount !== 0) return byCount;
      return a.name.localeCompare(b.name, 'es');
    }
    if (sort.column === 'type') {
      const left = metaById[a.id]?.typeLabel ?? '';
      const right = metaById[b.id]?.typeLabel ?? '';
      const byType = left.localeCompare(right, 'es') * factor;
      if (byType !== 0) return byType;
      return a.name.localeCompare(b.name, 'es');
    }
    if (sort.column === 'carousel') {
      const left = metaById[a.id]?.carouselPinned ? 1 : 0;
      const right = metaById[b.id]?.carouselPinned ? 1 : 0;
      const byCarousel = (right - left) * factor;
      if (byCarousel !== 0) return byCarousel;
      return a.name.localeCompare(b.name, 'es');
    }
    return a.name.localeCompare(b.name, 'es') * factor;
  });
}

export function toggleListHubFavoriteColumn(
  listConfig: ListPanelConfig,
  columnId: ListHubColumnId,
): ListHubColumnId[] {
  const current = new Set(listConfig.hubFavoriteColumnIds ?? ['name', 'count']);
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);
  return ALL_LIST_HUB_COLUMNS.filter((id) => current.has(id));
}
