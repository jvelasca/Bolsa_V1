/**
 * Visibilidad y tamaño de los paneles acoplables
 * (Watchlist | Gráfico | Operaciones) + Operativa a altura completa.
 * Persistido solo en localStorage (`bolsa-trading-layout-v1`) — por dispositivo.
 *
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import type { TradingDockLayoutPrefs } from "@bolsa/shared";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  isNamedLayoutId,
  namedLayoutDockSnapshot,
  NAMED_LAYOUT_DEFAULT,
  type NamedLayoutId,
} from "@/features/command-palette/named-layout";

const DEFAULT_LISTS_WIDTH_PCT = 26;
/** Clave de persistencia local; también marca si ya hay preferencia de ancho. */
const TRADING_LAYOUT_STORAGE_KEY = "bolsa-trading-layout-v1";
const DEFAULT_OPERATIONS_HEIGHT_PCT = 22;
/** V2.41 — DECISIÓN floor ~28% so tablet ≥ ~280px (was ~215 @1024). */
const DEFAULT_OPERATIVA_WIDTH_PCT = 28;
const MIN_LISTS_WIDTH_PCT = 18;
const MAX_LISTS_WIDTH_PCT = 45;
const MIN_OPERATIONS_HEIGHT_PCT = 12;
const MAX_OPERATIONS_HEIGHT_PCT = 50;
const MIN_OPERATIVA_WIDTH_PCT = 20;
const MAX_OPERATIVA_WIDTH_PCT = 42;

const MIN_OPERATIVA_SECTION_HEIGHT_PX = 72;
/** Tope alto: panel Operativa a altura completa; el scroll solo si el contenido supera el alto elegido. */
const MAX_OPERATIVA_SECTION_HEIGHT_PX = 900;

/**
 * Bloques plegables de DECISIÓN (V2.48). Cada id = un asunto, no un cajón:
 * el seguimiento del Lab, el mandato vigente, la evidencia técnica, el
 * aprendizaje y la postura AUTO. Análisis diario y Decisión no son plegables:
 * son el parte y la acción.
 */
export type OperativaSectionId =
  | "lab"
  | "mandato"
  | "evidencia"
  | "resultados"
  | "auto";

/** Única tabla de alturas por defecto (la sección la usa como fallback). */
export const DEFAULT_OPERATIVA_SECTION_HEIGHTS: Record<
  OperativaSectionId,
  number
> = {
  lab: 280,
  mandato: 220,
  evidencia: 320,
  resultados: 200,
  auto: 220,
};

