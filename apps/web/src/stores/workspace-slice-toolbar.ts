import {
  normalizeChartToolbarGlobalConfig,
  DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG,
  normalizeChartDataStripConfig,
  normalizeChartTimeframeFavorites,
  toggleChartTimeframeFavoriteList,
  normalizeChartSeriesType,
  normalizeChartSeriesTypeParams,
  normalizeChartSeriesTypeFavorites,
  toggleChartSeriesTypeFavoriteList,
  normalizeChartInstrumentFieldFavorites,
  normalizeChartCursorFieldFavorites,
  normalizeIndicatorTemplateFavorites,
  toggleIndicatorTemplateFavoriteList,
  normalizeInspectorBarShortcutFavorites,
  toggleInspectorBarShortcutFavoriteList,
  normalizeDrawToolFavorites,
  toggleDrawToolFavoriteList,
  IMPLEMENTED_DRAW_TOOLS,
  toggleBarZoneFavoriteList,
  CHART_INSTRUMENT_BAR_ANCHOR,
  CHART_CURSOR_BAR_ANCHOR,
  normalizeChartToolbarChartOverrides,
  clampPricePanelHeightPct,
  applySubPanelWeightsToInstances,
  DEFAULT_INDICATOR_TEMPLATES,
  type ChartDrawTool,
} from "@bolsa/shared";
import { writeDrawToolFavoritesLocal } from "@/lib/draw-tool-favorites-storage";
import {
  type WorkspaceSlice,
  scheduleWorkspaceSettingsPersist,
  finalizeChartWorkspace,
} from "./workspace-store-core";

