/**
 * Preferencias persistentes hub Instrumentos (columnas · split · detalle).
 * Persistidas en localStorage del navegador (por perfil/máquina).
 * Split wide vs stack se guardan por separado para no mezclar escritorio y móvil.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  DEFAULT_INSTRUMENTS_HUB_COLUMN_LAYOUT,
  DEFAULT_INSTRUMENTS_HUB_FAVORITE_COLUMN_IDS,
  normalizeInstrumentsHubColumnLayout,
  type InstrumentsHubColumnId,
  type InstrumentsHubColumnLayoutItem,
  type InstrumentsHubColumnSortState,
} from '@/features/instruments/instruments-hub-column-layout';
import {
  DEFAULT_INSTRUMENTS_HUB_LIST_PCT,
  DEFAULT_INSTRUMENTS_HUB_STACK_PCT,
  clampInstrumentsHubListPct,
  clampInstrumentsHubStackPct,
} from '@/features/instruments/instruments-hub-split-layout';
import {
  DEFAULT_INSTRUMENTS_HUB_DETAIL_SECTIONS,
  type InstrumentsHubDetailSectionId,
} from '@/features/instruments/instruments-hub-detail-panel';

const PREFS_STORAGE_KEY = 'bolsa-instruments-hub-prefs-v2';
const PREFS_STORAGE_KEY_V1 = 'bolsa-instruments-hub-prefs-v1';

/** Migra prefs v1 → v2 una vez (mismo navegador / perfil). */
function migrateInstrumentsHubPrefsStorage(): void {
  if (typeof window === 'undefined') return;
  try {
    if (window.localStorage.getItem(PREFS_STORAGE_KEY)) return;
    const legacy = window.localStorage.getItem(PREFS_STORAGE_KEY_V1);
    if (legacy) window.localStorage.setItem(PREFS_STORAGE_KEY, legacy);
  } catch {
    /* ignore quota / private mode */
  }
}

migrateInstrumentsHubPrefsStorage();

export type InstrumentsHubLayoutMode = 'wide' | 'stack';

export type InstrumentsHubWideSplitPrefs = {
  listWidthPct: number;
  detailPanelOpen: boolean;
};

export type InstrumentsHubStackSplitPrefs = {
  stackHeightPct: number;
  detailPanelOpen: boolean;
};

function normalizeDetailSections(
  value: unknown,
): Record<InstrumentsHubDetailSectionId, boolean> {
  const base = { ...DEFAULT_INSTRUMENTS_HUB_DETAIL_SECTIONS };
  if (!value || typeof value !== 'object') return base;
  const raw = value as Partial<Record<InstrumentsHubDetailSectionId, boolean>>;
  for (const key of Object.keys(base) as InstrumentsHubDetailSectionId[]) {
    if (typeof raw[key] === 'boolean') base[key] = raw[key]!;
  }
  return base;
}

function normalizeWideSplit(value: unknown): InstrumentsHubWideSplitPrefs {
  const raw = (value ?? {}) as Partial<InstrumentsHubWideSplitPrefs>;
  return {
    listWidthPct: clampInstrumentsHubListPct(
      typeof raw.listWidthPct === 'number'
        ? raw.listWidthPct
        : DEFAULT_INSTRUMENTS_HUB_LIST_PCT,
    ),
    detailPanelOpen:
      typeof raw.detailPanelOpen === 'boolean' ? raw.detailPanelOpen : true,
  };
}

function normalizeStackSplit(value: unknown): InstrumentsHubStackSplitPrefs {
  const raw = (value ?? {}) as Partial<InstrumentsHubStackSplitPrefs>;
  return {
    stackHeightPct: clampInstrumentsHubStackPct(
      typeof raw.stackHeightPct === 'number'
        ? raw.stackHeightPct
        : DEFAULT_INSTRUMENTS_HUB_STACK_PCT,
    ),
    detailPanelOpen:
      typeof raw.detailPanelOpen === 'boolean' ? raw.detailPanelOpen : true,
  };
}

type InstrumentsHubPreferencesState = {
  columnLayout: InstrumentsHubColumnLayoutItem[];
  sort: InstrumentsHubColumnSortState | null;
  favoriteColumnIds: InstrumentsHubColumnId[];
  autoFitColumns: boolean;
  /** Split horizontal (desktop / ≥1024px). */
  wideSplit: InstrumentsHubWideSplitPrefs;
  /** Split vertical (móvil / tablet apilada). */
  stackSplit: InstrumentsHubStackSplitPrefs;
  detailSectionsOpen: Record<InstrumentsHubDetailSectionId, boolean>;
  setColumnLayout: (columnLayout: InstrumentsHubColumnLayoutItem[]) => void;
  setSort: (sort: InstrumentsHubColumnSortState | null) => void;
  setFavoriteColumnIds: (favoriteColumnIds: InstrumentsHubColumnId[]) => void;
  setAutoFitColumns: (autoFitColumns: boolean) => void;
  setListWidthPct: (listWidthPct: number) => void;
  setStackHeightPct: (stackHeightPct: number) => void;
  setDetailPanelOpen: (mode: InstrumentsHubLayoutMode, open: boolean) => void;
  setDetailSectionsOpen: (
    detailSectionsOpen: Record<InstrumentsHubDetailSectionId, boolean>,
  ) => void;
  toggleDetailSection: (id: InstrumentsHubDetailSectionId) => void;
};

