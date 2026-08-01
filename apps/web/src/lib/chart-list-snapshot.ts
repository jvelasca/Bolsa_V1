import type { ChartDrawing } from '@bolsa/shared';
import type { IndicatorPreset, IndicatorTemplate } from '@bolsa/shared';
import {
  chartListStateKey,
  DEFAULT_LIST_CONFIG,
  mergeChartToolbarChartOverrides,
  mergeChartToolbarGlobalConfig,
  normalizeChartSeriesType,
  normalizeChartSeriesTypeParams,
  normalizeIndicatorPresets,
  normalizeIndicatorTemplates,
  snapshotFromChartTab,
  normalizeNewChartTemplateChartId,
  type ChartInstrumentSnapshot,
  type ChartTabState,
  type ListPanelConfig,
  type WorkspaceDocument,
} from '@bolsa/shared';
import { sanitizeChartDrawings } from '@bolsa/shared';

/** Une dibujos por id — solo para migraciones puntuales; no usar en borrados. */
export function mergeDrawingsById(
  primary: ChartDrawing[],
  secondary: ChartDrawing[],
): ChartDrawing[] {
  const map = new Map<string, ChartDrawing>();
  for (const drawing of secondary) map.set(drawing.id, drawing);
  for (const drawing of primary) map.set(drawing.id, { ...drawing });
  return Array.from(map.values());
}

function instrumentIdFromSnapshotKey(key: string): string | null {
  const sep = key.indexOf('::');
  if (sep < 0) return null;
  return key.slice(sep + 2);
}

/** Dibujos canónicos por instrumento según las pestañas abiertas en el workspace. */
function canonicalDrawingsByInstrument(
  workspace: WorkspaceDocument,
): Map<string, ChartDrawing[]> {
  const map = new Map<string, ChartDrawing[]>();
  for (const tab of workspace.charts) {
    map.set(tab.instrumentId, sanitizeChartDrawings(tab.drawings));
  }
  return map;
}

function listIdForTab(workspace: WorkspaceDocument, tab: ChartTabState): string {
  if (tab.sourceListId) return tab.sourceListId;
  if (workspace.chartListContext?.instrumentId === tab.instrumentId) {
    return workspace.chartListContext.listId;
  }
  return workspace.list?.apiListId ?? workspace.list?.id ?? 'default';
}

/** Lista de origen de un gráfico al cambiar de pestaña. */
export function resolveSourceListIdForTab(
  workspace: WorkspaceDocument,
  tab: ChartTabState,
): string | null {
  if (tab.sourceListId) return tab.sourceListId;

  const snapshots = workspace.chartStateByListInstrument ?? {};
  const listIds: string[] = [];
  for (const key of Object.keys(snapshots)) {
    const sep = key.indexOf('::');
    if (sep < 0) continue;
    const instrumentId = key.slice(sep + 2);
    if (instrumentId === tab.instrumentId) {
      listIds.push(key.slice(0, sep));
    }
  }

  const ctx = workspace.chartListContext;
  if (ctx?.instrumentId === tab.instrumentId) return ctx.listId;
  if (listIds.length > 0) return listIds[0]!;

  return workspace.list?.apiListId ?? workspace.list?.id ?? null;
}

export function applySnapshotToTab(
  tab: ChartTabState,
  snapshot: ChartInstrumentSnapshot,
  cloneChart: (config?: import('@bolsa/shared').ChartInstanceConfig) => import('@bolsa/shared').ChartInstanceConfig,
): ChartTabState {
  const chart = cloneChart(snapshot.chart);
  return {
    ...tab,
    timeframe: snapshot.timeframe,
    seriesType: normalizeChartSeriesType(snapshot.seriesType, tab.seriesType),
    seriesTypeParams: normalizeChartSeriesTypeParams(snapshot.seriesTypeParams ?? tab.seriesTypeParams),
    chart,
    indicatorInstances: snapshot.indicatorInstances.map((instance) => ({
      ...instance,
      parameters: { ...instance.parameters },
    })),
    drawings: sanitizeChartDrawings(snapshot.drawings),
    activeIndicatorTemplateId: snapshot.activeIndicatorTemplateId ?? null,
    toolbar: snapshot.toolbar ?? tab.toolbar,
    pricePanelHeightPct: snapshot.pricePanelHeightPct ?? tab.pricePanelHeightPct,
    drawingsLayerHidden: snapshot.drawingsLayerHidden ?? tab.drawingsLayerHidden,
    drawingsLayerLocked: snapshot.drawingsLayerLocked ?? tab.drawingsLayerLocked,
  };
}

