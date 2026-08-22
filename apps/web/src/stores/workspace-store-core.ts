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
import {
  DEFAULT_CHART_CONFIG,
  DEFAULT_LIST_CONFIG,
  DEFAULT_LIST_PANEL_SIZE_PCT,
  DEFAULT_RIGHT_PANEL_SIZE_PCT,
  MIN_LIST_PANEL_SIZE_PCT,
  MIN_RIGHT_PANEL_SIZE_PCT,
  normalizeColumnLayout,
  normalizeChartToolbarGlobalConfig,
  normalizeChartToolbarChartOverrides,
  type ChartInstrumentBarField,
  type ChartCursorBarField,
  visibleListColumns,
  normalizeDrawingTemplates,
  DEFAULT_DRAWING_TEMPLATES,
  DEFAULT_INDICATOR_TEMPLATES,
  BUILTIN_PERSONAL_TEMPLATE_ID,
  ensurePresetInTemplate,
  instancesFromTemplate,
  normalizeIndicatorFavoritesByListId,
  normalizeIndicatorTemplates,
  normalizeIndicatorPresets,
  DEFAULT_SYSTEM_PRESETS,
  type ChartInspectorBarShortcutId,
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
  normalizeChartSeriesTypeParams,
  type DrawToolStyleMemory,
  type ChartSeriesType,
  type ChartSeriesTypeParams,
  resolvePricePanelHeightPct,
  isChartTimeframe,
  mergeDisplayFromInstances,
  seedIndicatorInstancesFromDisplay,
} from "@bolsa/shared";
import {
  attachActiveTabListSnapshot,
  syncSnapshotsFromCharts,
  pruneOrphanChartSnapshots,
} from "@/lib/chart-list-snapshot";
import { dedupeChartTabsByInstrument } from "@/lib/chart-tab-uniqueness";
import { readDrawToolFavoritesLocal } from "@/lib/draw-tool-favorites-storage";
import {
  reportLegacyStorageMetric,
  reportWorkspaceDeprecatedFields,
} from "@/lib/legacy-storage-metrics";
import {
  applyDrawToolSessionToUi,
  drawToolSessionFromUi,
  readDrawToolSessionLocal,
} from "@/lib/draw-tool-session-storage";
import type { ChartListMembershipSnapshot } from "@/lib/chart-list-membership";
import { getWorkspaceUiBridge } from "@/stores/workspace-ui-bridge";
import type { ChartInspectorNavigateInput } from "@/features/charts/chart-inspector-nav";

let chartTabIdSeq = 0;

