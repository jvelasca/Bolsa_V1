import {
  seedIndicatorInstancesFromDisplay,
  mergeDisplayFromInstances,
} from "@bolsa/shared";
import {
  attachActiveTabListSnapshot,
  pruneOrphanChartSnapshots,
  syncSnapshotsFromCharts,
} from "@/lib/chart-list-snapshot";
import {
  reconcileWorkspaceChartMembership,
  resolveValidSourceListIdForTab,
} from "@/lib/chart-list-membership";
import { getWorkspaceUiBridge } from "@/stores/workspace-ui-bridge";
import {
  type WorkspaceSlice,
  finalizeChartWorkspace,
  openDrawingEditorId,
  createChartTabForInstrument,
  requestWorkspaceAutoSave,
  flushDrawingAutoSave,
  scheduleWorkspaceSettingsPersist,
} from "./workspace-store-core";

export const chartsSlice: WorkspaceSlice = (get, set) => ({
  openChartTab: (instrumentId, label) => {
    const existing = get().workspace.charts.find(
      (tab) => tab.instrumentId === instrumentId,
    );
    if (existing) {
      set((state) => ({
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          activeChartId: existing.id,
        }),
        // Con autoSave, isDirty=false permitía sync remoto con menos tabs.
        isDirty: true,
      }));
      return existing.id;
    }
    const nextTab = createChartTabForInstrument(
      get().workspace,
      instrumentId,
      label,
    );
    set((state) => ({
      workspace: finalizeChartWorkspace({
        ...state.workspace,
        charts: [...state.workspace.charts, nextTab],
        activeChartId: nextTab.id,
      }),
      isDirty: true,
    }));
    if (get().workspace.preferences.autoSave) {
      requestWorkspaceAutoSave(get);
    }
    return nextTab.id;
  },
  focusInstrumentFromList: (listId, instrumentId, label) => {
    let activeTabId = "";
    set((state) => {
      let workspace = attachActiveTabListSnapshot(
        state.workspace,
        openDrawingEditorId(),
      );
      const existingIndex = workspace.charts.findIndex(
        (tab) => tab.instrumentId === instrumentId,
      );
      let charts = [...workspace.charts];
      let activeChartId = workspace.activeChartId;

      if (existingIndex >= 0) {
        const existing = charts[existingIndex]!;
        charts[existingIndex] = {
          ...existing,
          label,
          sourceListId: listId,
        };
        activeChartId = charts[existingIndex]!.id;
      } else {
        const baseTab = createChartTabForInstrument(
          workspace,
          instrumentId,
          label,
          {
            sourceListId: listId,
          },
        );
        charts = [...charts, baseTab];
        activeChartId = baseTab.id;
      }

      workspace = finalizeChartWorkspace({
        ...workspace,
        charts,
        activeChartId,
        chartListContext: { listId, instrumentId },
      });
      activeTabId = activeChartId ?? "";
      return {
        workspace,
        // Siempre dirty: con autoSave no marcar dirty permitía que un sync/PUT
        // concurrente borrara pestañas recién abiertas.
        isDirty: true,
      };
    });

    flushDrawingAutoSave(get, true);
    if (get().workspace.preferences.autoSave) {
      requestWorkspaceAutoSave(get);
    }
    return activeTabId;
  },
  focusInstrumentsFromList: (listId, items) => {
    if (!items.length) return;
    set((state) => {
      let workspace = attachActiveTabListSnapshot(
        state.workspace,
        openDrawingEditorId(),
      );
      let charts = [...workspace.charts];
      let activeChartId = workspace.activeChartId;
      let lastInstrumentId = "";

      for (const item of items) {
        if (!item.instrumentId) continue;
        lastInstrumentId = item.instrumentId;
        const existingIndex = charts.findIndex(
          (tab) => tab.instrumentId === item.instrumentId,
        );
        if (existingIndex >= 0) {
          const existing = charts[existingIndex]!;
          charts[existingIndex] = {
            ...existing,
            label: item.label,
            sourceListId: listId,
          };
          activeChartId = charts[existingIndex]!.id;
        } else {
          const baseTab = createChartTabForInstrument(
            workspace,
            item.instrumentId,
            item.label,
            { sourceListId: listId },
          );
          charts = [...charts, baseTab];
          activeChartId = baseTab.id;
        }
      }

      workspace = finalizeChartWorkspace({
        ...workspace,
        charts,
        activeChartId,
        chartListContext: lastInstrumentId
          ? { listId, instrumentId: lastInstrumentId }
          : workspace.chartListContext,
      });
      return { workspace, isDirty: true };
    });
    flushDrawingAutoSave(get, true);
    if (get().workspace.preferences.autoSave) {
      requestWorkspaceAutoSave(get);
    }
  },
  setDrawingEditorOpen: (drawingId) => {
    if (drawingId) {
      getWorkspaceUiBridge().focusDrawing(drawingId);
      getWorkspaceUiBridge().setOpenDrawingEditorId(drawingId);
    } else {
      getWorkspaceUiBridge().setOpenDrawingEditorId(null);
    }
    set((state) => ({
      workspace: finalizeChartWorkspace(state.workspace),
      isDirty: !state.workspace.preferences.autoSave,
    }));
    flushDrawingAutoSave(get, true);
  },
  closeChartTab: (chartId) => {
    const closing = get().workspace.charts.find((tab) => tab.id === chartId);
    set((state) => {
      const workspace = finalizeChartWorkspace(state.workspace);
      const closingTab = workspace.charts.find((tab) => tab.id === chartId);
      const charts = workspace.charts.filter((tab) => tab.id !== chartId);
      const activeChartId =
        workspace.activeChartId === chartId
          ? (charts.at(-1)?.id ?? null)
          : workspace.activeChartId;
      const ctx = workspace.chartListContext;
      const chartListContext =
        ctx?.instrumentId === closingTab?.instrumentId
          ? null
          : workspace.chartListContext;
      const purged = pruneOrphanChartSnapshots({
        ...workspace,
        charts,
        activeChartId,
        chartListContext,
        preferences: {
          ...workspace.preferences,
          newChartTemplateChartId:
            closingTab?.id === workspace.preferences.newChartTemplateChartId
              ? null
              : (workspace.preferences.newChartTemplateChartId ?? null),
        },
        updatedAt: new Date().toISOString(),
      });
      const next = reconcileWorkspaceChartMembership(
        purged,
        state.chartListMembership,
      );
      return {
        workspace: syncSnapshotsFromCharts(next),
        isDirty: true,
      };
    });
    if (closing) {
      const editorId = getWorkspaceUiBridge().getOpenDrawingEditorId();
      if (
        editorId &&
        closing.drawings.some((drawing) => drawing.id === editorId)
      ) {
        getWorkspaceUiBridge().setOpenDrawingEditorId(null);
      }
    }
    scheduleWorkspaceSettingsPersist(get, set, true);
    flushDrawingAutoSave(get, true);
  },
  closeChartTabsForInstruments: (instrumentIds) => {
    const remove = new Set(instrumentIds.filter(Boolean));
    if (remove.size === 0) return;
    const before = get().workspace.charts;
    const closingTabs = before.filter(
      (tab) => tab.instrumentId && remove.has(tab.instrumentId),
    );
    if (closingTabs.length === 0) return;
    set((state) => {
      const workspace = finalizeChartWorkspace(state.workspace);
      const charts = workspace.charts.filter(
        (tab) => !tab.instrumentId || !remove.has(tab.instrumentId),
      );
      const activeStillOpen =
        workspace.activeChartId &&
        charts.some((tab) => tab.id === workspace.activeChartId);
      const activeChartId = activeStillOpen
        ? workspace.activeChartId
        : (charts.at(-1)?.id ?? null);
      const ctx = workspace.chartListContext;
      const chartListContext =
        ctx?.instrumentId && remove.has(ctx.instrumentId)
          ? null
          : workspace.chartListContext;
      const templateId = workspace.preferences.newChartTemplateChartId;
      const templateClosed =
        Boolean(templateId) && closingTabs.some((tab) => tab.id === templateId);
      const purged = pruneOrphanChartSnapshots({
        ...workspace,
        charts,
        activeChartId,
        chartListContext,
        preferences: {
          ...workspace.preferences,
          newChartTemplateChartId: templateClosed
            ? null
            : (workspace.preferences.newChartTemplateChartId ?? null),
        },
        updatedAt: new Date().toISOString(),
      });
      const next = reconcileWorkspaceChartMembership(
        purged,
        state.chartListMembership,
      );
      return {
        workspace: syncSnapshotsFromCharts(next),
        isDirty: true,
      };
    });
    const editorId = getWorkspaceUiBridge().getOpenDrawingEditorId();
    if (
      editorId &&
      closingTabs.some((tab) =>
        tab.drawings.some((drawing) => drawing.id === editorId),
      )
    ) {
      getWorkspaceUiBridge().setOpenDrawingEditorId(null);
    }
    scheduleWorkspaceSettingsPersist(get, set, true);
    flushDrawingAutoSave(get, true);
  },
  reorderChartTabsByInstrumentIds: (orderedInstrumentIds) => {
    const order = orderedInstrumentIds.filter(Boolean);
    if (order.length === 0) return;
    const rank = new Map(order.map((id, index) => [id, index]));
    set((state) => {
      const charts = [...state.workspace.charts];
      const selected: typeof charts = [];
      const rest: typeof charts = [];
      for (const tab of charts) {
        if (tab.instrumentId && rank.has(tab.instrumentId)) selected.push(tab);
        else rest.push(tab);
      }
      selected.sort((a, b) => {
        const ra = rank.get(a.instrumentId!) ?? 0;
        const rb = rank.get(b.instrumentId!) ?? 0;
        return ra - rb;
      });
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: [...selected, ...rest],
          updatedAt: new Date().toISOString(),
        }),
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set, true);
  },
  selectChartTab: (chartId) =>
    set((state) => {
      const tab = state.workspace.charts.find((item) => item.id === chartId);
      if (!tab) {
        return {
          workspace: { ...state.workspace, activeChartId: chartId },
          isDirty: true,
        };
      }
      const membership = state.chartListMembership;
      const listId = membership
        ? resolveValidSourceListIdForTab(state.workspace, tab, membership)
        : (tab.sourceListId ??
          state.workspace.chartListContext?.listId ??
          null);
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        activeChartId: chartId,
        chartListContext: listId
          ? { listId, instrumentId: tab.instrumentId }
          : membership
            ? null
            : state.workspace.chartListContext,
      });
      return { workspace, isDirty: true };
    }),
  /**
   * Antes clonaba la pestaña (mismo instrumentId → conflictos de sync/snapshots).
   * Política actual: una pestaña por valor; ancla el activo como plantilla de gráficos nuevos.
   */
  duplicateActiveChart: () => {
    const active = get().getActiveChartTab();
    if (!active) return;
    set((state) => {
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        activeChartId: active.id,
        preferences: {
          ...state.workspace.preferences,
          newChartTemplateChartId: active.id,
        },
        updatedAt: new Date().toISOString(),
      });
      return { workspace, isDirty: true };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  updateChartConfig: (patch) =>
    set((state) => {
      const chartId = patch.chartId ?? state.workspace.activeChartId;
      if (!chartId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) => {
            if (tab.id !== chartId) return tab;
            const nextChart = {
              ...tab.chart,
              grid: { ...tab.chart.grid, ...patch.grid },
              cursor: { ...tab.chart.cursor, ...patch.cursor },
              colors: { ...tab.chart.colors, ...patch.colors },
              display: { ...tab.chart.display, ...patch.display },
            };
            const indicatorInstances = patch.display
              ? seedIndicatorInstancesFromDisplay(nextChart.display)
              : tab.indicatorInstances;
            return {
              ...tab,
              chart: {
                ...nextChart,
                display: mergeDisplayFromInstances(
                  nextChart.display,
                  indicatorInstances,
                ),
              },
              indicatorInstances,
            };
          }),
        }),
        isDirty: true,
      };
    }),
  updateChartTimeframe: (timeframe, chartId) =>
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id === targetId ? { ...tab, timeframe } : tab,
          ),
        }),
        isDirty: true,
      };
    }),
  setChartDisplayFlags: (patch, chartId) =>
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) => {
            if (tab.id !== targetId) return tab;
            const nextDisplay = { ...tab.chart.display, ...patch };
            const indicatorInstances =
              seedIndicatorInstancesFromDisplay(nextDisplay);
            return {
              ...tab,
              chart: {
                ...tab.chart,
                display: mergeDisplayFromInstances(
                  nextDisplay,
                  indicatorInstances,
                ),
              },
              indicatorInstances,
            };
          }),
        }),
        isDirty: true,
      };
    }),
});
