import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';
import type { ListHubColumnId, ListHubColumnLayoutItem, ListHubSortState } from '@bolsa/shared';
import {
  buildListHubDataGridTemplate,
  buildListHubRowGridTemplate,
  getVisibleListHubColumnLayout,
  isSortableListHubColumn,
  patchListHubColumnLayout,
  reorderListHubColumnsById,
  resolveListHubColumnLayout,
  resolveListHubRowActionsWidth,
  resolveListHubSort,
  toggleListHubColumnInLayout,
} from '@/lib/list-hub-column-layout';
import {
  hubLayoutForServerSync,
  mergeHubColumnWidths,
  resolveLocalHubRowActionsWidth,
  useListChromeLayoutStore,
} from '@/stores/list-chrome-layout-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

interface ListHubColumnLayoutContextValue {
  layout: ListHubColumnLayoutItem[];
  visibleColumns: ListHubColumnLayoutItem[];
  gridTemplateColumns: string;
  dataGridTemplateColumns: string;
  rowActionsWidth: number;
  sortState: ListHubSortState;
  persistLayout: (layout: ListHubColumnLayoutItem[], save?: boolean) => void;
  resizeColumn: (columnId: ListHubColumnId, width: number) => void;
  resizeRowActionsWidth: (width: number) => void;
  reorderColumns: (fromId: ListHubColumnId, toId: ListHubColumnId) => void;
  toggleColumn: (columnId: ListHubColumnId) => void;
  cycleSort: (columnId: ListHubColumnId) => void;
  commitLayout: () => void;
}

const ListHubColumnLayoutContext = createContext<ListHubColumnLayoutContextValue | null>(null);

export function ListHubColumnLayoutProvider({ children }: { children: ReactNode }) {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);

  const hubWidths = useListChromeLayoutStore((state) => state.hubWidths);
  const hubRowActionsWidth = useListChromeLayoutStore((state) => state.hubRowActionsWidth);
  const hubSeeded = useListChromeLayoutStore((state) => state.hubSeeded);
  const seedHubIfNeeded = useListChromeLayoutStore((state) => state.seedHubIfNeeded);
  const setHubColumnWidth = useListChromeLayoutStore((state) => state.setHubColumnWidth);
  const setHubRowActionsWidth = useListChromeLayoutStore((state) => state.setHubRowActionsWidth);

  const serverLayout = useMemo(() => resolveListHubColumnLayout(listConfig), [listConfig]);
  const serverRowActionsWidth = useMemo(
    () => resolveListHubRowActionsWidth(listConfig),
    [listConfig],
  );

  useEffect(() => {
    seedHubIfNeeded(serverLayout, serverRowActionsWidth);
  }, [seedHubIfNeeded, serverLayout, serverRowActionsWidth]);

  const layout = useMemo(
    () => mergeHubColumnWidths(serverLayout),
    [hubSeeded, hubWidths, serverLayout],
  );
  const visibleColumns = useMemo(() => getVisibleListHubColumnLayout(layout), [layout]);
  const rowActionsWidth = useMemo(
    () => resolveLocalHubRowActionsWidth(serverRowActionsWidth),
    [hubRowActionsWidth, serverRowActionsWidth],
  );
  const gridTemplateColumns = useMemo(
    () => buildListHubRowGridTemplate(visibleColumns, rowActionsWidth),
    [visibleColumns, rowActionsWidth],
  );
  const dataGridTemplateColumns = useMemo(
    () => buildListHubDataGridTemplate(visibleColumns),
    [visibleColumns],
  );
  const sortState = resolveListHubSort(listConfig);

  const persistLayout = useCallback(
    (next: ListHubColumnLayoutItem[], shouldSave = true) => {
      updateListConfig(patchListHubColumnLayout(listConfig, hubLayoutForServerSync(next)));
      if (shouldSave) save();
    },
    [listConfig, save, updateListConfig],
  );

  const commitLayout = useCallback(() => {
    // Anchos: solo localStorage.
  }, []);

  const resizeColumn = useCallback(
    (columnId: ListHubColumnId, width: number) => {
      setHubColumnWidth(columnId, width);
    },
    [setHubColumnWidth],
  );

  const resizeRowActionsWidth = useCallback(
    (width: number) => {
      setHubRowActionsWidth(width);
    },
    [setHubRowActionsWidth],
  );

  const reorderColumns = useCallback(
    (fromId: ListHubColumnId, toId: ListHubColumnId) => {
      persistLayout(reorderListHubColumnsById(layout, fromId, toId));
    },
    [layout, persistLayout],
  );

  const toggleColumn = useCallback(
    (columnId: ListHubColumnId) => {
      persistLayout(toggleListHubColumnInLayout(layout, columnId));
    },
    [layout, persistLayout],
  );

  const cycleSort = useCallback(
    (columnId: ListHubColumnId) => {
      if (!isSortableListHubColumn(columnId)) return;
      const current = resolveListHubSort(listConfig);
      let next: ListHubSortState;
      if (current.column !== columnId) {
        next = { column: columnId, direction: 'asc' };
      } else if (current.direction === 'asc') {
        next = { column: columnId, direction: 'desc' };
      } else {
        next = { column: 'name', direction: 'asc' };
      }
      updateListConfig({ hubSort: next });
      save();
    },
    [listConfig, save, updateListConfig],
  );

  const value = useMemo(
    () => ({
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
    <ListHubColumnLayoutContext.Provider value={value}>{children}</ListHubColumnLayoutContext.Provider>
  );
}

export function useListHubColumnLayoutContext() {
  const context = useContext(ListHubColumnLayoutContext);
  if (!context) {
    throw new Error(
      'useListHubColumnLayoutContext debe usarse dentro de ListHubColumnLayoutProvider',
    );
  }
  return context;
}

export function useOptionalListHubColumnLayoutContext() {
  return useContext(ListHubColumnLayoutContext);
}
