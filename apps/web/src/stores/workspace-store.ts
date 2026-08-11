/**
 * Estado del espacio de trabajo de trading — persistido en servidor (`/api/workspaces`).
 *
 * ## Producto (UI)
 * - Cabecera: chip con el nombre → abre el gestor (`WorkspacePickerDialog`).
 * - Arranque: último `activeWorkspaceId` local; si no, espacio `isDefault` (preferido); si no, el primero.
 * - Nuevo = documento en blanco; Duplicar = clona el activo (gráficos/listas/dibujos + dock).
 *
 * ## Persistencia
 * - Servidor: documento (`WorkspaceDocument`). `dockLayout` en API es legado (chrome por dispositivo).
 * - Local: `bolsa-workspace-meta` (`activeWorkspaceId`, `recents`, `chartPersistBackup`).
 * - Preferencias: `autoSave`, `openOnStartup` (→ `isDefault` al guardar).
 *
 * @see docs/WORKSPACE_PERSISTENCE.md
 * @see apps/web/src/features/workspace/workspace-picker-dialog.tsx
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  DEFAULT_CHART_CONFIG,
  DEFAULT_LIST_CONFIG,
  DEFAULT_LIST_PANEL_SIZE_PCT,
  DEFAULT_RIGHT_PANEL_SIZE_PCT,
  MAX_LIST_PANEL_SIZE_PCT,
  MAX_RIGHT_PANEL_SIZE_PCT,
  MIN_LIST_PANEL_SIZE_PCT,
  MIN_RIGHT_PANEL_SIZE_PCT,
  normalizeColumnLayout,
  normalizeChartDataStripConfig,
  normalizeChartToolbarGlobalConfig,
  normalizeChartToolbarChartOverrides,
  normalizeChartTimeframeFavorites,
  toggleChartTimeframeFavoriteList,
  normalizeChartInstrumentFieldFavorites,
  normalizeChartCursorFieldFavorites,
  toggleBarZoneFavoriteList,
  CHART_INSTRUMENT_BAR_ANCHOR,
  CHART_CURSOR_BAR_ANCHOR,
  type ChartInstrumentBarField,
  type ChartCursorBarField,
  DEFAULT_CHART_TOOLBAR_GLOBAL_CONFIG,
  visibleListColumns,
  createBlankDrawingTemplate,
  normalizeDrawingTemplates,
  DEFAULT_DRAWING_TEMPLATES,
  drawingPatchFromTemplate,
  newChartDrawingTemplateId,
  createBlankIndicatorTemplate,
  DEFAULT_INDICATOR_TEMPLATES,
  BUILTIN_PERSONAL_TEMPLATE_ID,
  ensurePresetInTemplate,
  favoriteRefKey,
  findInstanceByRef,
  indicatorTemplateFromInstances,
  instancesFromTemplate,
  newIndicatorTemplateId,
  normalizeIndicatorFavoritesByListId,
  normalizeIndicatorTemplates,
  normalizeIndicatorPresets,
  DEFAULT_SYSTEM_PRESETS,
  instanceFromPreset,
  findInstanceByPreset,
  findIndicatorPreset,
  createAiIndicatorVariantPreset,
  forkIndicatorPreset,
  duplicateIndicatorPreset,
  newIndicatorPresetId,
  presetFromInstance,
  togglePresetInTemplate,
  templateHasIndicators,
  normalizeIndicatorTemplateFavorites,
  toggleIndicatorTemplateFavoriteList,
  normalizeInspectorBarShortcutFavorites,
  toggleInspectorBarShortcutFavoriteList,
  type ChartInspectorBarShortcutId,
  applySubPanelWeightsToInstances,
  assignSubPanelWeightOnAdd,
  adjustSubPanelWeightsAfterVisibilityChange,
  redistributeSubPanelWeightAfterRemove,
  rebalanceSubPanelWeights,
  isSubPanelInstance,
  visibleSubPanelInstances,
  applyChartNewTabSeed,
  extractChartNewTabSeed,
  normalizeNewChartTemplateChartId,
  resolveNewChartTemplateTab,
  type IndicatorPreset,
  DEFAULT_INDICATOR_FAVORITES,
  type IndicatorFavoriteRef,
  type IndicatorTemplate,
  type ChartDrawTool,
  type ChartDrawingTemplate,
  type ChartInstanceConfig,
  sanitizeChartDrawings,
  type ChartDrawing,
  type ChartDrawingVertexPatch,
  type ChartIndicatorInstance,
  type ChartTabState,
  type ChartTimeframe,
  type ListPanelConfig,
  type ChartToolbarChartOverrides,
  type ChartToolbarGlobalConfig,
  type TradingDockLayoutPrefs,
  type WorkspaceDocument,
  type WorkspaceSummaryDto,
  DEFAULT_CHART_TIMEFRAME,
  DEFAULT_CHART_SERIES_TYPE,
  normalizeChartSeriesType,
  normalizeChartSeriesTypeFavorites,
  normalizeChartSeriesTypeParams,
  toggleChartSeriesTypeFavoriteList,
  toggleDrawToolFavoriteList,
  normalizeDrawToolFavorites,
  IMPLEMENTED_DRAW_TOOLS,
  mergeDrawToolStyleMemory,
  styleMemoryFromTemplate,
  styleMemoryFromDrawing,
  drawToolForDrawing,
  type DrawToolStyleMemory,
  type ChartSeriesType,
  type ChartSeriesTypeParams,
  clampPricePanelHeightPct,
  resolvePricePanelHeightPct,
  displayPatchForInstance,
  findIndicatorDefinition,
  findInstanceBySpec,
  hasDuplicateInstance,
  instanceSpecKey,
  dataParametersKey,
  isChartTimeframe,
  mergeDisplayFromInstances,
  normalizeParameters,
  newIndicatorInstanceId,
  seedIndicatorInstancesFromDisplay,
} from "@bolsa/shared";
import { api, ApiError } from "@/lib/api";
import {
  attachActiveTabListSnapshot,
  mergeWorkspaceChartState,
  syncSnapshotsFromCharts,
  pruneOrphanChartSnapshots,
  totalChartDrawings,
  totalSnapshotDrawings,
  workspaceTimestamp,
} from "@/lib/chart-list-snapshot";
import { dedupeChartTabsByInstrument } from "@/lib/chart-tab-uniqueness";
import {
  readDrawToolFavoritesLocal,
  writeDrawToolFavoritesLocal,
} from "@/lib/draw-tool-favorites-storage";
import {
  applyDrawToolSessionToUi,
  drawToolSessionFromUi,
  readDrawToolSessionLocal,
} from "@/lib/draw-tool-session-storage";
import {
  membershipFingerprint,
  reconcileWorkspaceChartMembership,
  resolveValidSourceListIdForTab,
  type ChartListMembershipSnapshot,
} from "@/lib/chart-list-membership";
import {
  buildWorkspacePayload,
  DEFAULT_DOCK_LAYOUT,
  readLegacyDockFromStorage,
  readLegacyWorkspaceFromStorage,
} from "@/lib/workspace-payload";
import { getWorkspaceUiBridge } from "@/stores/workspace-ui-bridge";
import {
  createInspectorNavRequest,
  inspectorNavigateKey,
  type ChartInspectorNavigateInput,
} from "@/features/charts/chart-inspector-nav";

let chartTabIdSeq = 0;

function newChartTabId(): string {
  // Date.now() solo no basta: Abrir gráficos abre N tabs en el mismo ms y
  // ids duplicados colapsan keys de React + el Map del saveToServer.
  chartTabIdSeq += 1;
  return `chart-${Date.now().toString(36)}-${chartTabIdSeq.toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

let drawingAutoSaveTimer: ReturnType<typeof setTimeout> | null = null;
let settingsPersistTimer: ReturnType<typeof setTimeout> | null = null;
let workspaceServerSaveTimer: ReturnType<typeof setTimeout> | null = null;
let saveQueued = false;

/** Debounce único para autosave al servidor (M7). */
export const WORKSPACE_AUTOSAVE_DEBOUNCE_MS = 1000;

function findDrawingTemplate(
  templates: ChartDrawingTemplate[] | undefined,
  templateId: string,
): ChartDrawingTemplate | undefined {
  const pool = templates?.length ? templates : DEFAULT_DRAWING_TEMPLATES;
  return pool.find((item) => item.id === templateId);
}

const STYLE_MEMORY_KEYS = [
  "color",
  "lineWidth",
  "lineStyle",
  "fillOpacity",
  "strokeOpacity",
  "fontSize",
] as const;

function patchHasStyleMemory(patch: ChartDrawingVertexPatch): boolean {
  return STYLE_MEMORY_KEYS.some((key) => key in patch);
}

function styleMemoryFromPatch(
  patch: ChartDrawingVertexPatch,
): DrawToolStyleMemory {
  const memory: DrawToolStyleMemory = {};
  if ("color" in patch && patch.color) memory.color = patch.color;
  if ("lineWidth" in patch && patch.lineWidth != null)
    memory.lineWidth = patch.lineWidth;
  if ("lineStyle" in patch && patch.lineStyle)
    memory.lineStyle = patch.lineStyle;
  if ("fillOpacity" in patch && patch.fillOpacity != null)
    memory.fillOpacity = patch.fillOpacity;
  if ("strokeOpacity" in patch && patch.strokeOpacity != null) {
    memory.strokeOpacity = patch.strokeOpacity;
  }
  if ("fontSize" in patch && patch.fontSize != null)
    memory.fontSize = patch.fontSize;
  return memory;
}

function applyLocalDrawToolFavorites(
  workspace: WorkspaceDocument,
): WorkspaceDocument {
  const localFavorites = readDrawToolFavoritesLocal();
  if (!localFavorites?.length) return workspace;
  return {
    ...workspace,
    chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
      ...workspace.chartToolbarGlobal,
      drawToolFavorites: localFavorites,
    }),
  };
}

function applyLocalDrawToolSession(
  workspace: WorkspaceDocument,
): WorkspaceDocument {
  const local = readDrawToolSessionLocal();
  const global = workspace.chartToolbarGlobal;
  const chartDrawTool = local?.chartDrawTool ?? global?.activeDrawTool;
  const lastDrawToolByGroup =
    local?.lastDrawToolByGroup ?? global?.lastDrawToolByGroup;
  if (local) {
    applyDrawToolSessionToUi(local);
  } else if (chartDrawTool) {
    applyDrawToolSessionToUi({
      chartDrawTool,
      lastDrawToolByGroup: lastDrawToolByGroup ?? {},
    });
  }
  if (!chartDrawTool && !lastDrawToolByGroup) return workspace;
  return {
    ...workspace,
    chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
      ...global,
      activeDrawTool: chartDrawTool,
      lastDrawToolByGroup,
    }),
  };
}

