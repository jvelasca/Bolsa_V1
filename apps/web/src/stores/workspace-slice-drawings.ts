import {
  createBlankDrawingTemplate,
  newChartDrawingTemplateId,
  styleMemoryFromTemplate,
  styleMemoryFromDrawing,
  drawingPatchFromTemplate,
  mergeDrawToolStyleMemory,
  normalizeChartToolbarGlobalConfig,
  drawToolForDrawing,
  type ChartDrawTool,
  type ChartDrawingTemplate,
  type DrawToolStyleMemory,
} from "@bolsa/shared";
import {
  type WorkspaceSlice,
  finalizeChartWorkspace,
  chartPersistBackupFrom,
  writeChartPersistBackupSync,
  flushDrawingAutoSave,
  scheduleWorkspaceServerSave,
  scheduleWorkspaceSettingsPersist,
  findDrawingTemplate,
  patchHasStyleMemory,
  styleMemoryFromPatch,
} from "./workspace-store-core";

export const drawingsSlice: WorkspaceSlice = (get, set) => ({
  addChartDrawing: (drawing, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((tab) =>
          tab.id !== targetId
            ? tab
            : { ...tab, drawings: [...tab.drawings, drawing] },
        ),
      });
      return {
        workspace,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        isDirty: true,
      };
    });
    const { activeWorkspaceId, recents, workspace } = get();
    writeChartPersistBackupSync(
      activeWorkspaceId,
      recents,
      chartPersistBackupFrom(workspace),
    );
    flushDrawingAutoSave(get, true);
  },
  updateChartDrawing: (drawingId, patch, chartId) => {
    let styleTool: ChartDrawTool | null = null;
    let stylePatch: DrawToolStyleMemory | null = null;

    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      const drawing = tab?.drawings.find((item) => item.id === drawingId);
      if (drawing && patchHasStyleMemory(patch)) {
        styleTool = drawToolForDrawing(drawing);
        stylePatch = styleMemoryFromPatch(patch);
      }
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((tabItem) =>
          tabItem.id !== targetId
            ? tabItem
            : {
                ...tabItem,
                drawings: tabItem.drawings.map((item) =>
                  item.id !== drawingId ? item : { ...item, ...patch },
                ),
              },
        ),
      });
      return {
        workspace,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        isDirty: true,
      };
    });
    if (styleTool && stylePatch && Object.keys(stylePatch).length > 0) {
      get().rememberDrawStyleForTool(styleTool, stylePatch);
    }
    const { activeWorkspaceId, recents, workspace } = get();
    writeChartPersistBackupSync(
      activeWorkspaceId,
      recents,
      chartPersistBackupFrom(workspace),
    );
    flushDrawingAutoSave(get, true);
  },
  removeChartDrawing: (drawingId, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((tab) =>
          tab.id !== targetId
            ? tab
            : {
                ...tab,
                drawings: tab.drawings.filter((d) => d.id !== drawingId),
              },
        ),
      });
      return {
        workspace,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        isDirty: true,
      };
    });
    const { activeWorkspaceId, recents, workspace } = get();
    writeChartPersistBackupSync(
      activeWorkspaceId,
      recents,
      chartPersistBackupFrom(workspace),
    );
    flushDrawingAutoSave(get, true);
  },
  clearChartDrawings: (chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const workspace = finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((tab) =>
          tab.id !== targetId ? tab : { ...tab, drawings: [] },
        ),
      });
      return {
        workspace,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        isDirty: true,
      };
    });
    const { activeWorkspaceId, recents, workspace } = get();
    writeChartPersistBackupSync(
      activeWorkspaceId,
      recents,
      chartPersistBackupFrom(workspace),
    );
    flushDrawingAutoSave(get, true);
  },
  flushDrawingSave: () => {
    scheduleWorkspaceServerSave(get, true);
  },
  addDrawingTemplate: () => {
    const template = createBlankDrawingTemplate();
    set((state) => ({
      workspace: {
        ...state.workspace,
        drawingTemplates: [
          ...(state.workspace.drawingTemplates ?? []),
          template,
        ],
      },
      isDirty: true,
    }));
    return template;
  },
  updateDrawingTemplate: (templateId, patch) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        drawingTemplates: (state.workspace.drawingTemplates ?? []).map(
          (template) => {
            if (template.id !== templateId) return template;
            return {
              ...template,
              ...patch,
              style: patch.style
                ? { ...template.style, ...patch.style }
                : template.style,
              text: patch.text
                ? { ...template.text, ...patch.text }
                : template.text,
              coordinates: patch.coordinates
                ? { ...template.coordinates, ...patch.coordinates }
                : template.coordinates,
              visibility: patch.visibility
                ? { ...template.visibility, ...patch.visibility }
                : template.visibility,
            };
          },
        ),
      },
      isDirty: true,
    })),
  removeDrawingTemplate: (templateId) =>
    set((state) => {
      const target = state.workspace.drawingTemplates?.find(
        (t) => t.id === templateId,
      );
      if (!target || target.builtin) return state;
      const activeDrawingTemplateByTool = {
        ...(state.workspace.activeDrawingTemplateByTool ?? {}),
      };
      for (const [tool, id] of Object.entries(activeDrawingTemplateByTool)) {
        if (id === templateId)
          delete activeDrawingTemplateByTool[tool as ChartDrawTool];
      }
      return {
        workspace: {
          ...state.workspace,
          drawingTemplates: (state.workspace.drawingTemplates ?? []).filter(
            (t) => t.id !== templateId,
          ),
          activeDrawingTemplateByTool,
        },
        isDirty: true,
      };
    }),
  duplicateDrawingTemplate: (templateId) => {
    const source = get().workspace.drawingTemplates?.find(
      (t) => t.id === templateId,
    );
    if (!source) return null;
    const copy: ChartDrawingTemplate = {
      ...source,
      id: newChartDrawingTemplateId(),
      name: `${source.name} (copia)`,
      builtin: false,
      style: { ...source.style },
      text: { ...source.text },
      coordinates: { ...source.coordinates },
      visibility: { ...source.visibility },
      drawingTypes: [...source.drawingTypes],
    };
    set((state) => ({
      workspace: {
        ...state.workspace,
        drawingTemplates: [...(state.workspace.drawingTemplates ?? []), copy],
      },
      isDirty: true,
    }));
    return copy;
  },
  setActiveDrawingTemplateForTool: (tool, templateId) => {
    set((state) => {
      const activeDrawingTemplateByTool = {
        ...(state.workspace.activeDrawingTemplateByTool ?? {}),
      };
      const lastDrawStyleByTool = {
        ...(state.workspace.chartToolbarGlobal?.lastDrawStyleByTool ?? {}),
      };
      if (templateId) {
        activeDrawingTemplateByTool[tool] = templateId;
        const template = findDrawingTemplate(
          state.workspace.drawingTemplates,
          templateId,
        );
        if (template) {
          lastDrawStyleByTool[tool] = styleMemoryFromTemplate(template);
        }
      } else {
        delete activeDrawingTemplateByTool[tool];
      }
      return {
        workspace: {
          ...state.workspace,
          updatedAt: new Date().toISOString(),
          activeDrawingTemplateByTool,
          chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
            ...state.workspace.chartToolbarGlobal,
            lastDrawStyleByTool,
          }),
        },
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  applyDrawingTemplate: (drawingId, templateId, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      const drawing = tab?.drawings.find((item) => item.id === drawingId);
      const template = findDrawingTemplate(
        state.workspace.drawingTemplates,
        templateId,
      );
      if (!tab || !drawing || !template) return state;
      const patch = drawingPatchFromTemplate(drawing, template);
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((item) =>
            item.id !== targetId
              ? item
              : {
                  ...item,
                  drawings: item.drawings.map((itemDrawing) =>
                    itemDrawing.id !== drawingId
                      ? itemDrawing
                      : { ...itemDrawing, ...patch },
                  ),
                },
          ),
        }),
        isDirty: !state.workspace.preferences.autoSave,
      };
    });
    flushDrawingAutoSave(get, true);
  },
  rememberDrawStyleForTool: (tool, patch) => {
    if (!patch || Object.keys(patch).length === 0) return;
    const state = get();
    const prev = state.workspace.chartToolbarGlobal?.lastDrawStyleByTool ?? {};
    const merged = mergeDrawToolStyleMemory(prev[tool], patch);
    const current = prev[tool];
    if (
      current &&
      current.color === merged.color &&
      current.lineWidth === merged.lineWidth &&
      current.lineStyle === merged.lineStyle &&
      current.fillOpacity === merged.fillOpacity &&
      current.strokeOpacity === merged.strokeOpacity &&
      current.fontSize === merged.fontSize
    ) {
      return;
    }
    set((inner) => ({
      workspace: {
        ...inner.workspace,
        updatedAt: new Date().toISOString(),
        chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
          ...inner.workspace.chartToolbarGlobal,
          lastDrawStyleByTool: { ...prev, [tool]: merged },
        }),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
  rememberDrawStyleFromDrawing: (drawing, sourceTool) => {
    const tool = sourceTool ?? drawToolForDrawing(drawing);
    if (!tool) return;
    get().rememberDrawStyleForTool(tool, styleMemoryFromDrawing(drawing));
  },
  toggleChartDrawingsLayerHidden: (chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id === targetId
              ? { ...tab, drawingsLayerHidden: !tab.drawingsLayerHidden }
              : tab,
          ),
        }),
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
  toggleChartDrawingsLayerLocked: (chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id === targetId
              ? { ...tab, drawingsLayerLocked: !tab.drawingsLayerLocked }
              : tab,
          ),
        }),
        isDirty: true,
      };
    });
    scheduleWorkspaceSettingsPersist(get, set);
  },
});