export function newChartTabId(): string {
  // Date.now() solo no basta: Abrir gráficos abre N tabs en el mismo ms y
  // ids duplicados colapsan keys de React + el Map del saveToServer.
  chartTabIdSeq += 1;
  return `chart-${Date.now().toString(36)}-${chartTabIdSeq.toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

let drawingAutoSaveTimer: number | null = null;
let settingsPersistTimer: number | null = null;
let workspaceServerSaveTimer: number | null = null;

/** Debounce único para autosave al servidor (M7). */
export const WORKSPACE_AUTOSAVE_DEBOUNCE_MS = 1000;

export function findDrawingTemplate(
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

export function patchHasStyleMemory(patch: ChartDrawingVertexPatch): boolean {
  return STYLE_MEMORY_KEYS.some((key) => key in patch);
}

export function styleMemoryFromPatch(
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

export function applyLocalDrawToolFavorites(
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

export function applyLocalDrawToolSession(
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

export function flushDrawingAutoSave(
  get: () => WorkspaceState,
  immediate = false,
) {
  if (drawingAutoSaveTimer) {
    clearTimeout(drawingAutoSaveTimer);
    drawingAutoSaveTimer = null;
  }
  if (immediate) {
    requestWorkspaceAutoSave(get, true);
    return;
  }
  drawingAutoSaveTimer = window.setTimeout(() => {
    drawingAutoSaveTimer = null;
    requestWorkspaceAutoSave(get);
  }, 450);
}

/** Un solo timer de guardado en servidor — evita duplicar con WorkspaceAutoSave. */
export function requestWorkspaceAutoSave(
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

  workspaceServerSaveTimer = window.setTimeout(() => {
    workspaceServerSaveTimer = null;
    const current = get();
    if (!current.hydrated || !current.workspace.preferences.autoSave) return;
    void current.saveToServer();
  }, WORKSPACE_AUTOSAVE_DEBOUNCE_MS);
}

/** @deprecated Usa requestWorkspaceAutoSave */
export function scheduleWorkspaceServerSave(
  get: () => WorkspaceState,
  immediate = false,
) {
  requestWorkspaceAutoSave(get, immediate);
}

/** Backup local inmediato + guardado en servidor para listas y barras. */
export function scheduleWorkspaceSettingsPersist(
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
  settingsPersistTimer = window.setTimeout(() => {
    settingsPersistTimer = null;
    run();
  }, 500);
}

export function mergeListConfigPatch(
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

export function buildBackupWorkspaceDoc(
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

export function prepareWorkspaceForSave(
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

export function chartPersistBackupFrom(
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

export const WORKSPACE_META_KEY = "bolsa-workspace-meta";

export function writeChartPersistBackupSync(
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

export function appendPresetToPersonalTemplate(
  templates: IndicatorTemplate[],
  presetId: string,
): IndicatorTemplate[] {
  return templates.map((template) =>
    template.id === BUILTIN_PERSONAL_TEMPLATE_ID
      ? ensurePresetInTemplate(template, presetId)
      : template,
  );
}

export function cloneChartConfig(
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

export function openDrawingEditorId(): string | null {
  return getWorkspaceUiBridge().getOpenDrawingEditorId();
}

export function finalizeChartWorkspace(
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

export function mapTabIndicators(
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

export function getListIndicatorFavorites(
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

export function newDefaultChartTab(
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

export function createChartTabForInstrument(
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

export function normalizeChartTab(
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

export const DEFAULT_WORKSPACE: WorkspaceDocument = {
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

export const LEGACY_TIMEFRAME_FAVORITES_KEY = "bolsa-chart-timeframe-favorites";

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

export function normalizeWorkspace(
  raw:
    | (Partial<WorkspaceDocument> & { chart?: ChartInstanceConfig })
    | undefined,
): WorkspaceDocument {
  if (!raw) return DEFAULT_WORKSPACE;

  reportWorkspaceDeprecatedFields(raw);

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
    chartToolbarGlobal: (() => {
      const legacyTimeframeFavorites =
        raw.chartToolbarGlobal?.timeframeFavorites == null
          ? readLegacyTimeframeFavorites()
          : undefined;
      if (legacyTimeframeFavorites) {
        reportLegacyStorageMetric("timeframe_favorites_legacy_blob", {
          count: legacyTimeframeFavorites.length,
        });
      }
      return normalizeChartToolbarGlobalConfig(
        {
          ...raw.chartToolbarGlobal,
          timeframeFavorites:
            raw.chartToolbarGlobal?.timeframeFavorites ??
            legacyTimeframeFavorites,
        },
        raw.chartDataStrip ?? raw.chartToolbarGlobal?.chartDefaults,
      );
    })(),
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

export interface ChartPersistBackup {
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

export interface WorkspaceState {
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

export function downloadJson(filename: string, data: unknown) {
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

export function applyServerWorkspace(record: {
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

export type WorkspaceSet = (
  partial:
    | WorkspaceState
    | Partial<WorkspaceState>
    | ((state: WorkspaceState) => WorkspaceState | Partial<WorkspaceState>),
  replace?: boolean,
) => void;

export type WorkspaceGet = () => WorkspaceState;

/** Fragmento de acciones que un slice aporta al store compuesto. */
export type WorkspaceSlice = (
  get: WorkspaceGet,
  set: WorkspaceSet,
) => Partial<WorkspaceState>;