/** Aplica el snapshot de la lista activa (sin unir con dibujos previos de otras fuentes). */
export function mergeSnapshotIntoTab(
  tab: ChartTabState,
  snapshot: ChartInstrumentSnapshot,
  cloneChart: (config?: import('@bolsa/shared').ChartInstanceConfig) => import('@bolsa/shared').ChartInstanceConfig,
): ChartTabState {
  const applied = applySnapshotToTab(tab, snapshot, cloneChart);
  return {
    ...applied,
    activeIndicatorTemplateId: tab.activeIndicatorTemplateId ?? applied.activeIndicatorTemplateId,
  };
}

/**
 * Rellena pestañas vacías solo desde el snapshot de su lista actual.
 * No fusiona snapshots de otras listas para el mismo instrumento.
 */
export function hydrateChartsFromListSnapshots(
  workspace: WorkspaceDocument,
): WorkspaceDocument {
  const snapshots = workspace.chartStateByListInstrument;
  if (!snapshots || Object.keys(snapshots).length === 0) return workspace;

  const charts = workspace.charts.map((tab) => {
    if (tab.drawings.length > 0) return tab;

    const listId = listIdForTab(workspace, tab);
    const key = chartListStateKey(listId, tab.instrumentId);
    const snap = snapshots[key];
    if (!snap?.drawings?.length) return tab;

    return {
      ...tab,
      drawings: sanitizeChartDrawings(snap.drawings),
    };
  });

  return { ...workspace, charts };
}

/** Propaga el estado de cada pestaña abierta a snapshots; no conserva instrumentos cerrados. */
export function syncSnapshotsFromCharts(workspace: WorkspaceDocument): WorkspaceDocument {
  const canonical = canonicalDrawingsByInstrument(workspace);
  const snapshots: Record<string, ChartInstrumentSnapshot> = {};

  for (const tab of workspace.charts) {
    const listId = listIdForTab(workspace, tab);
    const key = chartListStateKey(listId, tab.instrumentId);
    const next = snapshotFromChartTab(tab, null);
    snapshots[key] = {
      ...next,
      drawings: canonical.get(tab.instrumentId) ?? [],
      indicatorInstances: next.indicatorInstances,
    };
  }

  const prev = workspace.chartStateByListInstrument ?? {};
  if (snapshotRecordsEqual(prev, snapshots)) {
    return workspace;
  }

  return {
    ...workspace,
    chartStateByListInstrument: snapshots,
  };
}

function snapshotRecordsEqual(
  a: Record<string, ChartInstrumentSnapshot>,
  b: Record<string, ChartInstrumentSnapshot>,
): boolean {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const key of keysA) {
    const left = a[key];
    const right = b[key];
    if (!left || !right) return false;
    if (left.timeframe !== right.timeframe) return false;
    if (left.seriesType !== right.seriesType) return false;
    if ((left.drawings?.length ?? 0) !== (right.drawings?.length ?? 0)) return false;
    if (left.indicatorInstances.length !== right.indicatorInstances.length) return false;
    if (left.activeIndicatorTemplateId !== right.activeIndicatorTemplateId) return false;
  }
  return true;
}

