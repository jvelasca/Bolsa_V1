/**
 * Visibilidad y tamaño de los paneles acoplables
 * (Watchlist | Gráfico | Operaciones) + Operativa a altura completa.
 * Persistido solo en localStorage (`bolsa-trading-layout-v1`) — por dispositivo.
 *
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import type { TradingDockLayoutPrefs } from '@bolsa/shared';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const DEFAULT_LISTS_WIDTH_PCT = 26;
const DEFAULT_OPERATIONS_HEIGHT_PCT = 22;
const DEFAULT_OPERATIVA_WIDTH_PCT = 24;
const MIN_LISTS_WIDTH_PCT = 18;
const MAX_LISTS_WIDTH_PCT = 45;
const MIN_OPERATIONS_HEIGHT_PCT = 12;
const MAX_OPERATIONS_HEIGHT_PCT = 50;
const MIN_OPERATIVA_WIDTH_PCT = 16;
const MAX_OPERATIVA_WIDTH_PCT = 42;

const MIN_OPERATIVA_SECTION_HEIGHT_PX = 72;
/** Tope alto: panel Operativa a altura completa; el scroll solo si el contenido supera el alto elegido. */
const MAX_OPERATIVA_SECTION_HEIGHT_PX = 900;
const DEFAULT_OPERATIVA_SECTION_HEIGHTS: Record<OperativaSectionId, number> = {
  recommendation: 320,
  info: 200,
  config: 180,
};

export type OperativaSectionId = 'recommendation' | 'info' | 'config';

interface TradingLayoutState {
  listsOpen: boolean;
  chartsOpen: boolean;
  operationsOpen: boolean;
  operativaOpen: boolean;
  listsMaximized: boolean;
  chartsMaximized: boolean;
  operationsMaximized: boolean;
  listsWidthPct: number;
  operationsHeightPct: number;
  operativaWidthPct: number;
  operativaSections: Record<OperativaSectionId, boolean>;
  operativaSectionHeights: Record<OperativaSectionId, number>;
  toggleLists: () => void;
  ensureListsOpen: () => void;
  toggleCharts: () => void;
  toggleOperations: () => void;
  toggleOperativa: () => void;
  maximizeLists: () => void;
  maximizeCharts: () => void;
  maximizeOperations: () => void;
  restoreLayout: () => void;
  resetLayout: () => void;
  setListsWidthPct: (pct: number) => void;
  setOperationsHeightPct: (pct: number) => void;
  setOperativaWidthPct: (pct: number) => void;
  toggleOperativaSection: (id: OperativaSectionId) => void;
  setOperativaSectionHeight: (id: OperativaSectionId, heightPx: number) => void;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

const DEFAULT_OPERATIVA_SECTIONS: Record<OperativaSectionId, boolean> = {
  recommendation: true,
  info: true,
  config: true,
};

export const useTradingLayoutStore = create<TradingLayoutState>()(
  persist(
    (set, get) => ({
      listsOpen: true,
      chartsOpen: true,
      operationsOpen: true,
      operativaOpen: true,
      listsMaximized: false,
      chartsMaximized: false,
      operationsMaximized: false,
      listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
      operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
      operativaWidthPct: DEFAULT_OPERATIVA_WIDTH_PCT,
      operativaSections: { ...DEFAULT_OPERATIVA_SECTIONS },
      operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },

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

      toggleOperativa: () => {
        set({ operativaOpen: !get().operativaOpen });
      },

      maximizeLists: () => {
        const { listsMaximized } = get();
        if (listsMaximized) {
          set({ listsMaximized: false, chartsMaximized: false, operationsMaximized: false });
          return;
        }
        set({
          listsOpen: true,
          listsMaximized: true,
          chartsMaximized: false,
          operationsMaximized: false,
        });
      },

      maximizeCharts: () => {
        const { chartsMaximized } = get();
        if (chartsMaximized) {
          set({ listsMaximized: false, chartsMaximized: false, operationsMaximized: false });
          return;
        }
        set({
          chartsOpen: true,
          chartsMaximized: true,
          listsMaximized: false,
          operationsMaximized: false,
        });
      },

      maximizeOperations: () => {
        const { operationsMaximized } = get();
        if (operationsMaximized) {
          set({ operationsMaximized: false });
          return;
        }
        set({
          operationsOpen: true,
          operationsMaximized: true,
          listsMaximized: false,
          chartsMaximized: false,
        });
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
          operativaOpen: true,
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
          listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
          operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
          operativaWidthPct: DEFAULT_OPERATIVA_WIDTH_PCT,
          operativaSections: { ...DEFAULT_OPERATIVA_SECTIONS },
          operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
        }),

      setListsWidthPct: (pct) =>
        set({ listsWidthPct: clamp(pct, MIN_LISTS_WIDTH_PCT, MAX_LISTS_WIDTH_PCT) }),

      setOperationsHeightPct: (pct) =>
        set({
          operationsHeightPct: clamp(pct, MIN_OPERATIONS_HEIGHT_PCT, MAX_OPERATIONS_HEIGHT_PCT),
        }),

      setOperativaWidthPct: (pct) =>
        set({
          operativaWidthPct: clamp(pct, MIN_OPERATIVA_WIDTH_PCT, MAX_OPERATIVA_WIDTH_PCT),
        }),

      toggleOperativaSection: (id) => {
        const sections = get().operativaSections ?? DEFAULT_OPERATIVA_SECTIONS;
        set({
          operativaSections: {
            ...DEFAULT_OPERATIVA_SECTIONS,
            ...sections,
            [id]: !(sections[id] ?? true),
          },
        });
      },

      setOperativaSectionHeight: (id, heightPx) => {
        const heights = get().operativaSectionHeights ?? DEFAULT_OPERATIVA_SECTION_HEIGHTS;
        set({
          operativaSectionHeights: {
            ...DEFAULT_OPERATIVA_SECTION_HEIGHTS,
            ...heights,
            [id]: clamp(heightPx, MIN_OPERATIVA_SECTION_HEIGHT_PX, MAX_OPERATIVA_SECTION_HEIGHT_PX),
          },
        });
      },
    }),
    {
      name: 'bolsa-trading-layout-v1',
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<TradingLayoutState>;
        return {
          ...current,
          ...p,
          operativaOpen: p.operativaOpen ?? true,
          operativaWidthPct: clamp(
            p.operativaWidthPct ?? DEFAULT_OPERATIVA_WIDTH_PCT,
            MIN_OPERATIVA_WIDTH_PCT,
            MAX_OPERATIVA_WIDTH_PCT,
          ),
          operativaSections: {
            ...DEFAULT_OPERATIVA_SECTIONS,
            ...(p.operativaSections ?? {}),
          },
          operativaSectionHeights: {
            ...DEFAULT_OPERATIVA_SECTION_HEIGHTS,
            ...(p.operativaSectionHeights ?? {}),
          },
        };
      },
    },
  ),
);

export {
  MIN_LISTS_WIDTH_PCT,
  MAX_LISTS_WIDTH_PCT,
  MIN_OPERATIONS_HEIGHT_PCT,
  MAX_OPERATIONS_HEIGHT_PCT,
  MIN_OPERATIVA_WIDTH_PCT,
  MAX_OPERATIVA_WIDTH_PCT,
  DEFAULT_OPERATIVA_WIDTH_PCT,
  MIN_OPERATIVA_SECTION_HEIGHT_PX,
  MAX_OPERATIVA_SECTION_HEIGHT_PX,
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