interface TradingLayoutState {
  listsOpen: boolean;
  chartsOpen: boolean;
  operationsOpen: boolean;
  operativaOpen: boolean;
  listsMaximized: boolean;
  chartsMaximized: boolean;
  operationsMaximized: boolean;
  /** DECISIÓN a área completa (excluyente con el resto de maximizados). */
  operativaMaximized: boolean;
  listsWidthPct: number;
  operationsHeightPct: number;
  operativaWidthPct: number;
  operativaSections: Record<OperativaSectionId, boolean>;
  operativaSectionHeights: Record<OperativaSectionId, number>;
  /** V1.31.2 — último preset nombrado; null si el usuario tweakeó docks a mano. */
  namedLayoutId: NamedLayoutId | null;
  toggleLists: () => void;
  ensureListsOpen: () => void;
  toggleCharts: () => void;
  toggleOperations: () => void;
  toggleOperativa: () => void;
  ensureOperativaOpen: () => void;
  ensureChartsOpen: () => void;
  maximizeLists: () => void;
  maximizeCharts: () => void;
  maximizeOperations: () => void;
  maximizeOperativa: () => void;
  restoreLayout: () => void;
  resetLayout: () => void;
  applyNamedLayout: (id: NamedLayoutId) => void;
  setListsWidthPct: (pct: number) => void;
  setOperationsHeightPct: (pct: number) => void;
  setOperativaWidthPct: (pct: number) => void;
  toggleOperativaSection: (id: OperativaSectionId) => void;
  setOperativaSectionHeight: (id: OperativaSectionId, heightPx: number) => void;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/**
 * Los cinco bloques arrancan colapsados (V2.41 densidad, sostenido en V2.48):
 * el idioma principal es el parte diario + la tarjeta DECISIÓN; el detalle se
 * abre a demanda.
 */
const DEFAULT_OPERATIVA_SECTIONS: Record<OperativaSectionId, boolean> = {
  lab: false,
  mandato: false,
  evidencia: false,
  resultados: false,
  auto: false,
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
      operativaMaximized: false,
      listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
      operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
      operativaWidthPct: DEFAULT_OPERATIVA_WIDTH_PCT,
      operativaSections: { ...DEFAULT_OPERATIVA_SECTIONS },
      operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
      namedLayoutId: NAMED_LAYOUT_DEFAULT,

      toggleLists: () => {
        const open = !get().listsOpen;
        set({
          listsOpen: open,
          listsMaximized: open ? get().listsMaximized : false,
          namedLayoutId: null,
        });
      },

      ensureListsOpen: () => {
        if (!get().listsOpen) {
          set({ listsOpen: true, listsMaximized: false, namedLayoutId: null });
        }
      },

      toggleCharts: () => {
        const open = !get().chartsOpen;
        set({
          chartsOpen: open,
          chartsMaximized: open ? get().chartsMaximized : false,
          namedLayoutId: null,
        });
      },

      toggleOperations: () => {
        const open = !get().operationsOpen;
        set({
          operationsOpen: open,
          operationsMaximized: open ? get().operationsMaximized : false,
          namedLayoutId: null,
        });
      },

      toggleOperativa: () => {
        const open = !get().operativaOpen;
        set({
          operativaOpen: open,
          // Reabrir no resucita el maximizado (mismo patrón que toggleLists).
          operativaMaximized: open ? get().operativaMaximized : false,
          namedLayoutId: null,
        });
      },

      ensureOperativaOpen: () => {
        if (!get().operativaOpen) {
          set({
            operativaOpen: true,
            operativaMaximized: false,
            namedLayoutId: null,
          });
        }
      },

      ensureChartsOpen: () => {
        const s = get();
        if (!s.chartsOpen || s.chartsMaximized) {
          set({
            chartsOpen: true,
            chartsMaximized: false,
            namedLayoutId: null,
          });
        }
      },

      maximizeLists: () => {
        const { listsMaximized } = get();
        if (listsMaximized) {
          set({
            listsMaximized: false,
            chartsMaximized: false,
            operationsMaximized: false,
            operativaMaximized: false,
          });
          return;
        }
        set({
          listsOpen: true,
          listsMaximized: true,
          chartsMaximized: false,
          operationsMaximized: false,
          operativaMaximized: false,
        });
      },

      maximizeCharts: () => {
        const { chartsMaximized } = get();
        if (chartsMaximized) {
          set({
            listsMaximized: false,
            chartsMaximized: false,
            operationsMaximized: false,
            operativaMaximized: false,
          });
          return;
        }
        set({
          chartsOpen: true,
          chartsMaximized: true,
          listsMaximized: false,
          operationsMaximized: false,
          operativaMaximized: false,
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
          operativaMaximized: false,
        });
      },

      maximizeOperativa: () => {
        const { operativaMaximized } = get();
        if (operativaMaximized) {
          set({ operativaMaximized: false });
          return;
        }
        set({
          operativaOpen: true,
          operativaMaximized: true,
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
        });
      },

      restoreLayout: () =>
        set({
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
          operativaMaximized: false,
        }),

      resetLayout: () => get().applyNamedLayout("trader"),

      applyNamedLayout: (id) => {
        const docks = namedLayoutDockSnapshot(id);
        set({
          ...docks,
          listsMaximized: false,
          chartsMaximized: false,
          operationsMaximized: false,
          operativaMaximized: false,
          listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
          operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
          operativaWidthPct: DEFAULT_OPERATIVA_WIDTH_PCT,
          operativaSections: { ...DEFAULT_OPERATIVA_SECTIONS },
          operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
          namedLayoutId: id,
        });
      },

      setListsWidthPct: (pct) =>
        set({
          listsWidthPct: clamp(pct, MIN_LISTS_WIDTH_PCT, MAX_LISTS_WIDTH_PCT),
          namedLayoutId: null,
        }),

      setOperationsHeightPct: (pct) =>
        set({
          operationsHeightPct: clamp(
            pct,
            MIN_OPERATIONS_HEIGHT_PCT,
            MAX_OPERATIONS_HEIGHT_PCT,
          ),
          namedLayoutId: null,
        }),

      setOperativaWidthPct: (pct) =>
        set({
          operativaWidthPct: clamp(
            pct,
            MIN_OPERATIVA_WIDTH_PCT,
            MAX_OPERATIVA_WIDTH_PCT,
          ),
          namedLayoutId: null,
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
        const heights =
          get().operativaSectionHeights ?? DEFAULT_OPERATIVA_SECTION_HEIGHTS;
        set({
          operativaSectionHeights: {
            ...DEFAULT_OPERATIVA_SECTION_HEIGHTS,
            ...heights,
            [id]: clamp(
              heightPx,
              MIN_OPERATIVA_SECTION_HEIGHT_PX,
              MAX_OPERATIVA_SECTION_HEIGHT_PX,
            ),
          },
        });
      },
    }),
    {
      name: TRADING_LAYOUT_STORAGE_KEY,
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<TradingLayoutState>;
        const namedLayoutId =
          p.namedLayoutId === null
            ? null
            : isNamedLayoutId(p.namedLayoutId)
              ? p.namedLayoutId
              : (current.namedLayoutId ?? NAMED_LAYOUT_DEFAULT);
        return {
          ...current,
          ...p,
          operativaOpen: p.operativaOpen ?? true,
          // Un estado guardado inconsistente (maximizado con la zona cerrada)
          // dejaría DECISIÓN invisible: se degrada a dock normal.
          operativaMaximized:
            p.operativaMaximized === true && (p.operativaOpen ?? true),
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
          namedLayoutId,
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

/**
 * Siembra el ancho del panel listas desde el workspace (legado `listPanelSizePct`)
 * solo en la primera visita: si ya hay preferencia local, manda el store.
 * No toca `namedLayoutId` (no es un ajuste manual del usuario).
 */
export function seedListsWidthPctFromLegacy(pct: number | undefined): void {
  if (pct == null || !Number.isFinite(pct)) return;
  if (typeof window === "undefined") return;
  if (window.localStorage.getItem(TRADING_LAYOUT_STORAGE_KEY)) return;
  const current = useTradingLayoutStore.getState().listsWidthPct;
  const next = clamp(pct, MIN_LISTS_WIDTH_PCT, MAX_LISTS_WIDTH_PCT);
  if (next === current) return;
  useTradingLayoutStore.setState({ listsWidthPct: next });
}