/** Elimina snapshots y contexto de lista para instrumentos sin pestaña abierta. */
export function pruneOrphanChartSnapshots(workspace: WorkspaceDocument): WorkspaceDocument {
  const openInstruments = new Set(workspace.charts.map((tab) => tab.instrumentId));
  const snapshots: Record<string, ChartInstrumentSnapshot> = {};
  for (const [key, snap] of Object.entries(workspace.chartStateByListInstrument ?? {})) {
    const instrumentId = instrumentIdFromSnapshotKey(key);
    if (instrumentId && openInstruments.has(instrumentId)) {
      snapshots[key] = snap;
    }
  }
  const ctx = workspace.chartListContext;
  const chartListContext =
    ctx && openInstruments.has(ctx.instrumentId) ? ctx : null;
  return { ...workspace, chartStateByListInstrument: snapshots, chartListContext };
}

export function totalChartDrawings(charts: ChartTabState[]): number {
  return charts.reduce((sum, tab) => sum + tab.drawings.length, 0);
}

export function totalSnapshotDrawings(
  snapshots: Record<string, ChartInstrumentSnapshot> | undefined,
): number {
  if (!snapshots) return 0;
  return Object.values(snapshots).reduce((sum, snap) => sum + (snap.drawings?.length ?? 0), 0);
}

function listConfigHasCarouselState(list?: ListPanelConfig): boolean {
  if (!list) return false;
  return (
    list.carouselInitialized === true ||
    (list.carouselListIds?.length ?? 0) > 0 ||
    (list.carouselPinnedListNames?.length ?? 0) > 0 ||
    (list.carouselHiddenListIds?.length ?? 0) > 0
  );
}

function listConfigHasColumnLayouts(list?: ListPanelConfig): boolean {
  return Object.keys(list?.columnLayoutsByListId ?? {}).length > 0;
}

function mergeListConfig(
  preferred?: ListPanelConfig,
  fallback?: ListPanelConfig,
): ListPanelConfig {
  const base: ListPanelConfig = { ...DEFAULT_LIST_CONFIG, ...fallback };
  const patch: Partial<ListPanelConfig> = preferred ?? {};
  const preferredCarouselReady = listConfigHasCarouselState(patch as ListPanelConfig);
  const fallbackCarouselReady = listConfigHasCarouselState(base);
  return {
    ...base,
    ...patch,
    columnLayoutsByListId: {
      ...(base.columnLayoutsByListId ?? {}),
      ...(patch.columnLayoutsByListId ?? {}),
    },
    sortByListId: { ...(base.sortByListId ?? {}), ...(patch.sortByListId ?? {}) },
    carouselListIds:
      preferredCarouselReady && patch.carouselListIds !== undefined
        ? patch.carouselListIds
        : fallbackCarouselReady
          ? base.carouselListIds
          : patch.carouselListIds ?? base.carouselListIds,
    carouselPinnedListNames:
      preferredCarouselReady && patch.carouselPinnedListNames !== undefined
        ? patch.carouselPinnedListNames
        : fallbackCarouselReady
          ? base.carouselPinnedListNames
          : patch.carouselPinnedListNames ?? base.carouselPinnedListNames,
    carouselHiddenListIds:
      preferredCarouselReady && patch.carouselHiddenListIds !== undefined
        ? patch.carouselHiddenListIds
        : fallbackCarouselReady
          ? base.carouselHiddenListIds
          : patch.carouselHiddenListIds ?? base.carouselHiddenListIds,
    carouselInitialized: preferredCarouselReady || fallbackCarouselReady,
    rowActionsWidth: patch.rowActionsWidth ?? base.rowActionsWidth,
    visualizationEntries:
      (patch.visualizationEntries?.length ?? 0) > 0
        ? patch.visualizationEntries
        : (base.visualizationEntries?.length ?? 0) > 0
          ? base.visualizationEntries
          : patch.visualizationEntries ?? base.visualizationEntries,
    columnLayout:
      patch.columnLayout?.length && !listConfigHasColumnLayouts(patch as ListPanelConfig)
        ? patch.columnLayout
        : base.columnLayout?.length
          ? base.columnLayout
          : patch.columnLayout ?? base.columnLayout,
  };
}

