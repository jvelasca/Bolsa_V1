import {
  MAX_LIST_PANEL_SIZE_PCT,
  MAX_RIGHT_PANEL_SIZE_PCT,
  MIN_LIST_PANEL_SIZE_PCT,
  MIN_RIGHT_PANEL_SIZE_PCT,
  DEFAULT_LIST_PANEL_SIZE_PCT,
  DEFAULT_RIGHT_PANEL_SIZE_PCT,
} from "@bolsa/shared";
import { getWorkspaceUiBridge } from "@/stores/workspace-ui-bridge";
import {
  createInspectorNavRequest,
  inspectorNavigateKey,
} from "@/features/charts/chart-inspector-nav";
import {
  type WorkspaceSlice,
  finalizeChartWorkspace,
  chartPersistBackupFrom,
  scheduleWorkspaceServerSave,
  flushDrawingAutoSave,
  scheduleWorkspaceSettingsPersist,
} from "./workspace-store-core";

export const layoutSlice: WorkspaceSlice = (get, set) => ({
  setListPanelOpen: (open) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        layout: { ...state.workspace.layout, listPanelOpen: open },
      },
      isDirty: true,
    })),
  setListPanelSizePct: (pct) => {
    const clamped = Math.min(
      MAX_LIST_PANEL_SIZE_PCT,
      Math.max(MIN_LIST_PANEL_SIZE_PCT, Math.round(pct)),
    );
    set((state) => ({
      workspace: {
        ...state.workspace,
        layout: { ...state.workspace.layout, listPanelSizePct: clamped },
        updatedAt: new Date().toISOString(),
      },
      isDirty: !state.workspace.preferences.autoSave,
    }));
    if (get().workspace.preferences.autoSave) scheduleWorkspaceServerSave(get);
  },
  setRightPanelOpen: (open) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        layout: { ...state.workspace.layout, rightPanelOpen: open },
      },
      isDirty: true,
    })),
  setRightPanelSizePct: (pct) => {
    const clamped = Math.min(
      MAX_RIGHT_PANEL_SIZE_PCT,
      Math.max(MIN_RIGHT_PANEL_SIZE_PCT, Math.round(pct)),
    );
    set((state) => ({
      workspace: {
        ...state.workspace,
        layout: { ...state.workspace.layout, rightPanelSizePct: clamped },
        updatedAt: new Date().toISOString(),
      },
      isDirty: !state.workspace.preferences.autoSave,
    }));
    if (get().workspace.preferences.autoSave) scheduleWorkspaceServerSave(get);
  },
  setChartInspectorOpen: (open) =>
    set((state) => {
      if (!open) {
        getWorkspaceUiBridge().setChartInspectorActiveShortcutKey(null);
      }
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        layout: { ...state.workspace.layout, chartInspectorOpen: open },
      });
      return {
        workspace,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        isDirty: !state.workspace.preferences.autoSave,
      };
    }),
  toggleChartInspector: () => {
    const open = get().workspace.layout.chartInspectorOpen;
    get().setChartInspectorOpen(!open);
    flushDrawingAutoSave(get, true);
  },
  openChartInspector: (target) => {
    getWorkspaceUiBridge().setChartInspectorNav(
      createInspectorNavRequest(target),
    );
    get().setChartInspectorOpen(true);
  },
  toggleChartInspectorShortcut: (target) => {
    const key = inspectorNavigateKey(target);
    const open = get().workspace.layout.chartInspectorOpen ?? false;
    const activeKey =
      getWorkspaceUiBridge().getChartInspectorActiveShortcutKey();
    if (open && activeKey === key) {
      get().setChartInspectorOpen(false);
      return;
    }
    getWorkspaceUiBridge().setChartInspectorActiveShortcutKey(key);
    getWorkspaceUiBridge().setChartInspectorNav(
      createInspectorNavRequest(target),
    );
    get().setChartInspectorOpen(true);
  },
  resetPanelLayout: () =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        layout: {
          ...state.workspace.layout,
          listPanelOpen: true,
          listPanelSizePct: DEFAULT_LIST_PANEL_SIZE_PCT,
          rightPanelOpen: true,
          rightPanelSizePct: DEFAULT_RIGHT_PANEL_SIZE_PCT,
        },
        updatedAt: new Date().toISOString(),
      },
      isDirty: true,
    })),
  toggleNewChartTemplatePin: () => {
    const activeId = get().workspace.activeChartId;
    if (!activeId) return;
    set((state) => {
      const current =
        state.workspace.preferences.newChartTemplateChartId ?? null;
      const nextId = current === activeId ? null : activeId;
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          preferences: {
            ...state.workspace.preferences,
            newChartTemplateChartId: nextId,
          },
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
});