export const useInstrumentsHubPreferencesStore = create<InstrumentsHubPreferencesState>()(
  persist(
    (set) => ({
      columnLayout: DEFAULT_INSTRUMENTS_HUB_COLUMN_LAYOUT.map((c) => ({ ...c })),
      sort: { columnId: 'symbol', direction: 'asc' },
      favoriteColumnIds: [...DEFAULT_INSTRUMENTS_HUB_FAVORITE_COLUMN_IDS],
      autoFitColumns: false,
      wideSplit: {
        listWidthPct: DEFAULT_INSTRUMENTS_HUB_LIST_PCT,
        detailPanelOpen: true,
      },
      stackSplit: {
        stackHeightPct: DEFAULT_INSTRUMENTS_HUB_STACK_PCT,
        detailPanelOpen: true,
      },
      detailSectionsOpen: { ...DEFAULT_INSTRUMENTS_HUB_DETAIL_SECTIONS },
      setColumnLayout: (columnLayout) =>
        set({ columnLayout: normalizeInstrumentsHubColumnLayout(columnLayout) }),
      setSort: (sort) => set({ sort }),
      setFavoriteColumnIds: (favoriteColumnIds) => set({ favoriteColumnIds }),
      setAutoFitColumns: (autoFitColumns) => set({ autoFitColumns }),
      setListWidthPct: (listWidthPct) =>
        set((state) => ({
          wideSplit: {
            ...state.wideSplit,
            listWidthPct: clampInstrumentsHubListPct(listWidthPct),
          },
        })),
      setStackHeightPct: (stackHeightPct) =>
        set((state) => ({
          stackSplit: {
            ...state.stackSplit,
            stackHeightPct: clampInstrumentsHubStackPct(stackHeightPct),
          },
        })),
      setDetailPanelOpen: (mode, open) =>
        set((state) =>
          mode === 'wide'
            ? { wideSplit: { ...state.wideSplit, detailPanelOpen: open } }
            : { stackSplit: { ...state.stackSplit, detailPanelOpen: open } },
        ),
      setDetailSectionsOpen: (detailSectionsOpen) =>
        set({ detailSectionsOpen: normalizeDetailSections(detailSectionsOpen) }),
      toggleDetailSection: (id) =>
        set((state) => ({
          detailSectionsOpen: {
            ...state.detailSectionsOpen,
            [id]: !state.detailSectionsOpen[id],
          },
        })),
    }),
    {
      name: PREFS_STORAGE_KEY,
      partialize: (s) => ({
        columnLayout: s.columnLayout,
        sort: s.sort,
        favoriteColumnIds: s.favoriteColumnIds,
        autoFitColumns: s.autoFitColumns,
        wideSplit: s.wideSplit,
        stackSplit: s.stackSplit,
        detailSectionsOpen: s.detailSectionsOpen,
      }),
      merge: (persisted, current) => {
        const stored = (persisted ?? {}) as Partial<InstrumentsHubPreferencesState> & {
          /** v1 flat fields */
          listWidthPct?: number;
          stackHeightPct?: number;
          detailPanelOpen?: boolean;
          detailTab?: string;
        };

        const wideFromV1 =
          typeof stored.listWidthPct === 'number' || typeof stored.detailPanelOpen === 'boolean'
            ? {
                listWidthPct:
                  typeof stored.listWidthPct === 'number'
                    ? stored.listWidthPct
                    : DEFAULT_INSTRUMENTS_HUB_LIST_PCT,
                detailPanelOpen:
                  typeof stored.detailPanelOpen === 'boolean'
                    ? stored.detailPanelOpen
                    : true,
              }
            : undefined;

        const stackFromV1 =
          typeof stored.stackHeightPct === 'number' || typeof stored.detailPanelOpen === 'boolean'
            ? {
                stackHeightPct:
                  typeof stored.stackHeightPct === 'number'
                    ? stored.stackHeightPct
                    : DEFAULT_INSTRUMENTS_HUB_STACK_PCT,
                detailPanelOpen:
                  typeof stored.detailPanelOpen === 'boolean'
                    ? stored.detailPanelOpen
                    : true,
              }
            : undefined;

        return {
          ...current,
          ...stored,
          columnLayout: normalizeInstrumentsHubColumnLayout(stored.columnLayout),
          favoriteColumnIds:
            stored.favoriteColumnIds?.length
              ? stored.favoriteColumnIds
              : current.favoriteColumnIds,
          sort: stored.sort ?? current.sort,
          autoFitColumns:
            typeof stored.autoFitColumns === 'boolean'
              ? stored.autoFitColumns
              : current.autoFitColumns,
          wideSplit: normalizeWideSplit(stored.wideSplit ?? wideFromV1 ?? current.wideSplit),
          stackSplit: normalizeStackSplit(
            stored.stackSplit ?? stackFromV1 ?? current.stackSplit,
          ),
          detailSectionsOpen: normalizeDetailSections(
            stored.detailSectionsOpen ?? current.detailSectionsOpen,
          ),
        };
      },
    },
  ),
);
