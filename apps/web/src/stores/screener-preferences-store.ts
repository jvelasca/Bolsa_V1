import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { TrackerScheduleKind, PositionExecutionMode } from "@bolsa/shared";
import {
  DEFAULT_SCAN_RESULTS_FAVORITE_COLUMN_IDS,
  defaultScanResultsColumnLayout,
  type ScanResultsColumnId,
  type ScanResultsColumnLayoutItem,
  type ScanResultsSortState,
} from "@/lib/scan-results-column-layout";
import {
  DEFAULT_SCREENER_SPLIT_LAYOUT,
  type ScreenerSplitLayoutPrefs,
} from "@/lib/screener-split-layout";
import {
  defaultScanRunnerConfig,
  type ScanRunnerConfig,
} from "@/features/screeners/scan-runner-form";

interface TrackerSavePrefs {
  scheduleKind: TrackerScheduleKind;
  defaultPolicyId: string;
}

interface PositionPanelPrefs {
  mode: PositionExecutionMode;
  executeTrades: boolean;
  exitStrategyId: string;
  executionPolicyId: string;
}

export type ScreenerPanelId =
  | "trackers"
  | "fa-screener"
  | "paper-d"
  | "fa-weekly"
  | "saved-strategies"
  | "ai-assistant"
  | "execution"
  | "position"
  | "events"
  | "pipeline"
  | "jobs"
  | "history";

export type ScreenerMobileView = "workflow" | "tools";

export const DEFAULT_SCREENER_PANELS: Record<ScreenerPanelId, boolean> = {
  trackers: true,
  "fa-screener": true,
  "paper-d": true,
  "fa-weekly": false,
  "saved-strategies": false,
  "ai-assistant": false,
  execution: false,
  position: false,
  events: false,
  pipeline: false,
  jobs: true,
  history: false,
};

interface ScreenerLayoutPrefs {
  mobileView: ScreenerMobileView;
  panels: Record<ScreenerPanelId, boolean>;
  split: ScreenerSplitLayoutPrefs;
}

interface ScanResultsTablePrefs {
  columnLayout: ScanResultsColumnLayoutItem[];
  sort: ScanResultsSortState | null;
  favoriteColumnIds: ScanResultsColumnId[];
}

interface ScreenerPreferencesState {
  scanConfig: ScanRunnerConfig;
  runInBackground: boolean;
  lastExecutionPolicyId: string | null;
  trackerSave: TrackerSavePrefs;
  positionPanel: PositionPanelPrefs;
  layout: ScreenerLayoutPrefs;
  scanResultsTable: ScanResultsTablePrefs;
  patchScanConfig: (patch: Partial<ScanRunnerConfig>) => void;
  setScanConfig: (config: ScanRunnerConfig) => void;
  setRunInBackground: (value: boolean) => void;
  setLastExecutionPolicyId: (id: string | null) => void;
  patchTrackerSave: (patch: Partial<TrackerSavePrefs>) => void;
  patchPositionPanel: (patch: Partial<PositionPanelPrefs>) => void;
  setMobileView: (view: ScreenerMobileView) => void;
  togglePanel: (panelId: ScreenerPanelId) => void;
  setPanelOpen: (panelId: ScreenerPanelId, open: boolean) => void;
  patchSplitLayout: (patch: Partial<ScreenerSplitLayoutPrefs>) => void;
  setScanResultsColumnLayout: (layout: ScanResultsColumnLayoutItem[]) => void;
  setScanResultsSort: (sort: ScanResultsSortState | null) => void;
  setScanResultsFavoriteColumnIds: (
    favoriteColumnIds: ScanResultsColumnId[],
  ) => void;
}