function flushDrawingAutoSave(get: () => WorkspaceState, immediate = false) {
  if (drawingAutoSaveTimer) {
    clearTimeout(drawingAutoSaveTimer);
    drawingAutoSaveTimer = null;
  }
  if (immediate) {
    requestWorkspaceAutoSave(get, true);
    return;
  }
  drawingAutoSaveTimer = setTimeout(() => {
    drawingAutoSaveTimer = null;
    requestWorkspaceAutoSave(get);
  }, 450);
}

/** Un solo timer de guardado en servidor — evita duplicar con WorkspaceAutoSave. */
function requestWorkspaceAutoSave(
  get: () => WorkspaceState,
  immediate = false,
) {
  const state = get();
  if (!state.hydrated || !state.workspace.preferences.autoSave) return;

  if (workspaceServerSaveTimer) {
    clearTimeout(workspaceServerSaveTimer);
    workspaceServerSaveTimer = null;
  }

  if (immediate) {
    void state.saveToServer();
    return;
  }

  workspaceServerSaveTimer = setTimeout(() => {
    workspaceServerSaveTimer = null;
    const current = get();
    if (!current.hydrated || !current.workspace.preferences.autoSave) return;
    void current.saveToServer();
  }, WORKSPACE_AUTOSAVE_DEBOUNCE_MS);
}

/** @deprecated Usa requestWorkspaceAutoSave */
function scheduleWorkspaceServerSave(
  get: () => WorkspaceState,
  immediate = false,
) {
  requestWorkspaceAutoSave(get, immediate);
}

/** Backup local inmediato + guardado en servidor para listas y barras. */
function scheduleWorkspaceSettingsPersist(
  get: () => WorkspaceState,
  set: (partial: Partial<WorkspaceState>) => void,
  immediate = false,
) {
  if (settingsPersistTimer) {
    clearTimeout(settingsPersistTimer);
    settingsPersistTimer = null;
  }
  const run = () => {
    const state = get();
    if (!state.hydrated) return;
    const backup = chartPersistBackupFrom(state.workspace);
    writeChartPersistBackupSync(state.activeWorkspaceId, state.recents, backup);
    set({ chartPersistBackup: backup });
    requestWorkspaceAutoSave(get);
  };
  if (immediate) {
    run();
    return;
  }
  settingsPersistTimer = setTimeout(() => {
    settingsPersistTimer = null;
    run();
  }, 500);
}

function mergeListConfigPatch(
  current: ListPanelConfig,
  patch: Partial<ListPanelConfig>,
): ListPanelConfig {
  return {
    ...current,
    ...patch,
    columnLayoutsByListId: patch.columnLayoutsByListId
      ? {
          ...(current.columnLayoutsByListId ?? {}),
          ...patch.columnLayoutsByListId,
        }
      : current.columnLayoutsByListId,
    sortByListId: patch.sortByListId
      ? { ...(current.sortByListId ?? {}), ...patch.sortByListId }
      : current.sortByListId,
  };
}

function buildBackupWorkspaceDoc(
  backup: ChartPersistBackup,
): WorkspaceDocument {
  return normalizeWorkspace({
    charts: backup.charts,
    activeChartId: backup.activeChartId,
    chartStateByListInstrument: backup.chartStateByListInstrument,
    chartListContext: backup.chartListContext,
    chartToolbarGlobal: backup.chartToolbarGlobal,
    indicatorTemplates: backup.indicatorTemplates,
    indicatorPresets: backup.indicatorPresets,
    indicatorFavoritesByListId: backup.indicatorFavoritesByListId,
    defaultIndicatorTemplateId: backup.defaultIndicatorTemplateId,
    preferences: {
      ...DEFAULT_WORKSPACE.preferences,
      ...backup.preferences,
    },
    list: backup.list,
    layout: {
      ...DEFAULT_WORKSPACE.layout,
      chartInspectorOpen: backup.chartInspectorOpen ?? false,
    },
    updatedAt: backup.updatedAt,
  });
}

function prepareWorkspaceForSave(
  workspace: WorkspaceDocument,
): WorkspaceDocument {
  const session = drawToolSessionFromUi();
  const prepared = syncSnapshotsFromCharts(
    attachActiveTabListSnapshot(
      {
        ...workspace,
        updatedAt: new Date().toISOString(),
        chartToolbarGlobal: normalizeChartToolbarGlobalConfig({
          ...workspace.chartToolbarGlobal,
          activeDrawTool: session.chartDrawTool,
          lastDrawToolByGroup: session.lastDrawToolByGroup,
        }),
      },
      openDrawingEditorId(),
    ),
  );
  return prepared;
}

function chartPersistBackupFrom(
  workspace: WorkspaceDocument,
): ChartPersistBackup {
  return {
    charts: workspace.charts,
    activeChartId: workspace.activeChartId,
    chartStateByListInstrument: workspace.chartStateByListInstrument,
    chartListContext: workspace.chartListContext,
    chartToolbarGlobal: workspace.chartToolbarGlobal,
    indicatorTemplates: workspace.indicatorTemplates,
    indicatorPresets: workspace.indicatorPresets,
    indicatorFavoritesByListId: workspace.indicatorFavoritesByListId,
    defaultIndicatorTemplateId: workspace.defaultIndicatorTemplateId,
    preferences: {
      newChartTemplateChartId:
        workspace.preferences.newChartTemplateChartId ?? null,
    },
    chartInspectorOpen: workspace.layout.chartInspectorOpen,
    list: workspace.list,
    updatedAt: workspace.updatedAt,
  };
}

const WORKSPACE_META_KEY = "bolsa-workspace-meta";

function writeChartPersistBackupSync(
  activeWorkspaceId: string | null,
  recents: string[],
  backup: ChartPersistBackup,
): void {
  try {
    const raw = localStorage.getItem(WORKSPACE_META_KEY);
    const parsed = raw
      ? (JSON.parse(raw) as {
          state?: Record<string, unknown>;
          version?: number;
        })
      : {};
    localStorage.setItem(
      WORKSPACE_META_KEY,
      JSON.stringify({
        state: {
          ...(parsed.state ?? {}),
          activeWorkspaceId,
          recents,
          chartPersistBackup: backup,
        },
        version: parsed.version ?? 0,
      }),
    );
  } catch {
    // ignore quota / private mode
  }
}

function appendPresetToPersonalTemplate(
  templates: IndicatorTemplate[],
  presetId: string,
): IndicatorTemplate[] {
  return templates.map((template) =>
    template.id === BUILTIN_PERSONAL_TEMPLATE_ID
      ? ensurePresetInTemplate(template, presetId)
      : template,
  );
}

function cloneChartConfig(
  config: ChartInstanceConfig = DEFAULT_CHART_CONFIG,
): ChartInstanceConfig {
  return {
    ...config,
    id: config.id === DEFAULT_CHART_CONFIG.id ? newChartTabId() : config.id,
    grid: { ...config.grid },
    cursor: { ...config.cursor },
    colors: { ...config.colors },
    display: { ...config.display },
  };
}

function openDrawingEditorId(): string | null {
  return getWorkspaceUiBridge().getOpenDrawingEditorId();
}

function finalizeChartWorkspace(
  workspace: WorkspaceDocument,
): WorkspaceDocument {
  const deduped = dedupeChartTabsByInstrument(
    workspace.charts,
    workspace.activeChartId,
  );
  return syncSnapshotsFromCharts(
    attachActiveTabListSnapshot(
      {
        ...workspace,
        charts: deduped.charts,
        activeChartId: deduped.activeChartId,
      },
      openDrawingEditorId(),
    ),
  );
}

function mapTabIndicators(
  tab: ChartTabState,
  indicatorInstances: ChartIndicatorInstance[],
  activeIndicatorTemplateId?: string | null,
): ChartTabState {
  return {
    ...tab,
    indicatorInstances,
    activeIndicatorTemplateId:
      activeIndicatorTemplateId !== undefined
        ? activeIndicatorTemplateId
        : (tab.activeIndicatorTemplateId ?? null),
    chart: {
      ...tab.chart,
      display: mergeDisplayFromInstances(tab.chart.display, indicatorInstances),
    },
  };
}

function getListIndicatorFavorites(
  workspace: WorkspaceDocument,
  listId: string,
): IndicatorFavoriteRef[] {
  const stored = workspace.indicatorFavoritesByListId?.[listId];
  if (stored?.length) {
    return stored.map((ref) => ({
      definitionId: ref.definitionId,
      parameters: { ...ref.parameters },
      ...(ref.shortLabel ? { shortLabel: ref.shortLabel } : {}),
    }));
  }
  return DEFAULT_INDICATOR_FAVORITES.map((ref) => ({
    definitionId: ref.definitionId,
    parameters: { ...ref.parameters },
    ...(ref.shortLabel ? { shortLabel: ref.shortLabel } : {}),
  }));
}

function newDefaultChartTab(
  instrumentId: string,
  label: string,
  timeframe: ChartTimeframe = DEFAULT_CHART_TIMEFRAME,
  seriesType: ChartSeriesType = DEFAULT_CHART_SERIES_TYPE,
): ChartTabState {
  const chart = cloneChartConfig();
  return {
    id: newChartTabId(),
    instrumentId,
    label,
    timeframe,
    seriesType,
    chart,
    indicatorInstances: seedIndicatorInstancesFromDisplay(chart.display),
    drawings: [],
  };
}

function createChartTabForInstrument(
  workspace: WorkspaceDocument,
  instrumentId: string,
  label: string,
  options?: { sourceListId?: string },
): ChartTabState {
  const global = normalizeChartToolbarGlobalConfig(
    workspace.chartToolbarGlobal,
  );
  let tab = newDefaultChartTab(
    instrumentId,
    label,
    global.defaultTimeframe,
    global.defaultSeriesType,
  );
  if (options?.sourceListId) {
    tab = { ...tab, sourceListId: options.sourceListId };
  }

  const templateTab = resolveNewChartTemplateTab(workspace);
  if (templateTab) {
    tab = applyChartNewTabSeed(
      tab,
      extractChartNewTabSeed(templateTab),
      cloneChartConfig,
    );
    if (workspace.preferences.finalistTop1DefaultOn) {
      tab = {
        ...tab,
        showFinalistTop1Indicators: true,
        indicatorInstances: tab.indicatorInstances.filter(
          (instance) => instance.origin !== "finalist-top1",
        ),
      };
    }
    return tab;
  }

  const defaultTemplateId = workspace.defaultIndicatorTemplateId;
  if (defaultTemplateId) {
    const template = workspace.indicatorTemplates?.find(
      (item) => item.id === defaultTemplateId,
    );
    if (template) {
      const instances = instancesFromTemplate(
        template,
        workspace.indicatorPresets ?? DEFAULT_SYSTEM_PRESETS,
      );
      tab = mapTabIndicators(tab, instances, template.id);
    }
  }
  if (workspace.preferences.finalistTop1DefaultOn) {
    tab = {
      ...tab,
      showFinalistTop1Indicators: true,
      indicatorInstances: tab.indicatorInstances.filter(
        (instance) => instance.origin !== "finalist-top1",
      ),
    };
  }
  return tab;
}

