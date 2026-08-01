import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';
import type { ListColumnId, ListColumnLayoutItem, ListSortState } from '@bolsa/shared';
import {
  buildListRowDataGridTemplate,
  buildListRowGridTemplate,
  getVisibleColumnLayout,
  patchListColumnLayout,
  reorderColumnsInLayout,
  resolveListColumnLayout,
  resolveListRowActionsWidthFromConfig,
  toggleColumnInLayout,
} from '@/lib/list-column-layout';
import {
  layoutForServerSync,
  mergeListColumnWidths,
  resolveLocalRowActionsWidth,
  useListChromeLayoutStore,
} from '@/stores/list-chrome-layout-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

interface ListColumnLayoutContextValue {
  listId: string;
  layout: ListColumnLayoutItem[];
  visibleColumns: ListColumnLayoutItem[];
  gridTemplateColumns: string;
  dataGridTemplateColumns: string;
  rowActionsWidth: number;
  sortState: ListSortState | undefined;
  persistLayout: (layout: ListColumnLayoutItem[], save?: boolean) => void;
  resizeColumn: (columnId: ListColumnId, width: number) => void;
  resizeRowActionsWidth: (width: number) => void;
  reorderColumns: (fromId: ListColumnId, toId: ListColumnId) => void;
  toggleColumn: (columnId: ListColumnId) => void;
  cycleSort: (columnId: ListColumnId) => void;
  commitLayout: () => void;
}

const ListColumnLayoutContext = createContext<ListColumnLayoutContextValue | null>(null);

export function ListColumnLayoutProvider({
  listId,
  children,
}: {
  listId: string;
  children: ReactNode;
}) {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);

  const localWidths = useListChromeLayoutStore((state) => state.widthsByListId[listId]);
  const localRowActions = useListChromeLayoutStore((state) => state.rowActionsWidth);
  const seedListWidthsIfNeeded = useListChromeLayoutStore((state) => state.seedListWidthsIfNeeded);
  const seedRowActionsIfNeeded = useListChromeLayoutStore((state) => state.seedRowActionsIfNeeded);
  const setListColumnWidth = useListChromeLayoutStore((state) => state.setListColumnWidth);
  const setRowActionsWidth = useListChromeLayoutStore((state) => state.setRowActionsWidth);

  const serverLayout = useMemo(
    () => resolveListColumnLayout(listConfig, listId),
    [listConfig, listId],
  );

  const serverRowActionsWidth = useMemo(
    () => resolveListRowActionsWidthFromConfig(listConfig),
    [listConfig],
  );

  useEffect(() => {
    seedListWidthsIfNeeded(listId, serverLayout);
    seedRowActionsIfNeeded(serverRowActionsWidth);
  }, [listId, seedListWidthsIfNeeded, seedRowActionsIfNeeded, serverLayout, serverRowActionsWidth]);

  const layout = useMemo(
    () => mergeListColumnWidths(listId, serverLayout),
    [listId, localWidths, serverLayout],
  );

  const visibleColumns = useMemo(() => getVisibleColumnLayout(layout), [layout]);

  const rowActionsWidth = useMemo(
    () => resolveLocalRowActionsWidth(serverRowActionsWidth),
    [localRowActions, serverRowActionsWidth],
  );

  const gridTemplateColumns = useMemo(
    () => buildListRowGridTemplate(visibleColumns, rowActionsWidth),
    [visibleColumns, rowActionsWidth],
  );

  const dataGridTemplateColumns = useMemo(
    () => buildListRowDataGridTemplate(visibleColumns),
    [visibleColumns],
  );

  const sortState = listConfig.sortByListId?.[listId];

  /** Orden / visibilidad → servidor (anchos por defecto). Anchos reales van en chrome local. */
  const persistLayout = useCallback(
    (next: ListColumnLayoutItem[], shouldSave = true) => {
      updateListConfig(patchListColumnLayout(listConfig, listId, layoutForServerSync(next)));
      if (shouldSave) save();
    },
    [listConfig, listId, save, updateListConfig],
  );

  const commitLayout = useCallback(() => {
    // Anchos: solo localStorage. No marcar el espacio como dirty.
  }, []);

  const resizeColumn = useCallback(
    (columnId: ListColumnId, width: number) => {
      setListColumnWidth(listId, columnId, width);
    },
    [listId, setListColumnWidth],
  );

  const reorderColumns = useCallback(
    (fromId: ListColumnId, toId: ListColumnId) => {
      persistLayout(reorderColumnsInLayout(layout, fromId, toId));
    },
    [layout, persistLayout],
  );

  const toggleColumn = useCallback(
    (columnId: ListColumnId) => {
      persistLayout(toggleColumnInLayout(layout, columnId));
    },
    [layout, persistLayout],
  );

  const cycleSort = useCallback(
    (columnId: ListColumnId) => {
      const current = listConfig.sortByListId?.[listId];
      let next: ListSortState | undefined;
      if (!current || current.column !== columnId) {
        next = { column: columnId, direction: 'asc' };
      } else if (current.direction === 'asc') {
        next = { column: columnId, direction: 'desc' };
      } else {
        next = undefined;
      }
      const sortByListId = { ...(listConfig.sortByListId ?? {}) };
      if (next) {
        sortByListId[listId] = next;
      } else {
        delete sortByListId[listId];
      }
      updateListConfig({ ...listConfig, sortByListId });
      save();
    },
    [listConfig, listId, save, updateListConfig],
  );

  const resizeRowActionsWidth = useCallback(
    (width: number) => {
      setRowActionsWidth(width);
    },
    [setRowActionsWidth],
  );

  const value = useMemo(
    () => ({
      listId,
      layout,
      visibleColumns,
      gridTemplateColumns,
      dataGridTemplateColumns,
      rowActionsWidth,
      sortState,
      persistLayout,
      resizeColumn,
      resizeRowActionsWidth,
      reorderColumns,
      toggleColumn,
      cycleSort,
      commitLayout,
    }),
    [
      commitLayout,
      cycleSort,
      dataGridTemplateColumns,
      gridTemplateColumns,
      layout,
      listId,
      persistLayout,
      reorderColumns,
      resizeColumn,
      resizeRowActionsWidth,
      rowActionsWidth,
      sortState,
      toggleColumn,
      visibleColumns,
    ],
  );

  return (
    <ListColumnLayoutContext.Provider value={value}>{children}</ListColumnLayoutContext.Provider>
  );
}

export function useListColumnLayoutContext() {
  const context = useContext(ListColumnLayoutContext);
  if (!context) {
    throw new Error('useListColumnLayoutContext debe usarse dentro de ListColumnLayoutProvider');
  }
  return context;
}
