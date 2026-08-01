/**
 * Anchos de columnas (Valores / Listas hub) y columnas de acciones — por dispositivo.
 * Orden y visibilidad siguen en el documento del espacio (servidor).
 *
 * localStorage: `bolsa-list-chrome-layout-v1`
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  ListColumnId,
  ListColumnLayoutItem,
  ListHubColumnId,
  ListHubColumnLayoutItem,
} from '@bolsa/shared';
import {
  clampListColumnWidth,
  clampListRowActionsWidth,
  DEFAULT_LIST_COLUMN_WIDTHS,
  DEFAULT_LIST_HUB_COLUMN_WIDTHS,
  clampListHubColumnWidth,
} from '@bolsa/shared';
import { clampListHubRowActionsWidth } from '@/lib/list-hub-column-layout';

type WidthMap = Partial<Record<string, number>>;

interface ListChromeLayoutState {
  /** Anchos por listId (Valores). */
  widthsByListId: Record<string, WidthMap>;
  /** null = aún no sembrado desde servidor/defaults. */
  rowActionsWidth: number | null;
  hubWidths: WidthMap;
  hubRowActionsWidth: number | null;
  hubSeeded: boolean;

  seedListWidthsIfNeeded: (listId: string, serverLayout: ListColumnLayoutItem[]) => void;
  setListColumnWidth: (listId: string, columnId: ListColumnId, width: number) => void;
  seedRowActionsIfNeeded: (serverWidth: number) => void;
  setRowActionsWidth: (width: number) => void;

  seedHubIfNeeded: (
    serverLayout: ListHubColumnLayoutItem[],
    serverRowActionsWidth: number,
  ) => void;
  setHubColumnWidth: (columnId: ListHubColumnId, width: number) => void;
  setHubRowActionsWidth: (width: number) => void;
}

export const useListChromeLayoutStore = create<ListChromeLayoutState>()(
  persist(
    (set, get) => ({
      widthsByListId: {},
      rowActionsWidth: null,
      hubWidths: {},
      hubRowActionsWidth: null,
      hubSeeded: false,

      seedListWidthsIfNeeded: (listId, serverLayout) => {
        if (!listId || get().widthsByListId[listId]) return;
        const widths: WidthMap = {};
        for (const column of serverLayout) {
          widths[column.id] = clampListColumnWidth(column.width);
        }
        set((state) => ({
          widthsByListId: { ...state.widthsByListId, [listId]: widths },
        }));
      },

      setListColumnWidth: (listId, columnId, width) => {
        if (!listId) return;
        const clamped = clampListColumnWidth(width);
        set((state) => {
          const prev = state.widthsByListId[listId] ?? {};
          return {
            widthsByListId: {
              ...state.widthsByListId,
              [listId]: { ...prev, [columnId]: clamped },
            },
          };
        });
      },

      seedRowActionsIfNeeded: (serverWidth) => {
        if (get().rowActionsWidth != null) return;
        set({ rowActionsWidth: clampListRowActionsWidth(serverWidth) });
      },

      setRowActionsWidth: (width) => {
        set({ rowActionsWidth: clampListRowActionsWidth(width) });
      },

      seedHubIfNeeded: (serverLayout, serverRowActionsWidth) => {
        if (get().hubSeeded) return;
        const hubWidths: WidthMap = {};
        for (const column of serverLayout) {
          hubWidths[column.id] = clampListHubColumnWidth(column.width, column.id);
        }
        set({
          hubWidths,
          hubRowActionsWidth: clampListHubRowActionsWidth(serverRowActionsWidth),
          hubSeeded: true,
        });
      },

      setHubColumnWidth: (columnId, width) => {
        set((state) => ({
          hubWidths: {
            ...state.hubWidths,
            [columnId]: clampListHubColumnWidth(width, columnId),
          },
        }));
      },

      setHubRowActionsWidth: (width) => {
        set({ hubRowActionsWidth: clampListHubRowActionsWidth(width) });
      },
    }),
    { name: 'bolsa-list-chrome-layout-v1' },
  ),
);

/** Aplica anchos locales sobre el layout del servidor (orden / visibilidad). */
export function mergeListColumnWidths(
  listId: string,
  serverLayout: ListColumnLayoutItem[],
): ListColumnLayoutItem[] {
  const local = useListChromeLayoutStore.getState().widthsByListId[listId];
  if (!local) return serverLayout;
  return serverLayout.map((column) => ({
    ...column,
    width: clampListColumnWidth(local[column.id] ?? column.width),
  }));
}

export function resolveLocalRowActionsWidth(serverWidth: number): number {
  const local = useListChromeLayoutStore.getState().rowActionsWidth;
  return clampListRowActionsWidth(local ?? serverWidth);
}

export function mergeHubColumnWidths(
  serverLayout: ListHubColumnLayoutItem[],
): ListHubColumnLayoutItem[] {
  const { hubWidths, hubSeeded } = useListChromeLayoutStore.getState();
  if (!hubSeeded) return serverLayout;
  return serverLayout.map((column) => ({
    ...column,
    width: clampListHubColumnWidth(hubWidths[column.id] ?? column.width, column.id),
  }));
}

export function resolveLocalHubRowActionsWidth(serverWidth: number): number {
  const local = useListChromeLayoutStore.getState().hubRowActionsWidth;
  return clampListHubRowActionsWidth(local ?? serverWidth);
}

/** Anchos por defecto al persistir orden/visibilidad en el servidor (sin chrome del PC). */
export function layoutForServerSync(layout: ListColumnLayoutItem[]): ListColumnLayoutItem[] {
  return layout.map((column) => ({
    ...column,
    width: DEFAULT_LIST_COLUMN_WIDTHS[column.id] ?? column.width,
  }));
}

export function hubLayoutForServerSync(
  layout: ListHubColumnLayoutItem[],
): ListHubColumnLayoutItem[] {
  return layout.map((column) => ({
    ...column,
    width: DEFAULT_LIST_HUB_COLUMN_WIDTHS[column.id] ?? column.width,
  }));
}