function normalizeChartTab(
  raw: Partial<ChartTabState>,
  fallback?: ChartInstanceConfig,
): ChartTabState {
  const chartBase = {
    ...DEFAULT_CHART_CONFIG,
    ...fallback,
    ...raw.chart,
    grid: {
      ...DEFAULT_CHART_CONFIG.grid,
      ...fallback?.grid,
      ...raw.chart?.grid,
    },
    cursor: {
      ...DEFAULT_CHART_CONFIG.cursor,
      ...fallback?.cursor,
      ...raw.chart?.cursor,
    },
    colors: {
      ...DEFAULT_CHART_CONFIG.colors,
      ...fallback?.colors,
      ...raw.chart?.colors,
    },
    display: {
      ...DEFAULT_CHART_CONFIG.display,
      ...fallback?.display,
      ...raw.chart?.display,
    },
  };
  const indicatorInstances =
    Array.isArray(raw.indicatorInstances) && raw.indicatorInstances.length > 0
      ? raw.indicatorInstances
      : seedIndicatorInstancesFromDisplay(chartBase.display);
  const chart = {
    ...chartBase,
    display: mergeDisplayFromInstances(chartBase.display, indicatorInstances),
  };
  const timeframe =
    raw.timeframe && isChartTimeframe(raw.timeframe)
      ? raw.timeframe
      : DEFAULT_CHART_TIMEFRAME;
  return {
    id: raw.id ?? chart.id ?? newChartTabId(),
    instrumentId: raw.instrumentId ?? "",
    label: raw.label ?? "Gráfico",
    timeframe,
    seriesType: normalizeChartSeriesType(raw.seriesType),
    seriesTypeParams: normalizeChartSeriesTypeParams(raw.seriesTypeParams),
    chart,
    indicatorInstances,
    drawings: sanitizeChartDrawings(raw.drawings),
    sourceListId: raw.sourceListId,
    activeIndicatorTemplateId: raw.activeIndicatorTemplateId ?? null,
    showFinalistTop1Indicators: Boolean(raw.showFinalistTop1Indicators),
    toolbar: normalizeChartToolbarChartOverrides(raw.toolbar),
    pricePanelHeightPct: resolvePricePanelHeightPct(raw.pricePanelHeightPct),
  };
}

const DEFAULT_WORKSPACE: WorkspaceDocument = {
  version: 1,
  id: "default",
  name: "Espacio de trabajo",
  updatedAt: new Date().toISOString(),
  layout: {
    listPanelOpen: true,
    listPanelSizePct: DEFAULT_LIST_PANEL_SIZE_PCT,
    rightPanelOpen: true,
    rightPanelSizePct: DEFAULT_RIGHT_PANEL_SIZE_PCT,
    chartInspectorOpen: false,
    activeRoute: "/trading",
  },
  preferences: {
    autoSave: true,
    openOnStartup: true,
    newChartTemplateChartId: null,
  },
  charts: [],
  activeChartId: null,
  drawingTemplates: [...DEFAULT_DRAWING_TEMPLATES],
  activeDrawingTemplateByTool: {},
  indicatorTemplates: [...DEFAULT_INDICATOR_TEMPLATES],
  indicatorPresets: normalizeIndicatorPresets(undefined),
  defaultIndicatorTemplateId: null,
  indicatorFavoritesByListId: {},
  list: DEFAULT_LIST_CONFIG,
  chartToolbarGlobal: normalizeChartToolbarGlobalConfig(),
};

const LEGACY_TIMEFRAME_FAVORITES_KEY = "bolsa-chart-timeframe-favorites";