export function workspaceTimestamp(doc: WorkspaceDocument): number {
  const parsed = Date.parse(doc.updatedAt);
  return Number.isFinite(parsed) ? parsed : 0;
}

function mergeChartTabState(primary: ChartTabState, secondary: ChartTabState): ChartTabState {
  const toolbar = mergeChartToolbarChartOverrides(primary.toolbar, secondary.toolbar);
  return {
    ...secondary,
    ...primary,
    drawings: sanitizeChartDrawings(primary.drawings),
    toolbar,
  };
}

function mergeSnapshotMaps(
  newer: WorkspaceDocument,
  older: WorkspaceDocument,
): Record<string, ChartInstrumentSnapshot> {
  const openInstruments = new Set(newer.charts.map((tab) => tab.instrumentId));
  const snapshots: Record<string, ChartInstrumentSnapshot> = {};

  for (const [key, snap] of Object.entries(newer.chartStateByListInstrument ?? {})) {
    const instrumentId = instrumentIdFromSnapshotKey(key);
    if (instrumentId && !openInstruments.has(instrumentId)) continue;
    snapshots[key] = {
      ...snap,
      drawings: sanitizeChartDrawings(snap.drawings ?? []),
    };
  }

  for (const [key, snap] of Object.entries(older.chartStateByListInstrument ?? {})) {
    if (snapshots[key]) continue;
    const instrumentId = instrumentIdFromSnapshotKey(key);
    if (instrumentId && !openInstruments.has(instrumentId)) continue;
    snapshots[key] = {
      ...snap,
      drawings: sanitizeChartDrawings(snap.drawings ?? []),
    };
  }

  return snapshots;
}

function mergeIndicatorTemplates(
  primary: IndicatorTemplate[] | undefined,
  secondary: IndicatorTemplate[] | undefined,
): IndicatorTemplate[] {
  const base = normalizeIndicatorTemplates(primary);
  const other = normalizeIndicatorTemplates(secondary);
  const byId = new Map(
    base.map((template) => [
      template.id,
      { ...template, presetIds: [...(template.presetIds ?? [])] },
    ]),
  );
  for (const template of other) {
    const existing = byId.get(template.id);
    if (!existing) {
      byId.set(template.id, {
        ...template,
        presetIds: [...(template.presetIds ?? [])],
      });
      continue;
    }
    const mergedPresetIds = new Set([
      ...(existing.presetIds ?? []),
      ...(template.presetIds ?? []),
    ]);
    byId.set(template.id, {
      ...existing,
      ...template,
      presetIds: [...mergedPresetIds],
    });
  }
  return [...byId.values()];
}

function mergeIndicatorPresets(
  primary: IndicatorPreset[] | undefined,
  secondary: IndicatorPreset[] | undefined,
): IndicatorPreset[] {
  const byId = new Map<string, IndicatorPreset>();
  for (const preset of normalizeIndicatorPresets(primary)) {
    byId.set(preset.id, preset);
  }
  for (const preset of normalizeIndicatorPresets(secondary)) {
    const existing = byId.get(preset.id);
    if (!existing) {
      byId.set(preset.id, preset);
      continue;
    }
    if (existing.source === 'builtin' && preset.source !== 'builtin') {
      byId.set(preset.id, preset);
    }
  }
  return [...byId.values()];
}

