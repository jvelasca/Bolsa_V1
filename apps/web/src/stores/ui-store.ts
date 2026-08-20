import type { ChartDrawTool } from "@bolsa/shared";
import type { DrawingToolGroupId } from "@bolsa/shared";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { groupForDrawTool } from "@/features/charts/chart-drawing-tools";
import type { ChartInspectorNavigateRequest } from "@/features/charts/chart-inspector-nav";
import { writeDrawToolSessionLocal } from "@/lib/draw-tool-session-storage";
export type PlatformConfigTab =
  | "general"
  | "investor-profile"
  | "commissions"
  | "notifications"
  | "sounds"
  | "confirmations"
  | "shortcuts"
  | "bd"
  | "other";

interface UiState {
  listHubOpen: boolean;
  workspacePickerOpen: boolean;
  listManagerOpen: boolean;
  instrumentSyncTarget: { instrumentId: string; symbol: string } | null;
  chartDrawTool: ChartDrawTool;
  /** Última herramienta elegida por grupo (para recordar sin forzar al abrir el menú). */
  lastDrawToolByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
  selectedDrawingId: string | null;
  openDrawingEditorId: string | null;
  selectedIndicatorInstanceId: string | null;
  indicatorConfigTarget: { chartId: string; instanceId: string } | null;
  indicatorsCatalogOpen: boolean;
  indicatorTemplatesOpen: boolean;
  drawingTemplatesOpen: boolean;
  chartGlobalBarSettingsOpen: boolean;
  chartDataBarSettingsOpen: boolean;
  platformConfigOpen: boolean;
  platformConfigTab: PlatformConfigTab;
  chartInspectorNav: ChartInspectorNavigateRequest | null;
  chartInspectorActiveShortcutKey: string | null;
  createAccountWizardOpen: boolean;
  openCreateAccountWizard: () => void;
  closeCreateAccountWizard: () => void;
  openChartGlobalBarSettings: () => void;
  closeChartGlobalBarSettings: () => void;
  openChartDataBarSettings: () => void;
  closeChartDataBarSettings: () => void;
  openListHub: () => void;
  closeListHub: () => void;
  openWorkspacePicker: () => void;
  closeWorkspacePicker: () => void;
  visualizationLogOpen: boolean;
  openVisualizationLog: () => void;
  closeVisualizationLog: () => void;
  openListManager: () => void;
  closeListManager: () => void;
  openInstrumentSyncDialog: (instrumentId: string, symbol: string) => void;
  closeInstrumentSyncDialog: () => void;
  setChartDrawTool: (tool: ChartDrawTool) => void;
  focusDrawing: (drawingId: string) => void;
  setSelectedDrawingId: (id: string | null) => void;
  setOpenDrawingEditorId: (id: string | null) => void;
  setSelectedIndicatorInstanceId: (id: string | null) => void;
  openIndicatorConfig: (chartId: string, instanceId: string) => void;
  closeIndicatorConfig: () => void;
  openIndicatorsCatalog: () => void;
  closeIndicatorsCatalog: () => void;
  openIndicatorTemplates: () => void;
  closeIndicatorTemplates: () => void;
  openDrawingTemplates: () => void;
  closeDrawingTemplates: () => void;
  openPlatformConfig: (tab?: PlatformConfigTab) => void;
  closePlatformConfig: () => void;
  setPlatformConfigTab: (tab: PlatformConfigTab) => void;
  setChartInspectorNav: (request: ChartInspectorNavigateRequest | null) => void;
  setChartInspectorActiveShortcutKey: (key: string | null) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      chartGlobalBarSettingsOpen: false,
      chartDataBarSettingsOpen: false,
      listHubOpen: false,
      workspacePickerOpen: false,
      listManagerOpen: false,
      instrumentSyncTarget: null,
      chartDrawTool: "select",
      lastDrawToolByGroup: { cursor: "select" },
      selectedDrawingId: null,
      openDrawingEditorId: null,
      selectedIndicatorInstanceId: null,
      indicatorConfigTarget: null,
      indicatorsCatalogOpen: false,
      indicatorTemplatesOpen: false,
      drawingTemplatesOpen: false,
      platformConfigOpen: false,
      platformConfigTab: "general",
      chartInspectorNav: null,
      chartInspectorActiveShortcutKey: null,
      createAccountWizardOpen: false,
      openChartGlobalBarSettings: () =>
        set({ chartGlobalBarSettingsOpen: true }),
      closeChartGlobalBarSettings: () =>
        set({ chartGlobalBarSettingsOpen: false }),
      openChartDataBarSettings: () => set({ chartDataBarSettingsOpen: true }),
      closeChartDataBarSettings: () => set({ chartDataBarSettingsOpen: false }),
      openListHub: () => {
        void import("@/features/trading/open-list-hub").then(
          ({ openListHubWorkspaceAction }) => {
            openListHubWorkspaceAction();
          },
        );
      },
      closeListHub: () => {},
      openWorkspacePicker: () => set({ workspacePickerOpen: true }),
      closeWorkspacePicker: () => set({ workspacePickerOpen: false }),
      visualizationLogOpen: false,
      openVisualizationLog: () => set({ visualizationLogOpen: true }),
      closeVisualizationLog: () => set({ visualizationLogOpen: false }),
      openListManager: () => set({ listHubOpen: true }),
      closeListManager: () => set({ listHubOpen: false }),
      openInstrumentSyncDialog: (instrumentId, symbol) =>
        set({ instrumentSyncTarget: { instrumentId, symbol } }),
      closeInstrumentSyncDialog: () => set({ instrumentSyncTarget: null }),
      setChartDrawTool: (tool) =>
        set((state) => {
          const group = groupForDrawTool(tool);
          const lastDrawToolByGroup = group
            ? { ...state.lastDrawToolByGroup, [group]: tool }
            : state.lastDrawToolByGroup;
          writeDrawToolSessionLocal({
            chartDrawTool: tool,
            lastDrawToolByGroup,
          });
          return {
            chartDrawTool: tool,
            lastDrawToolByGroup,
            selectedDrawingId: null,
            openDrawingEditorId: null,
          };
        }),
      focusDrawing: (drawingId) =>
        set(() => ({
          chartDrawTool: "select",
          selectedDrawingId: drawingId,
          selectedIndicatorInstanceId: null,
        })),
      setSelectedDrawingId: (id) =>
        set((state) => ({
          selectedDrawingId: id,
          openDrawingEditorId: id ? state.openDrawingEditorId : null,
          selectedIndicatorInstanceId: id
            ? null
            : state.selectedIndicatorInstanceId,
        })),
      setOpenDrawingEditorId: (id) => set({ openDrawingEditorId: id }),
      setSelectedIndicatorInstanceId: (id) =>
        set((state) => ({
          selectedIndicatorInstanceId: id,
          selectedDrawingId: id ? null : state.selectedDrawingId,
        })),
      openIndicatorConfig: (chartId, instanceId) =>
        set({
          indicatorConfigTarget: { chartId, instanceId },
          selectedIndicatorInstanceId: instanceId,
          selectedDrawingId: null,
        }),
      closeIndicatorConfig: () => set({ indicatorConfigTarget: null }),
      openIndicatorsCatalog: () => set({ indicatorsCatalogOpen: true }),
      closeIndicatorsCatalog: () => set({ indicatorsCatalogOpen: false }),
      openIndicatorTemplates: () => set({ indicatorTemplatesOpen: true }),
      closeIndicatorTemplates: () => set({ indicatorTemplatesOpen: false }),
      openDrawingTemplates: () => set({ drawingTemplatesOpen: true }),
      closeDrawingTemplates: () => set({ drawingTemplatesOpen: false }),
      openPlatformConfig: (tab = "general") =>
        set({ platformConfigOpen: true, platformConfigTab: tab }),
      closePlatformConfig: () => set({ platformConfigOpen: false }),
      setPlatformConfigTab: (tab) => set({ platformConfigTab: tab }),
      setChartInspectorNav: (request) => set({ chartInspectorNav: request }),
      setChartInspectorActiveShortcutKey: (key) =>
        set({ chartInspectorActiveShortcutKey: key }),
      openCreateAccountWizard: () => set({ createAccountWizardOpen: true }),
      closeCreateAccountWizard: () => set({ createAccountWizardOpen: false }),
    }),
    {
      name: "bolsa-chart-draw-tool-session",
      partialize: (state) => ({
        chartDrawTool: state.chartDrawTool,
        lastDrawToolByGroup: state.lastDrawToolByGroup,
      }),
    },
  ),
);
