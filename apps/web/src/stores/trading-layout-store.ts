/**
 * Visibilidad y tamaño de los paneles acoplables (Listas | Gráficos | Operaciones).
 * Persistido solo en localStorage (`bolsa-trading-layout-v1`) — por dispositivo.
 * No se aplica desde el `dockLayout` del servidor al cargar un espacio.
 */
import type { TradingDockLayoutPrefs } from '@bolsa/shared';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const DEFAULT_LISTS_WIDTH_PCT = 26;
const DEFAULT_OPERATIONS_HEIGHT_PCT = 22;
const MIN_LISTS_WIDTH_PCT = 18;
const MAX_LISTS_WIDTH_PCT = 45;
const MIN_OPERATIONS_HEIGHT_PCT = 12;
const MAX_OPERATIONS_HEIGHT_PCT = 50;

interface TradingLayoutState {
  listsOpen: boolean;
  chartsOpen: boolean;
  operationsOpen: boolean;
  listsMaximized: boolean;
  chartsMaximized: boolean;
  operationsMaximized: boolean;
  listsWidthPct: number;
  operationsHeightPct: number;
  toggleLists: () => void;
  ensureListsOpen: () => void;
  toggleCharts: () => void;
  toggleOperations: () => void;
  maximizeLists: () => void;
  maximizeCharts: () => void;
  maximizeOperations: () => void;
  restoreLayout: () => void;
  resetLayout: () => void;
  setListsWidthPct: (pct: number) => void;
  setOperationsHeightPct: (pct: number) => void;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export const useTradingLayoutStore = create<TradingLayoutState>()(
  persist(
    (set, get) => ({
      listsOpen: true,
      chartsOpen: true,
      operationsOpen: true,
      listsMaximized: false,
      chartsMaximized: false,
      operationsMaximized: false,
      listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
      operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,

      toggleLists: () => {
        const open = !get().listsOpen;
        set({
          listsOpen: open,
          listsMaximized: open ? get().listsMaximized : false,
        });
      },

      ensureListsOpen: () => {
        if (!get().listsOpen) {
          set({ listsOpen: true, listsMaximized: false });
        }
      },

      toggleCharts: () => {
        const open = !get().chartsOpen;
        set({
          chartsOpen: open,
          chartsMaximized: open ? get().chartsMaximized : false,
        });
      },

      toggleOperations: () => {
        const open = !get().operationsOpen;
        set({
          operationsOpen: open,
          operationsMaximized: open ? get().operationsMaximized : false,
        });
      },

      maximizeLists: () => {
        const { listsMaximized } = get();
        if (listsMaximized) {
          set({ listsMaximized: false, chartsMaximized: false, operationsMaximized: false });
          return;
        }
        set({ listsOpen: true, listsMaximized: true, chartsMaximized: false, operationsMaximized: false });
      },

      maximizeCharts: () => {
        const { chartsMaximized } = get();
        if (chartsMaximized) {
          set({ listsMaximized: false, chartsMaximized: false, operationsMaximized: false });
          return;
        }
        set({ chartsOpen: true, chartsMaximized: true, listsMaximized: false, operationsMaximized: false });
      },

      maximizeOperations: () => {
        const { operationsMaximized } = get();
        if (operationsMaximized) {
          set({ operationsMaximized: false });
          return;
        }
        set({ operationsOpen: true, operationsMaximized: true, listsMaximized: false, chartsMaximized: false });
      },

      restoreLayout: () =>
        set({
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
        }),

      resetLayout: () =>
        set({
          listsOpen: true,
          chartsOpen: true,
          operationsOpen: true,
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
          listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
          operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
        }),

      setListsWidthPct: (pct) =>
        set({ listsWidthPct: clamp(pct, MIN_LISTS_WIDTH_PCT, MAX_LISTS_WIDTH_PCT) }),

      setOperationsHeightPct: (pct) =>
        set({
          operationsHeightPct: clamp(pct, MIN_OPERATIONS_HEIGHT_PCT, MAX_OPERATIONS_HEIGHT_PCT),
        }),
    }),
    { name: 'bolsa-trading-layout-v1' },
  ),
);

export {
  MIN_LISTS_WIDTH_PCT,
  MAX_LISTS_WIDTH_PCT,
  MIN_OPERATIONS_HEIGHT_PCT,
  MAX_OPERATIONS_HEIGHT_PCT,
};

/** Snapshot del dock local (p. ej. depuración). No se aplica desde el servidor. */
export function getDockLayoutPrefs(): TradingDockLayoutPrefs {
  const s = useTradingLayoutStore.getState();
  return {
    listsOpen: s.listsOpen,
    operationsOpen: s.operationsOpen,
    listsWidthPct: s.listsWidthPct,
    operationsHeightPct: s.operationsHeightPct,
  };
}