function readLegacyTimeframeFavorites(): ChartTimeframe[] | undefined {
  try {
    const raw = localStorage.getItem(LEGACY_TIMEFRAME_FAVORITES_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return undefined;
    const valid = parsed.filter((item): item is ChartTimeframe =>
      isChartTimeframe(String(item)),
    );
    return valid.length > 0 ? valid : undefined;
  } catch {
    return undefined;
  }
}

function normalizeWorkspace(
  raw:
    | (Partial<WorkspaceDocument> & { chart?: ChartInstanceConfig })
    | undefined,
): WorkspaceDocument {
  if (!raw) return DEFAULT_WORKSPACE;

  let charts: ChartTabState[] = [];
  if (raw.charts?.length) {
    charts = raw.charts.map((tab) => normalizeChartTab(tab));
  } else if (raw.chart) {
    charts = [
      normalizeChartTab({
        id: "main",
        instrumentId: "",
        label: "Gráfico",
        chart: raw.chart,
      }),
    ];
  }

  const dedupedCharts = dedupeChartTabsByInstrument(
    charts,
    raw.activeChartId ?? null,
  );
  charts = dedupedCharts.charts;

  const activeChartId =
    dedupedCharts.activeChartId &&
    charts.some((tab) => tab.id === dedupedCharts.activeChartId)
      ? dedupedCharts.activeChartId
      : (charts[0]?.id ?? null);

  const workspace: WorkspaceDocument = {
    ...DEFAULT_WORKSPACE,
    ...raw,
    version: 1,
    layout: {
      ...DEFAULT_WORKSPACE.layout,
      ...raw.layout,
      listPanelSizePct: Math.max(
        MIN_LIST_PANEL_SIZE_PCT,
        raw.layout?.listPanelSizePct ??
          DEFAULT_WORKSPACE.layout.listPanelSizePct,
      ),
      rightPanelSizePct: Math.max(
        MIN_RIGHT_PANEL_SIZE_PCT,
        raw.layout?.rightPanelSizePct ??
          DEFAULT_WORKSPACE.layout.rightPanelSizePct,
      ),
      rightPanelOpen:
        raw.layout?.rightPanelOpen ?? DEFAULT_WORKSPACE.layout.rightPanelOpen,
      chartInspectorOpen:
        raw.layout?.chartInspectorOpen ??
        DEFAULT_WORKSPACE.layout.chartInspectorOpen,
    },
    preferences: {
      ...DEFAULT_WORKSPACE.preferences,
      ...raw.preferences,
      newChartTemplateChartId: normalizeNewChartTemplateChartId(
        raw.preferences?.newChartTemplateChartId,
        charts,
      ),
    },
    charts,
    activeChartId,
    chartStateByListInstrument: raw.chartStateByListInstrument ?? {},
    chartListContext: raw.chartListContext ?? null,
    drawingTemplates: normalizeDrawingTemplates(raw.drawingTemplates),
    activeDrawingTemplateByTool: raw.activeDrawingTemplateByTool ?? {},
    indicatorTemplates: normalizeIndicatorTemplates(raw.indicatorTemplates),
    indicatorPresets: normalizeIndicatorPresets(raw.indicatorPresets),
    defaultIndicatorTemplateId: raw.defaultIndicatorTemplateId ?? null,
    indicatorFavoritesByListId: normalizeIndicatorFavoritesByListId(
      raw.indicatorFavoritesByListId,
    ),
    chartToolbarGlobal: normalizeChartToolbarGlobalConfig(
      {
        ...raw.chartToolbarGlobal,
        timeframeFavorites:
          raw.chartToolbarGlobal?.timeframeFavorites ??
          readLegacyTimeframeFavorites(),
      },
      raw.chartDataStrip ?? raw.chartToolbarGlobal?.chartDefaults,
    ),
    list: {
      ...DEFAULT_LIST_CONFIG,
      ...raw.list,
      columnLayoutsByListId: (() => {
        const byList = { ...(raw.list?.columnLayoutsByListId ?? {}) };
        const activeId = raw.list?.apiListId;
        if (activeId && raw.list?.columnLayout?.length && !byList[activeId]) {
          byList[activeId] = raw.list.columnLayout;
        }
        return byList;
      })(),
      columnLayout: normalizeColumnLayout(
        raw.list?.columnLayout,
        raw.list?.columns,
      ),
      columns: visibleListColumns(
        normalizeColumnLayout(raw.list?.columnLayout, raw.list?.columns),
      ),
      carouselListIds: raw.list?.carouselListIds ?? [],
      carouselPinnedListNames: raw.list?.carouselPinnedListNames ?? [],
      carouselHiddenListIds: raw.list?.carouselHiddenListIds ?? [],
      carouselInitialized:
        raw.list?.carouselInitialized === true ||
        Boolean(raw.list?.carouselListIds?.length) ||
        Boolean(raw.list?.carouselPinnedListNames?.length) ||
        Boolean(raw.list?.carouselHiddenListIds?.length),
      sortByListId: raw.list?.sortByListId ?? {},
      rowActionsWidth: raw.list?.rowActionsWidth,
      visualizationEntries: raw.list?.visualizationEntries ?? [],
    },
  };
  return pruneOrphanChartSnapshots(syncSnapshotsFromCharts(workspace));
}

interface ChartPersistBackup {
  charts: ChartTabState[];
  activeChartId: string | null;
  chartStateByListInstrument?: WorkspaceDocument["chartStateByListInstrument"];
  chartListContext?: WorkspaceDocument["chartListContext"];
  chartToolbarGlobal?: WorkspaceDocument["chartToolbarGlobal"];
  indicatorTemplates?: WorkspaceDocument["indicatorTemplates"];
  indicatorPresets?: WorkspaceDocument["indicatorPresets"];
  indicatorFavoritesByListId?: WorkspaceDocument["indicatorFavoritesByListId"];
  defaultIndicatorTemplateId?: WorkspaceDocument["defaultIndicatorTemplateId"];
  preferences?: Pick<
    WorkspaceDocument["preferences"],
    "newChartTemplateChartId"
  >;
  chartInspectorOpen?: boolean;
  list?: WorkspaceDocument["list"];
  updatedAt: string;
}

interface WorkspaceState {
  /** Documento del espacio activo (gráficos, listas, preferencias…). */
  workspace: WorkspaceDocument;
  /** Id servidor del espacio activo; también en `bolsa-workspace-meta`. */
  activeWorkspaceId: string | null;
  chartPersistBackup: ChartPersistBackup | null;
  /** Membresía de listas en memoria (no se persiste). */
  chartListMembership: ChartListMembershipSnapshot | null;
  /** Catálogo ligero para el gestor (chip / picker). */
  workspaceSummaries: WorkspaceSummaryDto[];
  hydrated: boolean;
  isDirty: boolean;
  isSaving: boolean;
  recents: string[];
  getActiveChartTab: () => ChartTabState | null;
  /**
   * Carga inicial: lista API → elige activo local / preferido / primero;
   * fusiona backup local de gráficos si es más reciente.
   */
  bootstrapWorkspaces: () => Promise<void>;
  refreshSummaries: () => Promise<void>;
  /** PUT del documento activo (nombre, document, dockLayout, isDefault). */
  saveToServer: () => Promise<void>;
  requestAutoSave: (immediate?: boolean) => void;
  syncWorkspaceFromServer: () => Promise<void>;
  flushWorkspaceOnUnload: () => void;
  /** Cambia de espacio; confirma si hay cambios sin guardar. */
  switchWorkspace: (workspaceId: string) => Promise<void>;
  /** Crea espacio en blanco (`DEFAULT_WORKSPACE`) y lo activa. */
  createWorkspace: (name: string) => Promise<void>;
  /** Clona el documento activo (gráficos/listas/dibujos + dock) en un espacio nuevo. */
  duplicateWorkspace: (name?: string) => Promise<void>;
  /** Renombra en servidor (activo o cualquier id del catálogo). */
  renameWorkspaceById: (workspaceId: string, name: string) => Promise<void>;
  /** Recarga el espacio activo desde el servidor (descarta cambios locales si confirmas). */
  reloadActiveFromServer: () => Promise<void>;
  deleteWorkspaceById: (workspaceId: string) => Promise<void>;
  setListPanelOpen: (open: boolean) => void;
  setListPanelSizePct: (pct: number) => void;
  setRightPanelOpen: (open: boolean) => void;
  setRightPanelSizePct: (pct: number) => void;
  setChartInspectorOpen: (open: boolean) => void;
  toggleChartInspector: () => void;
  openChartInspector: (target: ChartInspectorNavigateInput) => void;
  toggleChartInspectorShortcut: (target: ChartInspectorNavigateInput) => void;
  resetPanelLayout: () => void;
  /** Renombre local del activo (marca dirty); preferir `renameWorkspaceById` desde el gestor. */
  rename: (name: string) => void;
  markDirty: () => void;
  touchWorkspace: () => void;
  /** Dispara guardado (respeta cola / autoguardado). */
  save: () => void;
  exportJson: () => void;
  /** Alias de `reloadActiveFromServer`. */
  reload: () => void;
  setAutoSave: (enabled: boolean) => void;
  /**
   * Marca el espacio como preferido al arrancar (`isDefault` en el próximo save).
   * Solo actúa si este dispositivo no tiene `activeWorkspaceId` válido.
   */
  setOpenOnStartup: (enabled: boolean) => void;
  toggleNewChartTemplatePin: () => void;
  openChartTab: (instrumentId: string, label: string) => string;
  focusInstrumentFromList: (
    listId: string,
    instrumentId: string,
    label: string,
  ) => string;
  /** Abre/enfoca varios gráficos en un solo update (evita races de autoguardado). */
  focusInstrumentsFromList: (
    listId: string,
    items: ReadonlyArray<{ instrumentId: string; label: string }>,
  ) => void;
  setDrawingEditorOpen: (drawingId: string | null) => void;
  closeChartTab: (chartId: string) => void;
  /** Cierra en un solo update todas las pestañas de los instrumentos dados (evita races de autosave). */
  closeChartTabsForInstruments: (instrumentIds: ReadonlyArray<string>) => void;
  /** Reordena pestañas: primero `orderedInstrumentIds` (izq→der), luego el resto en orden previo. */
  reorderChartTabsByInstrumentIds: (
    orderedInstrumentIds: ReadonlyArray<string>,
  ) => void;
  selectChartTab: (chartId: string) => void;
  duplicateActiveChart: () => void;
  updateChartConfig: (patch: {
    chartId?: string;
    grid?: Partial<ChartInstanceConfig["grid"]>;
    cursor?: Partial<ChartInstanceConfig["cursor"]>;
    colors?: Partial<ChartInstanceConfig["colors"]>;
    display?: Partial<ChartInstanceConfig["display"]>;
  }) => void;
  updateChartTimeframe: (timeframe: ChartTimeframe, chartId?: string) => void;
  setChartDisplayFlags: (
    patch: Partial<ChartInstanceConfig["display"]>,
    chartId?: string,
  ) => void;
  addIndicatorInstance: (
    definitionId: string,
    parameters?: ChartIndicatorInstance["parameters"],
    chartId?: string,
  ) => boolean;
  /**
   * Activa/desactiva el overlay Finalista TOP #1 en el gráfico.
   * Si `enabled` y se pasan `specs`, sincroniza instancias `origin: 'finalist-top1'`.
   * Si `enabled===false`, limpia solo esas instancias (no toca manuales).
   * No cambia `preferences.finalistTop1DefaultOn` (opt-in/out por gráfico).
   */
  setShowFinalistTop1Indicators: (
    enabled: boolean,
    specs?: Array<{
      definitionId: string;
      parameters: Record<string, number | boolean | string>;
    }>,
    chartId?: string,
  ) => void;
  /**
   * Política workspace: ON → default para gráficos nuevos + activa en todas las pestañas abiertas.
   * OFF → quita el default y limpia el overlay en todos los gráficos.
   * Cada gráfico puede desactivarse después con `setShowFinalistTop1Indicators(false, …)`.
   */
  setFinalistTop1DefaultForAll: (enabled: boolean) => void;
  /** Re-aplica specs TOP #1 sin cambiar el flag (p. ej. al cambiar instrumento/TF con switch ON). */
  syncFinalistTop1Indicators: (
    specs: Array<{
      definitionId: string;
      parameters: Record<string, number | boolean | string>;
    }>,
    chartId?: string,
  ) => void;
  updateIndicatorInstance: (
    instanceId: string,
    patch: Partial<
      Pick<
        ChartIndicatorInstance,
        "parameters" | "visible" | "scaleZoom" | "showLastValue" | "lineWidth"
      >
    >,
    chartId?: string,
  ) => string | null;
  duplicateIndicatorInstance: (
    instanceId: string,
    chartId?: string,
  ) => string | null;
  togglePresetOnChart: (
    presetId: string,
    chartId?: string,
  ) => "added" | "removed" | "failed";
  togglePresetVisibilityOnChart: (
    presetId: string,
    chartId?: string,
  ) => boolean;
  togglePresetInTemplate: (templateId: string, presetId: string) => void;
  swapChartInstanceToPreset: (
    instanceId: string,
    presetId: string,
    chartId?: string,
  ) => string | null;
  forkPresetToPersonal: (
    sourcePresetId: string,
    name: string,
    patch?: Partial<
      Pick<IndicatorPreset, "parameters" | "lineWidth" | "showLastValue">
    >,
  ) => string | null;
  forkInstanceToPersonalPreset: (
    instanceId: string,
    name: string,
    chartId?: string,
  ) => string | null;
  removeIndicatorPreset: (presetId: string) => void;
  updateIndicatorPreset: (
    presetId: string,
    patch: Partial<IndicatorPreset>,
  ) => void;
  duplicateUserIndicatorPreset: (
    presetId: string,
    name?: string,
  ) => string | null;
  createAiIndicatorVariant: (options: {
    definitionId: string;
    name: string;
    parameters?: ChartIndicatorInstance["parameters"];
    lineWidth?: number;
  }) => string | null;
  addIndicatorPresetFromDraft: (
    preset: IndicatorPreset,
    name?: string,
  ) => string | null;
  setDefaultIndicatorTemplate: (templateId: string | null) => void;
  removeIndicatorInstance: (instanceId: string, chartId?: string) => void;
  reorderIndicatorInstances: (
    fromInstanceId: string,
    toInstanceId: string,
    chartId?: string,
  ) => void;
  toggleIndicatorOnChart: (
    definitionId: string,
    parameters?: ChartIndicatorInstance["parameters"],
    chartId?: string,
  ) => "added" | "removed" | "failed";
  setIndicatorInstanceParameters: (
    instanceId: string,
    parameters: ChartIndicatorInstance["parameters"],
    chartId?: string,
  ) => boolean;
  resetChartConfig: (chartId?: string) => void;
  addChartDrawing: (drawing: ChartDrawing, chartId?: string) => void;
  updateChartDrawing: (
    drawingId: string,
    patch: ChartDrawingVertexPatch,
    chartId?: string,
  ) => void;
  removeChartDrawing: (drawingId: string, chartId?: string) => void;
  clearChartDrawings: (chartId?: string) => void;
  flushDrawingSave: () => void;
  addDrawingTemplate: () => ChartDrawingTemplate;
  updateDrawingTemplate: (
    templateId: string,
    patch: Partial<ChartDrawingTemplate>,
  ) => void;
  removeDrawingTemplate: (templateId: string) => void;
  duplicateDrawingTemplate: (templateId: string) => ChartDrawingTemplate | null;
  setActiveDrawingTemplateForTool: (
    tool: ChartDrawTool,
    templateId: string | null,
  ) => void;
  applyDrawingTemplate: (
    drawingId: string,
    templateId: string,
    chartId?: string,
  ) => void;
  getIndicatorFavoritesForList: (listId: string) => IndicatorFavoriteRef[];
  toggleIndicatorFavorite: (listId: string, ref: IndicatorFavoriteRef) => void;
  toggleIndicatorByFavorite: (
    listId: string,
    ref: IndicatorFavoriteRef,
    chartId?: string,
  ) => void;
  addIndicatorTemplate: () => IndicatorTemplate;
  updateIndicatorTemplate: (
    templateId: string,
    patch: Partial<IndicatorTemplate>,
  ) => void;
  removeIndicatorTemplate: (templateId: string) => void;
  duplicateIndicatorTemplate: (templateId: string) => IndicatorTemplate | null;
  applyIndicatorTemplate: (templateId: string, chartId?: string) => void;
  createIndicatorTemplateFromChart: (
    chartId: string,
    name?: string,
  ) => IndicatorTemplate;
  updateListConfig: (patch: Partial<ListPanelConfig>) => void;
  resetListConfig: () => void;
  updateChartToolbarGlobal: (patch: Partial<ChartToolbarGlobalConfig>) => void;
  toggleChartTimeframeFavorite: (timeframe: ChartTimeframe) => void;
  toggleChartSeriesTypeFavorite: (seriesType: ChartSeriesType) => void;
  toggleIndicatorTemplateFavorite: (templateId: string) => void;
  toggleInspectorBarShortcutFavorite: (
    shortcutId: ChartInspectorBarShortcutId,
  ) => void;
  toggleDrawToolFavorite: (tool: ChartDrawTool) => void;
  rememberDrawStyleForTool: (
    tool: ChartDrawTool,
    patch: DrawToolStyleMemory,
  ) => void;
  rememberDrawStyleFromDrawing: (
    drawing: ChartDrawing,
    sourceTool?: ChartDrawTool,
  ) => void;
  toggleChartDrawingsLayerHidden: (chartId?: string) => void;
  toggleChartDrawingsLayerLocked: (chartId?: string) => void;
  updateChartSeriesType: (
    seriesType: ChartSeriesType,
    chartId?: string,
  ) => void;
  updateChartSeriesTypeParams: (
    patch: Partial<ChartSeriesTypeParams>,
    chartId?: string,
  ) => void;
  toggleInstrumentFieldFavorite: (field: ChartInstrumentBarField) => void;
  toggleCursorFieldFavorite: (field: ChartCursorBarField) => void;
  updateChartToolbarForChart: (
    chartId: string,
    patch: ChartToolbarChartOverrides | null,
  ) => void;
  updateChartPricePanelHeight: (pct: number, chartId?: string) => void;
  setSubPanelWeights: (
    weights: Record<string, number>,
    chartId?: string,
  ) => void;
  resetChartToolbarForChart: (chartId: string) => void;
  setChartListMembership: (membership: ChartListMembershipSnapshot) => void;
  syncChartListMembership: (membership: ChartListMembershipSnapshot) => void;
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function applyServerWorkspace(record: {
  id: string;
  name: string;
  document: WorkspaceDocument;
  dockLayout: TradingDockLayoutPrefs | null;
}): Pick<WorkspaceState, "workspace" | "activeWorkspaceId" | "isDirty"> {
  const workspace = normalizeWorkspace(record.document);
  workspace.id = record.id;
  workspace.name = record.name;
  // dockLayout del servidor se ignora: paneles = localStorage por dispositivo.
  void record.dockLayout;
  return { workspace, activeWorkspaceId: record.id, isDirty: false };
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      workspace: DEFAULT_WORKSPACE,
      activeWorkspaceId: null,
      chartPersistBackup: null,
      chartListMembership: null,
      workspaceSummaries: [],
      hydrated: false,
      isDirty: false,
      isSaving: false,
      recents: [],
      getActiveChartTab: () => {
        const { charts, activeChartId } = get().workspace;
        return (
          charts.find((tab) => tab.id === activeChartId) ?? charts[0] ?? null
        );
      },
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
        if (get().workspace.preferences.autoSave)
          scheduleWorkspaceServerSave(get);
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
        if (get().workspace.preferences.autoSave)
          scheduleWorkspaceServerSave(get);
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
      rename: (name) =>
        set((state) => ({
          workspace: {
            ...state.workspace,
            name,
            updatedAt: new Date().toISOString(),
          },
          isDirty: true,
        })),
      markDirty: () => set({ isDirty: true }),
      touchWorkspace: () =>
        set((state) => ({
          isDirty: true,
          workspace: {
            ...state.workspace,
            updatedAt: new Date().toISOString(),
          },
        })),
      bootstrapWorkspaces: async () => {
        try {
          const list = await api.getWorkspaces();
          let summaries = list.data;
          if (summaries.length === 0) {
            const legacyDoc = readLegacyWorkspaceFromStorage();
            const legacyDock = readLegacyDockFromStorage();
            const created = await api.createWorkspace({
              name: legacyDoc?.name ?? "Espacio de trabajo",
              document: legacyDoc ?? DEFAULT_WORKSPACE,
              dockLayout: legacyDock ?? DEFAULT_DOCK_LAYOUT,
              isDefault: true,
            });
            summaries = [
              {
                id: created.data.id,
                name: created.data.name,
                isDefault: created.data.isDefault,
                updatedAt: created.data.updatedAt,
              },
            ];
            set({
              ...applyServerWorkspace(created.data),
              workspaceSummaries: summaries,
              hydrated: true,
            });
            return;
          }

          const { activeWorkspaceId } = get();
          const target =
            summaries.find((s) => s.id === activeWorkspaceId) ??
            summaries.find((s) => s.isDefault) ??
            summaries[0];
          if (!target) {
            set({ hydrated: true });
            return;
          }
          const detail = await api.getWorkspace(target.id);
          const applied = applyServerWorkspace(detail.data);
          let workspace = applied.workspace;
          const backup = get().chartPersistBackup;
          let backupWasNewer = false;
          if (backup) {
            const backupDoc = buildBackupWorkspaceDoc(backup);
            backupWasNewer =
              workspaceTimestamp(backupDoc) > workspaceTimestamp(workspace);
            workspace = mergeWorkspaceChartState(
              backupWasNewer ? backupDoc : workspace,
              backupWasNewer ? workspace : backupDoc,
            );
          }
          workspace = applyLocalDrawToolFavorites(workspace);
          workspace = applyLocalDrawToolSession(workspace);
          workspace.id = applied.workspace.id;
          workspace.name = applied.workspace.name;
          set({
            workspace,
            activeWorkspaceId: applied.activeWorkspaceId,
            chartPersistBackup: chartPersistBackupFrom(workspace),
            workspaceSummaries: summaries,
            hydrated: true,
            isDirty: backupWasNewer,
          });
        } catch (err) {
          const legacyDoc = readLegacyWorkspaceFromStorage();
          const backup = get().chartPersistBackup;
          if (legacyDoc) {
            let workspace = normalizeWorkspace(legacyDoc);
            if (backup) {
              const backupDoc = buildBackupWorkspaceDoc(backup);
              workspace = mergeWorkspaceChartState(backupDoc, workspace);
            }
            workspace = applyLocalDrawToolFavorites(workspace);
            workspace = applyLocalDrawToolSession(workspace);
            set({
              workspace,
              chartPersistBackup: chartPersistBackupFrom(workspace),
              hydrated: true,
              isDirty: true,
            });
          } else if (backup) {
            const backupDoc = buildBackupWorkspaceDoc(backup);
            set({
              workspace: backupDoc,
              chartPersistBackup: chartPersistBackupFrom(backupDoc),
              hydrated: true,
              isDirty: true,
            });
          } else {
            set({ hydrated: true });
          }
          if (err instanceof ApiError) {
            console.warn("Workspace bootstrap:", err.message);
          }
        }
      },
      refreshSummaries: async () => {
        const list = await api.getWorkspaces();
        set({ workspaceSummaries: list.data });
      },
      saveToServer: async () => {
        if (!get().hydrated) return;
        const id = get().activeWorkspaceId;
        if (!id) return;
        if (get().isSaving) {
          saveQueued = true;
          return;
        }

        set({ isSaving: true });
        try {
          const prepared = prepareWorkspaceForSave(get().workspace);
          const backup = chartPersistBackupFrom(prepared);
          writeChartPersistBackupSync(
            get().activeWorkspaceId,
            get().recents,
            backup,
          );
          // No sustituir `workspace` aquí: un set intermedio + await permite que un
          // sync/merge deje menos pestañas al volver. Solo enviamos `prepared`.
          const payload = buildWorkspacePayload(prepared);
          const response = await api.updateWorkspace(id, {
            name: prepared.name,
            document: payload.document,
            dockLayout: payload.dockLayout,
            isDefault: prepared.preferences.openOnStartup,
          });
          const live = get().workspace;
          // Autoridad post-PUT = pestañas vivas ahora. No reinyectar `prepared`
          // (si el usuario cerró tabs durante el await, la unión antigua las resucitaba).
          const preparedInstr = new Set(
            prepared.charts.map((c) => c.instrumentId).filter(Boolean),
          );
          const openedDuringSave = live.charts.some(
            (tab) => tab.instrumentId && !preparedInstr.has(tab.instrumentId),
          );
          const nextWorkspace = {
            ...live,
            name: response.data.name,
            updatedAt: response.data.updatedAt ?? live.updatedAt,
          };
          set({
            workspace: nextWorkspace,
            chartPersistBackup: chartPersistBackupFrom(nextWorkspace),
            activeWorkspaceId: response.data.id,
            isDirty: openedDuringSave,
            isSaving: false,
          });
          if (openedDuringSave) saveQueued = true;
          await get().refreshSummaries();
        } catch (err) {
          set({ isSaving: false });
          if (err instanceof ApiError) {
            window.alert(`No se pudo guardar: ${err.message}`);
          }
          throw err;
        } finally {
          if (saveQueued) {
            saveQueued = false;
            void get().saveToServer();
          }
        }
      },
      requestAutoSave: (immediate = false) => {
        requestWorkspaceAutoSave(get, immediate);
      },
      flushWorkspaceOnUnload: () => {
        const state = get();
        if (!state.hydrated || !state.activeWorkspaceId) return;
        const prepared = prepareWorkspaceForSave(state.workspace);
        const backup = chartPersistBackupFrom(prepared);
        writeChartPersistBackupSync(
          state.activeWorkspaceId,
          state.recents,
          backup,
        );
        const payload = buildWorkspacePayload(prepared);
        api.updateWorkspaceKeepalive(state.activeWorkspaceId, {
          name: prepared.name,
          document: payload.document,
          dockLayout: payload.dockLayout,
          isDefault: prepared.preferences.openOnStartup,
        });
      },
      syncWorkspaceFromServer: async () => {
        const id = get().activeWorkspaceId;
        if (!id || !get().hydrated || get().isDirty || get().isSaving) return;
        try {
          const detail = await api.getWorkspace(id);
          const serverBase = normalizeWorkspace(detail.data.document);
          serverBase.id = detail.data.id;
          serverBase.name = detail.data.name;
          const local = get().workspace;
          const serverDrawings =
            totalChartDrawings(serverBase.charts) +
            totalSnapshotDrawings(serverBase.chartStateByListInstrument);
          const localDrawings =
            totalChartDrawings(local.charts) +
            totalSnapshotDrawings(local.chartStateByListInstrument);
          const serverTs = detail.data.updatedAt ?? serverBase.updatedAt;
          if (serverDrawings <= localDrawings && serverTs <= local.updatedAt)
            return;

          // Preferir el set de pestañas local en pulls en background (este dispositivo).
          const merged = mergeWorkspaceChartState(local, serverBase);
          merged.id = local.id;
          merged.name = local.name;
          if (
            local.activeChartId &&
            merged.charts.some((t) => t.id === local.activeChartId)
          ) {
            merged.activeChartId = local.activeChartId;
          }
          set({
            workspace: merged,
            chartPersistBackup: chartPersistBackupFrom(merged),
          });
        } catch {
          // Sin conexión o sesión — ignorar
        }
      },
      switchWorkspace: async (workspaceId) => {
        const { isDirty, activeWorkspaceId } = get();
        if (workspaceId === activeWorkspaceId) return;
        if (
          isDirty &&
          !window.confirm(
            "Hay cambios sin guardar. ¿Cambiar de espacio de trabajo?",
          )
        ) {
          return;
        }
        const detail = await api.getWorkspace(workspaceId);
        set({
          ...applyServerWorkspace(detail.data),
          recents: [
            workspaceId,
            ...get().recents.filter((id) => id !== workspaceId),
          ].slice(0, 8),
        });
      },
      createWorkspace: async (name) => {
        const fresh = normalizeWorkspace({ ...DEFAULT_WORKSPACE, name });
        const payload = buildWorkspacePayload(fresh);
        const created = await api.createWorkspace({
          name,
          document: payload.document,
          dockLayout: payload.dockLayout,
        });
        set({
          ...applyServerWorkspace(created.data),
          isDirty: false,
        });
        await get().refreshSummaries();
      },
      duplicateWorkspace: async (name) => {
        const prepared = prepareWorkspaceForSave(get().workspace);
        const newName =
          name?.trim() ||
          `${prepared.name.replace(/\s*\(copia(?:\s+\d+)?\)\s*$/i, "").trim()} (copia)`;
        const cloneDoc = normalizeWorkspace({
          ...prepared,
          name: newName,
          updatedAt: new Date().toISOString(),
        });
        const payload = buildWorkspacePayload(cloneDoc);
        const created = await api.createWorkspace({
          name: newName,
          document: { ...payload.document, name: newName },
          dockLayout: payload.dockLayout,
          isDefault: false,
        });
        set({
          ...applyServerWorkspace(created.data),
          isDirty: false,
          recents: [
            created.data.id,
            ...get().recents.filter((id) => id !== created.data.id),
          ].slice(0, 8),
        });
        await get().refreshSummaries();
      },
      renameWorkspaceById: async (workspaceId, name) => {
        const trimmed = name.trim();
        if (!trimmed) return;
        const response = await api.updateWorkspace(workspaceId, {
          name: trimmed,
        });
        if (workspaceId === get().activeWorkspaceId) {
          set((state) => ({
            workspace: {
              ...state.workspace,
              name: response.data.name,
              updatedAt: response.data.updatedAt ?? state.workspace.updatedAt,
            },
          }));
        }
        await get().refreshSummaries();
      },
      reloadActiveFromServer: async () => {
        const id = get().activeWorkspaceId;
        if (!id) return;
        if (
          get().isDirty &&
          !window.confirm(
            "Hay cambios sin guardar. ¿Recargar el espacio desde el servidor?",
          )
        ) {
          return;
        }
        const detail = await api.getWorkspace(id);
        set({
          ...applyServerWorkspace(detail.data),
          isDirty: false,
        });
      },
      deleteWorkspaceById: async (workspaceId) => {
        await api.deleteWorkspace(workspaceId);
        await get().refreshSummaries();
        const { activeWorkspaceId } = get();
        if (workspaceId === activeWorkspaceId) {
          const defaultWs = await api.getDefaultWorkspace();
          set(applyServerWorkspace(defaultWs.data));
        }
      },
      save: () => {
        scheduleWorkspaceServerSave(get);
      },
      exportJson: () => {
        const { workspace } = get();
        downloadJson(
          `${workspace.name.replace(/\s+/g, "-").toLowerCase()}.bolsa-workspace.json`,
          workspace,
        );
        set({ isDirty: false });
      },
      reload: () => {
        void get().reloadActiveFromServer();
      },
      setAutoSave: (enabled) =>
        set((state) => ({
          workspace: {
            ...state.workspace,
            preferences: { ...state.workspace.preferences, autoSave: enabled },
          },
          isDirty: true,
        })),
      setOpenOnStartup: (enabled) =>
        set((state) => ({
          workspace: {
            ...state.workspace,
            preferences: {
              ...state.workspace.preferences,
              openOnStartup: enabled,
            },
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
        const closing = get().workspace.charts.find(
          (tab) => tab.id === chartId,
        );
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
            Boolean(templateId) &&
            closingTabs.some((tab) => tab.id === templateId);
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
            if (tab.instrumentId && rank.has(tab.instrumentId))
              selected.push(tab);
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
          const tab = state.workspace.charts.find(
            (item) => item.id === chartId,
          );
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
      addIndicatorInstance: (definitionId, parameters, chartId) => {
        const definition = findIndicatorDefinition(definitionId);
        if (!definition) return false;
        const params = normalizeParameters(definition, parameters ?? {});
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return false;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (
          !tab ||
          hasDuplicateInstance(tab.indicatorInstances, definitionId, params)
        ) {
          return false;
        }
        set((state) => ({
          workspace: finalizeChartWorkspace({
            ...state.workspace,
            charts: state.workspace.charts.map((item) => {
              if (item.id !== targetId) return item;
              const instance: ChartIndicatorInstance = {
                instanceId: newIndicatorInstanceId(definitionId, params),
                definitionId,
                parameters: params,
                visible: true,
              };
              const indicatorInstances = assignSubPanelWeightOnAdd(
                [...item.indicatorInstances, instance],
                instance.instanceId,
              );
              return {
                ...item,
                activeIndicatorTemplateId: null,
                indicatorInstances,
                chart: {
                  ...item.chart,
                  display: mergeDisplayFromInstances(
                    item.chart.display,
                    indicatorInstances,
                  ),
                },
              };
            }),
          }),
          isDirty: true,
        }));
        return true;
      },
      setShowFinalistTop1Indicators: (enabled, specs, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return;
        set((state) => {
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
          if (!tab) return state;

          const desired = specs ?? [];
          const desiredKeys = new Set<string>();
          const toAdd: ChartIndicatorInstance[] = [];
          for (const spec of desired) {
            const definition = findIndicatorDefinition(spec.definitionId);
            if (!definition) continue;
            const params = normalizeParameters(
              definition,
              spec.parameters ?? {},
            );
            const key = instanceSpecKey(definition.id, params);
            desiredKeys.add(key);
            toAdd.push({
              instanceId: newIndicatorInstanceId(spec.definitionId, params),
              definitionId: spec.definitionId,
              parameters: params,
              visible: true,
              origin: "finalist-top1",
            });
          }

          const existingTop = tab.indicatorInstances.filter(
            (inst) => inst.origin === "finalist-top1",
          );
          const existingKeys = new Set(
            existingTop.map((inst) =>
              instanceSpecKey(inst.definitionId, inst.parameters),
            ),
          );
          const sameSpecs =
            desiredKeys.size === existingKeys.size &&
            [...desiredKeys].every((k) => existingKeys.has(k));
          if (
            tab.showFinalistTop1Indicators === enabled &&
            (!enabled || sameSpecs)
          ) {
            return state;
          }

          let indicatorInstances = tab.indicatorInstances.filter(
            (inst) => inst.origin !== "finalist-top1",
          );
          if (enabled) {
            for (const instance of toAdd) {
              if (
                hasDuplicateInstance(
                  indicatorInstances,
                  instance.definitionId,
                  instance.parameters,
                )
              ) {
                continue;
              }
              indicatorInstances = assignSubPanelWeightOnAdd(
                [...indicatorInstances, instance],
                instance.instanceId,
              );
            }
          }
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((item) =>
                item.id !== targetId
                  ? item
                  : {
                      ...mapTabIndicators(
                        item,
                        indicatorInstances,
                        item.activeIndicatorTemplateId,
                      ),
                      showFinalistTop1Indicators: enabled,
                    },
              ),
            }),
            isDirty: true,
          };
        });
      },
      syncFinalistTop1Indicators: (specs, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (!tab?.showFinalistTop1Indicators) return;
        get().setShowFinalistTop1Indicators(true, specs, targetId);
      },
      setFinalistTop1DefaultForAll: (enabled) => {
        set((state) => {
          const prevDefault = Boolean(
            state.workspace.preferences.finalistTop1DefaultOn,
          );
          const chartsUnchanged =
            prevDefault === enabled &&
            state.workspace.charts.every(
              (tab) => Boolean(tab.showFinalistTop1Indicators) === enabled,
            );
          if (chartsUnchanged) return state;

          const charts = state.workspace.charts.map((tab) => {
            if (enabled) {
              if (tab.showFinalistTop1Indicators) return tab;
              return { ...tab, showFinalistTop1Indicators: true };
            }
            if (!tab.showFinalistTop1Indicators) {
              const hasTop = tab.indicatorInstances.some(
                (inst) => inst.origin === "finalist-top1",
              );
              if (!hasTop) return tab;
            }
            const indicatorInstances = tab.indicatorInstances.filter(
              (inst) => inst.origin !== "finalist-top1",
            );
            return {
              ...mapTabIndicators(
                tab,
                indicatorInstances,
                tab.activeIndicatorTemplateId,
              ),
              showFinalistTop1Indicators: false,
            };
          });

          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              preferences: {
                ...state.workspace.preferences,
                finalistTop1DefaultOn: enabled,
              },
              charts,
            }),
            isDirty: true,
          };
        });
      },
      toggleIndicatorOnChart: (definitionId, parameters, chartId) => {
        const definition = findIndicatorDefinition(definitionId);
        if (!definition) return "failed";
        const params = normalizeParameters(definition, parameters ?? {});
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return "failed";
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (!tab) return "failed";
        const existing = findInstanceBySpec(
          tab.indicatorInstances,
          definitionId,
          params,
        );
        if (existing) {
          get().removeIndicatorInstance(existing.instanceId, targetId);
          return "removed";
        }
        return get().addIndicatorInstance(definitionId, params, targetId)
          ? "added"
          : "failed";
      },
      setIndicatorInstanceParameters: (instanceId, parameters, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return false;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (!tab) return false;
        const current = tab.indicatorInstances.find(
          (item) => item.instanceId === instanceId,
        );
        if (!current) return false;
        const definition = findIndicatorDefinition(current.definitionId);
        if (!definition) return false;
        const params = normalizeParameters(definition, parameters);
        const others = tab.indicatorInstances.filter(
          (item) => item.instanceId !== instanceId,
        );
        if (hasDuplicateInstance(others, current.definitionId, params))
          return false;
        set((state) => ({
          workspace: finalizeChartWorkspace({
            ...state.workspace,
            charts: state.workspace.charts.map((chartTab) => {
              if (chartTab.id !== targetId) return chartTab;
              const indicatorInstances = chartTab.indicatorInstances.map(
                (instance) => {
                  if (instance.instanceId !== instanceId) return instance;
                  return {
                    ...instance,
                    instanceId: newIndicatorInstanceId(
                      instance.definitionId,
                      params,
                    ),
                    parameters: params,
                  };
                },
              );
              return {
                ...chartTab,
                activeIndicatorTemplateId: null,
                indicatorInstances,
                chart: {
                  ...chartTab.chart,
                  display: mergeDisplayFromInstances(
                    chartTab.chart.display,
                    indicatorInstances,
                  ),
                },
              };
            }),
          }),
          isDirty: true,
        }));
        return true;
      },
      updateIndicatorInstance: (instanceId, patch, chartId) => {
        let resultId: string | null = null;
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
          if (!tab) return state;
          const current = tab.indicatorInstances.find(
            (item) => item.instanceId === instanceId,
          );
          if (!current) return state;
          if (patch.parameters) {
            const definition = findIndicatorDefinition(current.definitionId);
            if (!definition) return state;
            const params = normalizeParameters(definition, patch.parameters);
            const others = tab.indicatorInstances.filter(
              (item) => item.instanceId !== instanceId,
            );
            if (hasDuplicateInstance(others, current.definitionId, params))
              return state;
          }
          const nextScaleZoom =
            patch.scaleZoom != null
              ? Math.min(3, Math.max(0.5, patch.scaleZoom))
              : undefined;
          const definition = findIndicatorDefinition(current.definitionId);
          if (!definition) return state;

          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((chartTab) => {
                if (chartTab.id !== targetId) return chartTab;
                const indicatorInstances = chartTab.indicatorInstances.map(
                  (instance) => {
                    if (instance.instanceId !== instanceId) return instance;
                    const nextParams = patch.parameters
                      ? normalizeParameters(definition, patch.parameters)
                      : instance.parameters;
                    const dataChanged =
                      patch.parameters != null &&
                      dataParametersKey(instance.parameters) !==
                        dataParametersKey(nextParams);
                    const nextInstanceId = dataChanged
                      ? newIndicatorInstanceId(
                          instance.definitionId,
                          nextParams,
                        )
                      : instance.instanceId;
                    const next = {
                      ...instance,
                      ...patch,
                      ...(nextScaleZoom != null
                        ? { scaleZoom: nextScaleZoom }
                        : {}),
                      parameters: nextParams,
                      instanceId: nextInstanceId,
                    };
                    resultId = next.instanceId;
                    return next;
                  },
                );
                const rebalanced =
                  patch.visible !== undefined && isSubPanelInstance(current)
                    ? adjustSubPanelWeightsAfterVisibilityChange(
                        indicatorInstances,
                        instanceId,
                        patch.visible,
                      )
                    : indicatorInstances;
                return {
                  ...chartTab,
                  activeIndicatorTemplateId: null,
                  indicatorInstances: rebalanced,
                  chart: {
                    ...chartTab.chart,
                    display: mergeDisplayFromInstances(
                      chartTab.chart.display,
                      rebalanced,
                    ),
                  },
                };
              }),
            }),
            isDirty: true,
          };
        });
        return resultId;
      },
      duplicateIndicatorInstance: (instanceId, chartId) => {
        let newId: string | null = null;
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
          if (!tab) return state;
          const index = tab.indicatorInstances.findIndex(
            (item) => item.instanceId === instanceId,
          );
          if (index < 0) return state;
          const source = tab.indicatorInstances[index]!;
          const clone: ChartIndicatorInstance = {
            ...source,
            instanceId: newIndicatorInstanceId(
              source.definitionId,
              source.parameters,
            ),
            visible: source.visible,
          };
          newId = clone.instanceId;
          let indicatorInstances = [...tab.indicatorInstances];
          indicatorInstances.splice(index + 1, 0, clone);
          if (isSubPanelInstance(clone)) {
            indicatorInstances = assignSubPanelWeightOnAdd(
              indicatorInstances,
              clone.instanceId,
            );
          }
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((chartTab) => {
                if (chartTab.id !== targetId) return chartTab;
                return {
                  ...chartTab,
                  activeIndicatorTemplateId: null,
                  indicatorInstances,
                  chart: {
                    ...chartTab.chart,
                    display: mergeDisplayFromInstances(
                      chartTab.chart.display,
                      indicatorInstances,
                    ),
                  },
                };
              }),
            }),
            isDirty: true,
          };
        });
        return newId;
      },
      togglePresetOnChart: (presetId, chartId) => {
        const presets = get().workspace.indicatorPresets ?? [];
        const preset = findIndicatorPreset(presets, presetId);
        if (!preset) return "failed";
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return "failed";
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (!tab) return "failed";
        const existing = findInstanceByPreset(tab.indicatorInstances, presetId);
        if (existing) {
          get().removeIndicatorInstance(existing.instanceId, targetId);
          return "removed";
        }
        const instance = instanceFromPreset(preset);
        set((state) => ({
          workspace: finalizeChartWorkspace({
            ...state.workspace,
            charts: state.workspace.charts.map((chartTab) => {
              if (chartTab.id !== targetId) return chartTab;
              const indicatorInstances = [
                ...chartTab.indicatorInstances,
                instance,
              ];
              return {
                ...chartTab,
                activeIndicatorTemplateId: null,
                indicatorInstances,
                chart: {
                  ...chartTab.chart,
                  display: mergeDisplayFromInstances(
                    chartTab.chart.display,
                    indicatorInstances,
                  ),
                },
              };
            }),
          }),
          isDirty: true,
        }));
        return "added";
      },
      togglePresetVisibilityOnChart: (presetId, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return false;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        const existing = tab
          ? findInstanceByPreset(tab.indicatorInstances, presetId)
          : undefined;
        if (!existing) return false;
        const nextId = get().updateIndicatorInstance(
          existing.instanceId,
          { visible: !existing.visible },
          targetId,
        );
        return Boolean(nextId);
      },
      togglePresetInTemplate: (templateId, presetId) =>
        set((state) => {
          const templates = state.workspace.indicatorTemplates ?? [];
          const template = templates.find((item) => item.id === templateId);
          if (!template) return state;
          const next = togglePresetInTemplate(template, presetId);
          return {
            workspace: {
              ...state.workspace,
              indicatorTemplates: templates.map((item) =>
                item.id === templateId ? next : item,
              ),
            },
            isDirty: true,
          };
        }),
      forkPresetToPersonal: (sourcePresetId, name, patch) => {
        const presets = get().workspace.indicatorPresets ?? [];
        const source = findIndicatorPreset(presets, sourcePresetId);
        if (!source) return null;
        const forked = forkIndicatorPreset(source, {
          name,
          parameters: patch?.parameters,
          lineWidth: patch?.lineWidth,
          showLastValue: patch?.showLastValue,
        });
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorPresets: [
              ...(state.workspace.indicatorPresets ?? []),
              forked,
            ],
            indicatorTemplates: appendPresetToPersonalTemplate(
              state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
              forked.id,
            ),
          },
          isDirty: true,
        }));
        return forked.id;
      },
      createAiIndicatorVariant: (options) => {
        const preset = createAiIndicatorVariantPreset(options);
        if (!preset) return null;
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorPresets: [
              ...(state.workspace.indicatorPresets ?? []),
              preset,
            ],
            indicatorTemplates: appendPresetToPersonalTemplate(
              state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
              preset.id,
            ),
          },
          isDirty: true,
        }));
        return preset.id;
      },
      addIndicatorPresetFromDraft: (preset, name) => {
        const nextPreset: IndicatorPreset = {
          ...preset,
          id: preset.id.startsWith("draft-")
            ? newIndicatorPresetId()
            : preset.id,
          name: name?.trim() || preset.name,
          locked: false,
        };
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorPresets: [
              ...(state.workspace.indicatorPresets ?? []),
              nextPreset,
            ],
            indicatorTemplates: appendPresetToPersonalTemplate(
              state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
              nextPreset.id,
            ),
          },
          isDirty: true,
        }));
        return nextPreset.id;
      },
      forkInstanceToPersonalPreset: (instanceId, name, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return null;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        const instance = tab?.indicatorInstances.find(
          (item) => item.instanceId === instanceId,
        );
        if (!instance) return null;
        const preset = presetFromInstance(instance, name, {
          derivedFromPresetId: instance.presetId,
        });
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorPresets: [
              ...(state.workspace.indicatorPresets ?? []),
              preset,
            ],
            indicatorTemplates: appendPresetToPersonalTemplate(
              state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
              preset.id,
            ),
          },
          isDirty: true,
        }));
        return preset.id;
      },
      removeIndicatorPreset: (presetId) =>
        set((state) => {
          const preset = findIndicatorPreset(
            state.workspace.indicatorPresets ?? [],
            presetId,
          );
          if (!preset || preset.locked) return state;
          return {
            workspace: {
              ...state.workspace,
              indicatorPresets: (state.workspace.indicatorPresets ?? []).filter(
                (item) => item.id !== presetId,
              ),
              indicatorTemplates: (
                state.workspace.indicatorTemplates ?? []
              ).map((template) => ({
                ...template,
                presetIds: (template.presetIds ?? []).filter(
                  (id) => id !== presetId,
                ),
              })),
            },
            isDirty: true,
          };
        }),
      updateIndicatorPreset: (presetId, patch) =>
        set((state) => {
          const current = findIndicatorPreset(
            state.workspace.indicatorPresets ?? [],
            presetId,
          );
          if (!current || current.locked) return state;
          const definition = findIndicatorDefinition(current.definitionId);
          const parameters =
            patch.parameters && definition
              ? normalizeParameters(definition, {
                  ...current.parameters,
                  ...patch.parameters,
                })
              : patch.parameters
                ? { ...current.parameters, ...patch.parameters }
                : current.parameters;
          const nextPreset = {
            ...current,
            ...patch,
            parameters,
          };
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              indicatorPresets: (state.workspace.indicatorPresets ?? []).map(
                (preset) => (preset.id === presetId ? nextPreset : preset),
              ),
              charts: state.workspace.charts.map((tab) => ({
                ...tab,
                indicatorInstances: tab.indicatorInstances.map((instance) => {
                  if (instance.presetId !== presetId) return instance;
                  return {
                    ...instance,
                    parameters: { ...nextPreset.parameters },
                    lineWidth: nextPreset.lineWidth ?? instance.lineWidth,
                    showLastValue:
                      nextPreset.showLastValue ?? instance.showLastValue,
                  };
                }),
              })),
            }),
            isDirty: true,
          };
        }),
      duplicateUserIndicatorPreset: (presetId, name) => {
        const presets = get().workspace.indicatorPresets ?? [];
        const source = findIndicatorPreset(presets, presetId);
        if (!source) return null;
        const copy = duplicateIndicatorPreset(source, name);
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorPresets: [
              ...(state.workspace.indicatorPresets ?? []),
              copy,
            ],
            indicatorTemplates: appendPresetToPersonalTemplate(
              state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
              copy.id,
            ),
          },
          isDirty: true,
        }));
        return copy.id;
      },
      swapChartInstanceToPreset: (instanceId, presetId, chartId) => {
        const presets = get().workspace.indicatorPresets ?? [];
        const preset = findIndicatorPreset(presets, presetId);
        if (!preset) return null;
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return null;
        let resultId: string | null = null;
        set((state) => {
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
          if (!tab) return state;
          const nextInstance = instanceFromPreset(preset);
          resultId = nextInstance.instanceId;
          const indicatorInstances = [
            ...tab.indicatorInstances.filter(
              (item) => item.instanceId !== instanceId,
            ),
            nextInstance,
          ];
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((chartTab) => {
                if (chartTab.id !== targetId) return chartTab;
                return {
                  ...chartTab,
                  activeIndicatorTemplateId: null,
                  indicatorInstances,
                  chart: {
                    ...chartTab.chart,
                    display: mergeDisplayFromInstances(
                      chartTab.chart.display,
                      indicatorInstances,
                    ),
                  },
                };
              }),
            }),
            isDirty: true,
          };
        });
        return resultId;
      },
      setDefaultIndicatorTemplate: (templateId) =>
        set((state) => ({
          workspace: {
            ...state.workspace,
            defaultIndicatorTemplateId: templateId,
          },
          isDirty: true,
        })),
      removeIndicatorInstance: (instanceId, chartId) =>
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((tab) => {
                if (tab.id !== targetId) return tab;
                const removed = tab.indicatorInstances.find(
                  (item) => item.instanceId === instanceId,
                );
                let indicatorInstances = tab.indicatorInstances.filter(
                  (item) => item.instanceId !== instanceId,
                );
                if (removed && isSubPanelInstance(removed) && removed.visible) {
                  const remainingCount =
                    visibleSubPanelInstances(indicatorInstances).length;
                  const removedWeight =
                    removed.subPanelWeight ??
                    (remainingCount > 0 ? 100 / (remainingCount + 1) : 100);
                  indicatorInstances = redistributeSubPanelWeightAfterRemove(
                    indicatorInstances,
                    removedWeight,
                  );
                }
                let nextDisplay = tab.chart.display;
                if (removed) {
                  const offPatch = displayPatchForInstance(
                    removed.definitionId,
                    removed.parameters,
                    false,
                  );
                  nextDisplay = { ...nextDisplay, ...offPatch };
                }
                return {
                  ...tab,
                  activeIndicatorTemplateId: null,
                  indicatorInstances,
                  chart: {
                    ...tab.chart,
                    display: mergeDisplayFromInstances(
                      nextDisplay,
                      indicatorInstances,
                    ),
                  },
                };
              }),
            }),
            isDirty: true,
          };
        }),
      reorderIndicatorInstances: (fromInstanceId, toInstanceId, chartId) =>
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((tab) => {
                if (tab.id !== targetId) return tab;
                const instances = [...tab.indicatorInstances];
                const from = instances.findIndex(
                  (item) => item.instanceId === fromInstanceId,
                );
                const to = instances.findIndex(
                  (item) => item.instanceId === toInstanceId,
                );
                if (from < 0 || to < 0 || from === to) return tab;
                const [moved] = instances.splice(from, 1);
                instances.splice(to, 0, moved!);
                return {
                  ...tab,
                  activeIndicatorTemplateId: null,
                  indicatorInstances: instances,
                  chart: {
                    ...tab.chart,
                    display: mergeDisplayFromInstances(
                      tab.chart.display,
                      instances,
                    ),
                  },
                };
              }),
            }),
            isDirty: true,
          };
        }),
      resetChartConfig: (chartId) =>
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((tab) => {
                if (tab.id !== targetId) return tab;
                const chart = cloneChartConfig(DEFAULT_CHART_CONFIG);
                return {
                  ...tab,
                  chart,
                  indicatorInstances: seedIndicatorInstancesFromDisplay(
                    chart.display,
                  ),
                };
              }),
            }),
            isDirty: true,
          };
        }),
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
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
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
          for (const [tool, id] of Object.entries(
            activeDrawingTemplateByTool,
          )) {
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
            drawingTemplates: [
              ...(state.workspace.drawingTemplates ?? []),
              copy,
            ],
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
          const tab = state.workspace.charts.find(
            (item) => item.id === targetId,
          );
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
      getIndicatorFavoritesForList: (listId) =>
        getListIndicatorFavorites(get().workspace, listId),
      toggleIndicatorFavorite: (listId, ref) =>
        set((state) => {
          const current = getListIndicatorFavorites(state.workspace, listId);
          const key = favoriteRefKey(ref);
          const exists = current.some((item) => favoriteRefKey(item) === key);
          const next = exists
            ? current.filter((item) => favoriteRefKey(item) !== key)
            : [
                ...current,
                {
                  definitionId: ref.definitionId,
                  parameters: { ...ref.parameters },
                  ...(ref.shortLabel ? { shortLabel: ref.shortLabel } : {}),
                },
              ];
          const favorites =
            next.length > 0
              ? next
              : DEFAULT_INDICATOR_FAVORITES.map((item) => ({
                  definitionId: item.definitionId,
                  parameters: { ...item.parameters },
                }));
          return {
            workspace: {
              ...state.workspace,
              indicatorFavoritesByListId: {
                ...(state.workspace.indicatorFavoritesByListId ?? {}),
                [listId]: favorites,
              },
              updatedAt: new Date().toISOString(),
            },
            isDirty: !state.workspace.preferences.autoSave,
          };
        }),
      toggleIndicatorByFavorite: (_listId, ref, chartId) => {
        const targetId = chartId ?? get().workspace.activeChartId;
        if (!targetId) return;
        const tab = get().workspace.charts.find((item) => item.id === targetId);
        if (!tab) return;
        const existing = findInstanceByRef(tab.indicatorInstances, ref);
        if (existing) {
          get().updateIndicatorInstance(
            existing.instanceId,
            { visible: !existing.visible },
            targetId,
          );
          return;
        }
        get().addIndicatorInstance(ref.definitionId, ref.parameters, targetId);
      },
      addIndicatorTemplate: () => {
        const template = createBlankIndicatorTemplate();
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorTemplates: [
              ...(state.workspace.indicatorTemplates ?? []),
              template,
            ],
          },
          isDirty: true,
        }));
        return template;
      },
      updateIndicatorTemplate: (templateId, patch) =>
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorTemplates: (state.workspace.indicatorTemplates ?? []).map(
              (template) => {
                if (template.id !== templateId) return template;
                return {
                  ...template,
                  ...patch,
                  items: patch.items
                    ? patch.items.map((item) => ({
                        ...item,
                        parameters: { ...item.parameters },
                      }))
                    : template.items,
                };
              },
            ),
          },
          isDirty: true,
        })),
      removeIndicatorTemplate: (templateId) =>
        set((state) => {
          const target = state.workspace.indicatorTemplates?.find(
            (t) => t.id === templateId,
          );
          if (!target || target.locked || target.builtin) return state;
          return {
            workspace: {
              ...state.workspace,
              indicatorTemplates: (
                state.workspace.indicatorTemplates ?? []
              ).filter((t) => t.id !== templateId),
              charts: state.workspace.charts.map((tab) =>
                tab.activeIndicatorTemplateId === templateId
                  ? { ...tab, activeIndicatorTemplateId: null }
                  : tab,
              ),
            },
            isDirty: true,
          };
        }),
      duplicateIndicatorTemplate: (templateId) => {
        const source = get().workspace.indicatorTemplates?.find(
          (t) => t.id === templateId,
        );
        if (!source) return null;
        const copy: IndicatorTemplate = {
          ...source,
          id: newIndicatorTemplateId(),
          name: `${source.name} (copia)`,
          locked: false,
          builtin: false,
          source: "custom",
          presetIds: [...(source.presetIds ?? [])],
          items: source.items?.map((item) => ({
            ...item,
            parameters: { ...item.parameters },
          })),
        };
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorTemplates: [
              ...(state.workspace.indicatorTemplates ?? []),
              copy,
            ],
          },
          isDirty: true,
        }));
        return copy;
      },
      applyIndicatorTemplate: (templateId, chartId) => {
        set((state) => {
          const targetId = chartId ?? state.workspace.activeChartId;
          if (!targetId) return state;
          const template = (state.workspace.indicatorTemplates ?? []).find(
            (item) => item.id === templateId,
          );
          if (!template) return state;
          if (!templateHasIndicators(template)) return state;
          const instances = rebalanceSubPanelWeights(
            instancesFromTemplate(
              template,
              state.workspace.indicatorPresets ?? DEFAULT_SYSTEM_PRESETS,
            ),
          );
          return {
            workspace: finalizeChartWorkspace({
              ...state.workspace,
              charts: state.workspace.charts.map((tab) =>
                tab.id !== targetId
                  ? tab
                  : {
                      ...mapTabIndicators(tab, instances, template.id),
                      showFinalistTop1Indicators: false,
                    },
              ),
            }),
            isDirty: !state.workspace.preferences.autoSave,
          };
        });
        flushDrawingAutoSave(get, true);
      },
      createIndicatorTemplateFromChart: (chartId, name) => {
        const tab = get().workspace.charts.find((item) => item.id === chartId);
        const instances = tab?.indicatorInstances ?? [];
        const presets =
          get().workspace.indicatorPresets ?? DEFAULT_SYSTEM_PRESETS;
        const template = indicatorTemplateFromInstances(
          instances,
          name?.trim() || "Plantilla del gráfico",
          presets,
        );
        set((state) => ({
          workspace: {
            ...state.workspace,
            indicatorTemplates: [
              ...(state.workspace.indicatorTemplates ?? []),
              template,
            ],
          },
          isDirty: true,
        }));
        return template;
      },
      updateListConfig: (patch) => {
        set((state) => ({
          workspace: {
            ...state.workspace,
            updatedAt: new Date().toISOString(),
            list: mergeListConfigPatch(state.workspace.list, patch),
          },
          isDirty: true,
        }));
        scheduleWorkspaceSettingsPersist(get, set);
      },
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
                    ...state.workspace.chartToolbarGlobal
                      ?.chartVisibilityDefaults,
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
                : state.workspace.chartToolbarGlobal
                    ?.indicatorTemplateFavorites,
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
          const next = toggleInspectorBarShortcutFavoriteList(
            current,
            shortcutId,
          );
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
          nextFavorites = normalizeDrawToolFavorites(
            next,
            IMPLEMENTED_DRAW_TOOLS,
          );
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
      rememberDrawStyleForTool: (tool, patch) => {
        if (!patch || Object.keys(patch).length === 0) return;
        const state = get();
        const prev =
          state.workspace.chartToolbarGlobal?.lastDrawStyleByTool ?? {};
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
      resetListConfig: () => {
        set((state) => ({
          workspace: {
            ...state.workspace,
            list: { ...DEFAULT_LIST_CONFIG },
            updatedAt: new Date().toISOString(),
          },
          isDirty: true,
        }));
        scheduleWorkspaceSettingsPersist(get, set);
      },
      setChartListMembership: (membership) =>
        set((state) => {
          if (
            state.chartListMembership &&
            membershipFingerprint(state.chartListMembership) ===
              membershipFingerprint(membership)
          ) {
            return state;
          }
          return { chartListMembership: membership };
        }),
      syncChartListMembership: (membership) =>
        set((state) => {
          const sameMembership =
            state.chartListMembership &&
            membershipFingerprint(state.chartListMembership) ===
              membershipFingerprint(membership);
          const workspace = reconcileWorkspaceChartMembership(
            state.workspace,
            membership,
          );
          const workspaceChanged = workspace !== state.workspace;
          if (sameMembership && !workspaceChanged) return state;
          return {
            chartListMembership: membership,
            workspace: workspaceChanged
              ? { ...workspace, updatedAt: new Date().toISOString() }
              : state.workspace,
            isDirty: workspaceChanged ? true : state.isDirty,
          };
        }),
    }),
    {
      name: "bolsa-workspace-meta",
      partialize: (state) => ({
        activeWorkspaceId: state.activeWorkspaceId,
        recents: state.recents,
        chartPersistBackup: chartPersistBackupFrom(state.workspace),
      }),
      merge: (persisted, current) => {
        const p = persisted as Partial<WorkspaceState> | undefined;
        return {
          ...current,
          activeWorkspaceId: p?.activeWorkspaceId ?? null,
          recents: p?.recents ?? [],
          chartPersistBackup: p?.chartPersistBackup ?? null,
        };
      },
    },
  ),
);

export function useActiveChartTab(): ChartTabState | null {
  return useWorkspaceStore((state) => {
    const { charts, activeChartId } = state.workspace;
    return charts.find((tab) => tab.id === activeChartId) ?? charts[0] ?? null;
  });
}