export function mergeWorkspaceChartState(
  preferred: WorkspaceDocument,
  fallback: WorkspaceDocument,
): WorkspaceDocument {
  const preferredNewer = workspaceTimestamp(preferred) >= workspaceTimestamp(fallback);
  const newerDoc = preferredNewer ? preferred : fallback;
  const olderDoc = preferredNewer ? fallback : preferred;
  const settingsPrimary = preferredNewer ? preferred : fallback;
  const settingsSecondary = preferredNewer ? fallback : preferred;

  const byInstrument = new Map<string, ChartTabState>();
  for (const tab of olderDoc.charts) byInstrument.set(tab.instrumentId, tab);
  for (const tab of newerDoc.charts) {
    const other = byInstrument.get(tab.instrumentId);
    if (!other) {
      byInstrument.set(tab.instrumentId, tab);
      continue;
    }
    byInstrument.set(tab.instrumentId, mergeChartTabState(tab, other));
  }

  // La lista de pestañas abiertas la marca el documento más reciente (no reabrir cerradas).
  const charts = newerDoc.charts.map((tab) => {
    const merged = byInstrument.get(tab.instrumentId);
    return merged ?? tab;
  });

  const activeChartId = charts.some((tab) => tab.id === newerDoc.activeChartId)
    ? newerDoc.activeChartId
    : charts.some((tab) => tab.id === olderDoc.activeChartId)
      ? olderDoc.activeChartId
      : (charts.at(-1)?.id ?? null);

  const merged: WorkspaceDocument = {
    ...newerDoc,
    charts,
    list: mergeListConfig(settingsPrimary.list, settingsSecondary.list),
    chartToolbarGlobal: mergeChartToolbarGlobalConfig(
      settingsPrimary.chartToolbarGlobal,
      settingsSecondary.chartToolbarGlobal,
    ),
    activeChartId,
    chartListContext: newerDoc.chartListContext ?? olderDoc.chartListContext,
    chartStateByListInstrument: mergeSnapshotMaps(newerDoc, olderDoc),
    chartNewTabSeed: newerDoc.chartNewTabSeed ?? olderDoc.chartNewTabSeed,
    preferences: {
      ...olderDoc.preferences,
      ...newerDoc.preferences,
      newChartTemplateChartId:
        newerDoc.preferences.newChartTemplateChartId ??
        olderDoc.preferences.newChartTemplateChartId ??
        null,
    },
    layout: {
      ...newerDoc.layout,
      chartInspectorOpen:
        newerDoc.layout.chartInspectorOpen ?? olderDoc.layout.chartInspectorOpen,
    },
    indicatorTemplates: mergeIndicatorTemplates(
      newerDoc.indicatorTemplates,
      olderDoc.indicatorTemplates,
    ),
    indicatorPresets: mergeIndicatorPresets(newerDoc.indicatorPresets, olderDoc.indicatorPresets),
    indicatorFavoritesByListId: {
      ...(olderDoc.indicatorFavoritesByListId ?? {}),
      ...(newerDoc.indicatorFavoritesByListId ?? {}),
    },
    defaultIndicatorTemplateId:
      newerDoc.defaultIndicatorTemplateId ?? olderDoc.defaultIndicatorTemplateId ?? null,
    updatedAt: newerDoc.updatedAt,
  };

  merged.preferences.newChartTemplateChartId = normalizeNewChartTemplateChartId(
    merged.preferences.newChartTemplateChartId,
    charts,
  );

  return hydrateChartsFromListSnapshots(syncSnapshotsFromCharts(merged));
}

export function attachActiveTabListSnapshot(
  workspace: WorkspaceDocument,
  openDrawingEditorId: string | null,
): WorkspaceDocument {
  const tab = workspace.charts.find((item) => item.id === workspace.activeChartId);
  if (!tab) return workspace;

  const listId = listIdForTab(workspace, tab);
  const key = chartListStateKey(listId, tab.instrumentId);
  const next = snapshotFromChartTab(tab, openDrawingEditorId);

  return syncSnapshotsFromCharts({
    ...workspace,
    chartStateByListInstrument: {
      ...(workspace.chartStateByListInstrument ?? {}),
      [key]: {
        ...next,
        drawings: sanitizeChartDrawings(tab.drawings),
      },
    },
  });
}