export const useScreenerPreferencesStore = create<ScreenerPreferencesState>()(
  persist(
    (set) => ({
      scanConfig: defaultScanRunnerConfig(),
      runInBackground: false,
      lastExecutionPolicyId: null,
      trackerSave: {
        scheduleKind: "manual",
        defaultPolicyId: "",
      },
      positionPanel: {
        mode: "exit_strategy",
        executeTrades: false,
        exitStrategyId: "",
        executionPolicyId: "",
      },
      layout: {
        mobileView: "workflow",
        panels: { ...DEFAULT_SCREENER_PANELS },
        split: { ...DEFAULT_SCREENER_SPLIT_LAYOUT },
      },
      scanResultsTable: {
        columnLayout: defaultScanResultsColumnLayout({
          full: true,
          hasRating: true,
          hasBreakdown: true,
          hasDataQuality: true,
        }),
        sort: { columnId: "globalScore", direction: "desc" },
        favoriteColumnIds: [...DEFAULT_SCAN_RESULTS_FAVORITE_COLUMN_IDS],
      },
      patchScanConfig: (patch) =>
        set((state) => ({ scanConfig: { ...state.scanConfig, ...patch } })),
      setScanConfig: (scanConfig) => set({ scanConfig }),
      setRunInBackground: (runInBackground) => set({ runInBackground }),
      setLastExecutionPolicyId: (lastExecutionPolicyId) =>
        set({ lastExecutionPolicyId }),
      patchTrackerSave: (patch) =>
        set((state) => ({ trackerSave: { ...state.trackerSave, ...patch } })),
      patchPositionPanel: (patch) =>
        set((state) => ({
          positionPanel: { ...state.positionPanel, ...patch },
        })),
      setMobileView: (mobileView) =>
        set((state) => ({ layout: { ...state.layout, mobileView } })),
      togglePanel: (panelId) =>
        set((state) => ({
          layout: {
            ...state.layout,
            panels: {
              ...state.layout.panels,
              [panelId]: !(
                state.layout.panels[panelId] ?? DEFAULT_SCREENER_PANELS[panelId]
              ),
            },
          },
        })),
      setPanelOpen: (panelId, open) =>
        set((state) => ({
          layout: {
            ...state.layout,
            panels: { ...state.layout.panels, [panelId]: open },
          },
        })),
      patchSplitLayout: (patch) =>
        set((state) => ({
          layout: {
            ...state.layout,
            split: { ...state.layout.split, ...patch },
          },
        })),
      setScanResultsColumnLayout: (columnLayout) =>
        set((state) => ({
          scanResultsTable: { ...state.scanResultsTable, columnLayout },
        })),
      setScanResultsSort: (sort) =>
        set((state) => ({
          scanResultsTable: { ...state.scanResultsTable, sort },
        })),
      setScanResultsFavoriteColumnIds: (favoriteColumnIds) =>
        set((state) => ({
          scanResultsTable: { ...state.scanResultsTable, favoriteColumnIds },
        })),
    }),
    {
      name: "bolsa-screener-preferences",
      merge: (persisted, current) => {
        const stored = persisted as
          | Partial<ScreenerPreferencesState>
          | undefined;
        if (!stored) return current;
        return {
          ...current,
          ...stored,
          scanConfig: { ...defaultScanRunnerConfig(), ...stored.scanConfig },
          layout: {
            mobileView: stored.layout?.mobileView ?? current.layout.mobileView,
            panels: {
              ...DEFAULT_SCREENER_PANELS,
              ...stored.layout?.panels,
            },
            split: {
              ...DEFAULT_SCREENER_SPLIT_LAYOUT,
              ...stored.layout?.split,
              sidebarPanelSizes: {
                ...DEFAULT_SCREENER_SPLIT_LAYOUT.sidebarPanelSizes,
                ...stored.layout?.split?.sidebarPanelSizes,
              },
            },
          },
          scanResultsTable: {
            columnLayout:
              stored.scanResultsTable?.columnLayout ??
              current.scanResultsTable.columnLayout,
            sort:
              stored.scanResultsTable?.sort ?? current.scanResultsTable.sort,
            favoriteColumnIds:
              stored.scanResultsTable?.favoriteColumnIds ??
              current.scanResultsTable.favoriteColumnIds,
          },
        };
      },
    },
  ),
);

/** Valida IDs contra listas/estrategias cargadas; conserva preferencia si aún existe. */
export function reconcileScanConfig(
  config: ScanRunnerConfig,
  lists: Array<{ id: string; name?: string }>,
  strategies: Array<{ id: string }>,
): ScanRunnerConfig {
  let listId = config.listId;
  if (lists.length > 0 && listId && !lists.some((list) => list.id === listId)) {
    const ibex = lists.find(
      (list) => list.name?.includes("IBEX") || list.id.includes("ibex"),
    );
    listId = ibex?.id ?? lists[0]?.id ?? listId;
  }
  if (lists.length > 0 && !listId) {
    listId = lists.find((l) => l.id)?.id ?? "";
  }

  let savedStrategyId = config.savedStrategyId;
  if (
    config.scanSource === "saved" &&
    strategies.length > 0 &&
    savedStrategyId &&
    !strategies.some((s) => s.id === savedStrategyId)
  ) {
    savedStrategyId = "";
  }

  return { ...config, listId, savedStrategyId };
}