export const toolbarSlice: WorkspaceSlice = (get, set) => ({
  updateChartToolbarGlobal: (patch) => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        updatedAt: new Date().toISOString(),
        chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
          ...DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG,
          ...state.workspace.chartToolbarGlobal,
          ...patch,
          visibility: {
            ...DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG.visibility,
            ...state.workspace.chartToolbarGlobal?.visibility,
            ...patch.visibility,
          },
          appearance: {
            ...DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG.appearance,
            ...state.workspace.chartToolbarGlobal?.appearance,
            ...patch.appearance,
          },
          chartDefaults: patch.chartDefaults
            ? normalizeChartDataStripConfig({
                ...state.workspace.chartToolbarGlobal?.chartDefaults,
                ...patch.chartDefaults,
              })
            : state.workspace.chartToolbarGlobal?.chartDefaults,
          chartVisibilityDefaults: patch.chartVisibilityDefaults
            ? {
                ...DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG.chartVisibilityDefaults,
                ...state.workspace.chartToolbarGlobal?.chartVisibilityDefaults,
                ...patch.chartVisibilityDefaults,
              }
            : state.workspace.chartToolbarGlobal?.chartVisibilityDefaults,
          timeframeFavorites: patch.timeframeFavorites
            ? normalizeChartTimeframeFavorites(patch.timeframeFavorites)
            : state.workspace.chartToolbarGlobal?.timeframeFavorites,
          defaultSeriesType: patch.defaultSeriesType
            ? normalizeChartSeriesType(patch.defaultSeriesType)
            : state.workspace.chartToolbarGlobal?.defaultSeriesType,
          seriesTypeFavorites: patch.seriesTypeFavorites
            ? normalizeChartSeriesTypeFavorites(patch.seriesTypeFavorites)
            : state.workspace.chartToolbarGlobal?.seriesTypeFavorites,
          instrumentFieldFavorites: patch.instrumentFieldFavorites
            ? normalizeChartInstrumentFieldFavorites(
                patch.instrumentFieldFavorites,
              )
            : state.workspace.chartToolbarGlobal?.instrumentFieldFavorites,
          cursorFieldFavorites: patch.cursorFieldFavorites
            ? normalizeChartCursorFieldFavorites(patch.cursorFieldFavorites)
            : state.workspace.chartToolbarGlobal?.cursorFieldFavorites,
          indicatorTemplateFavorites: patch.indicatorTemplateFavorites
            ? normalizeIndicatorTemplateFavorites(
                patch.indicatorTemplateFavorites,
                (
                  state.workspace.indicatorTemplates ??
                  DEFAULT_INDICATOR_TEMPLATES
                ).map((t) => t.id),
              )
            : state.workspace.chartToolbarGlobal?.indicatorTemplateFavorites,
          inspectorBarShortcutFavorites:
            patch.inspectorBarShortcutFavorites !== undefined
              ? normalizeInspectorBarShortcutFavorites(
                  patch.inspectorBarShortcutFavorites,
                )
              : state.workspace.chartToolbarGlobal
                  ?.inspectorBarShortcutFavorites,
        }),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleChartTimeframeFavorite: (timeframe) => {
    set((state) => {
      const current = normalizeChartTimeframeFavorites(
        state.workspace.chartToolbarGlobal?.timeframeFavorites,
      );
      const next = toggleChartTimeframeFavoriteList(current, timeframe);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            timeframeFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleChartSeriesTypeFavorite: (seriesType) => {
    set((state) => {
      const current = normalizeChartSeriesTypeFavorites(
        state.workspace.chartToolbarGlobal?.seriesTypeFavorites,
      );
      const next = toggleChartSeriesTypeFavoriteList(current, seriesType);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            seriesTypeFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleIndicatorTemplateFavorite: (templateId) => {
    set((state) => {
      const validIds = (
        state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES
      ).map((t) => t.id);
      const current = normalizeIndicatorTemplateFavorites(
        state.workspace.chartToolbarGlobal?.indicatorTemplateFavorites,
        validIds,
      );
      const next = toggleIndicatorTemplateFavoriteList(current, templateId);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            indicatorTemplateFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleInspectorBarShortcutFavorite: (shortcutId) => {
    set((state) => {
      const current = normalizeInspectorBarShortcutFavorites(
        state.workspace.chartToolbarGlobal?.inspectorBarShortcutFavorites,
      );
      const next = toggleInspectorBarShortcutFavoriteList(current, shortcutId);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            inspectorBarShortcutFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleDrawToolFavorite: (drawTool) => {
    let nextFavorites: ChartDrawTool[] = [];
    set((state) => {
      const current = normalizeDrawToolFavorites(
        state.workspace.chartToolbarGlobal?.drawToolFavorites,
        IMPLEMENTED_DRAW_TOOLS,
      );
      const next = toggleDrawToolFavoriteList(current, drawTool);
      nextFavorites = normalizeDrawToolFavorites(next, IMPLEMENTED_DRAW_TOOLS);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            drawToolFavorites: nextFavorites,
          }),
        },
        isDirty: true,
      };
    });
    writeDrawToolFavoritesLocal(nextFavorites);
    scheduleWorkspaceSettingsPersist(get, set);
  },
  updateChartToolbarForChart: (chartId, patch) => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        updatedAt: new Date().toISOString(),
        charts: state.workspace.charts.map((tab) =>
          tab.id !== chartId
            ? tab
            : {
                ...tab,
                toolbar:
                  patch === null
                    ? undefined
                    : normalizeChartToolbarChartOverrides({
                        ...tab.toolbar,
                        ...patch,
                        visibility: patch.visibility
                          ? {
                              ...tab.toolbar?.visibility,
                              ...patch.visibility,
                            }
                          : tab.toolbar?.visibility,
                        layout: patch.layout
                          ? { ...tab.toolbar?.layout, ...patch.layout }
                          : tab.toolbar?.layout,
                        appearance: patch.appearance
                          ? {
                              ...tab.toolbar?.appearance,
                              ...patch.appearance,
                            }
                          : tab.toolbar?.appearance,
                      }),
              },
        ),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
  updateChartPricePanelHeight: (pct, chartId) =>
    set((state) => {
      const id = chartId ?? state.workspace.activeChartId;
      if (!id) return state;
      const nextPct = clampPricePanelHeightPct(pct);
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          charts: state.workspace.charts.map((tab) =>
            tab.id === id ? { ...tab, pricePanelHeightPct: nextPct } : tab,
          ),
        },
        isDirty: true,
      };
    }),
  setSubPanelWeights: (weights, chartId) =>
    set((state) => {
      const id = chartId ?? state.workspace.activeChartId;
      if (!id) return state;
      const weightMap = new Map(Object.entries(weights));
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          charts: state.workspace.charts.map((tab) =>
            tab.id === id
              ? {
                  ...tab,
                  indicatorInstances: applySubPanelWeightsToInstances(
                    tab.indicatorInstances,
                    weightMap,
                  ),
                }
              : tab,
          ),
        },
        isDirty: true,
      };
    }),
  updateChartSeriesTypeParams: (patch, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id === targetId
              ? {
                  ...tab,
                  seriesTypeParams: {
                    ...normalizeChartSeriesTypeParams(tab.seriesTypeParams),
                    ...patch,
                  },
                }
              : tab,
          ),
        }),
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleInstrumentFieldFavorite: (field) => {
    set((state) => {
      const current = normalizeChartInstrumentFieldFavorites(
        state.workspace.chartToolbarGlobal?.instrumentFieldFavorites,
      );
      const next = toggleBarZoneFavoriteList(
        current,
        field,
        CHART_INSTRUMENT_BAR_ANCHOR,
      );
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            instrumentFieldFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleCursorFieldFavorite: (field) => {
    set((state) => {
      const current = normalizeChartCursorFieldFavorites(
        state.workspace.chartToolbarGlobal?.cursorFieldFavorites,
      );
      const next = toggleBarZoneFavoriteList(
        current,
        field,
        CHART_CURSOR_BAR_ANCHOR,
      );
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            cursorFieldFavorites: next,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  updateChartSeriesType: (seriesType, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const nextType = normalizeChartSeriesType(seriesType);
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id === targetId ? { ...tab, seriesType: nextType } : tab,
          ),
        }),
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  resetChartToolbarForChart: (chartId) => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        updatedAt: new Date().toISOString(),
        charts: state.workspace.charts.map((tab) =>
          tab.id === chartId ? { ...tab, toolbar: undefined } : tab,
        ),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
});
