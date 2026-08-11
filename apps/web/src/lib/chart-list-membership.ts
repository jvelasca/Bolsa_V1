/**
 * Membresía lista↔instrumento para contexto de gráfico y foco de watchlist.
 *
 * Prioridad al elegir lista visible: **Cartera → Estudio → resto**.
 *
 * @see docs/engineering/visualizados-list-ux-2026-08-06.md
 */

import {
  ESTUDIO_LIST_ID,
  isVirtualListId,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
} from "@bolsa/shared";
import type {
  ChartListContext,
  ChartTabState,
  WorkspaceDocument,
} from "@bolsa/shared";

export interface VirtualListMembership {
  visualization: ReadonlySet<string>;
  portfolio: ReadonlySet<string>;
  pendingOrders: ReadonlySet<string>;
}

export interface ChartListMembershipSnapshot {
  api: Record<string, ReadonlySet<string>>;
  listMeta: { id: string; source: string }[];
  virtual: VirtualListMembership;
}

export function isInstrumentInList(
  listId: string,
  instrumentId: string,
  membership: ChartListMembershipSnapshot,
): boolean {
  if (listId === VIRTUAL_LIST_VISUALIZATION) {
    return membership.virtual.visualization.has(instrumentId);
  }
  if (listId === VIRTUAL_LIST_PORTFOLIO) {
    return membership.virtual.portfolio.has(instrumentId);
  }
  if (listId === VIRTUAL_LIST_PENDING_ORDERS) {
    return membership.virtual.pendingOrders.has(instrumentId);
  }
  if (isVirtualListId(listId)) return false;
  return membership.api[listId]?.has(instrumentId) ?? false;
}

function collectCandidateListIds(
  workspace: WorkspaceDocument,
  tab: ChartTabState,
): string[] {
  const seen = new Set<string>();
  const candidates: string[] = [];

  function push(listId: string | undefined | null) {
    if (!listId || seen.has(listId)) return;
    seen.add(listId);
    candidates.push(listId);
  }

  push(tab.sourceListId);
  if (workspace.chartListContext?.instrumentId === tab.instrumentId) {
    push(workspace.chartListContext.listId);
  }
  for (const key of Object.keys(workspace.chartStateByListInstrument ?? {})) {
    if (!key.endsWith(`::${tab.instrumentId}`)) continue;
    push(key.slice(0, key.indexOf("::")));
  }
  push(workspace.list?.apiListId ?? workspace.list?.id);

  return candidates;
}

/**
 * Prioridad al mostrar un valor en varias listas:
 * 1) Cartera · 2) Estudio · 3) resto (candidatos, Visualizados, personal, índice…).
 */
export function resolvePreferredListIdForInstrument(
  instrumentId: string,
  membership: ChartListMembershipSnapshot,
  preferredCandidates: ReadonlyArray<string> = [],
): string | null {
  if (!instrumentId) return null;

  if (membership.virtual.portfolio.has(instrumentId)) {
    return VIRTUAL_LIST_PORTFOLIO;
  }
  if (membership.api[ESTUDIO_LIST_ID]?.has(instrumentId)) {
    return ESTUDIO_LIST_ID;
  }

  for (const listId of preferredCandidates) {
    if (
      listId === VIRTUAL_LIST_PORTFOLIO ||
      listId === ESTUDIO_LIST_ID ||
      listId === VIRTUAL_LIST_VISUALIZATION ||
      listId === VIRTUAL_LIST_PENDING_ORDERS
    ) {
      continue;
    }
    if (isInstrumentInList(listId, instrumentId, membership)) return listId;
  }

  if (membership.virtual.visualization.has(instrumentId)) {
    return VIRTUAL_LIST_VISUALIZATION;
  }
  if (membership.virtual.pendingOrders.has(instrumentId)) {
    return VIRTUAL_LIST_PENDING_ORDERS;
  }

  const containing = membership.listMeta.filter((list) =>
    membership.api[list.id]?.has(instrumentId),
  );
  const custom = containing.find((list) => list.source === "custom");
  if (custom) return custom.id;
  const catalog = containing.find((list) => list.source === "catalog");
  if (catalog) return catalog.id;
  return containing[0]?.id ?? null;
}

/** @deprecated Prefer {@link resolvePreferredListIdForInstrument}. */
export function resolveVirtualListForInstrument(
  instrumentId: string,
  membership: ChartListMembershipSnapshot,
): string | null {
  return resolvePreferredListIdForInstrument(instrumentId, membership);
}

export function findBestListForInstrument(
  instrumentId: string,
  membership: ChartListMembershipSnapshot,
): string | null {
  return resolvePreferredListIdForInstrument(instrumentId, membership);
}

/**
 * Resuelve la lista “fuente” de una pestaña al enfocarla / buscarla.
 * Prioridad: Cartera → Estudio → resto.
 */
export function resolveValidSourceListIdForTab(
  workspace: WorkspaceDocument,
  tab: ChartTabState,
  membership: ChartListMembershipSnapshot,
): string | null {
  if (!tab.instrumentId) return null;
  return resolvePreferredListIdForInstrument(
    tab.instrumentId,
    membership,
    collectCandidateListIds(workspace, tab),
  );
}

export function resolveChartListContext(
  workspace: WorkspaceDocument,
  membership: ChartListMembershipSnapshot | null,
): ChartListContext | null {
  const activeTab = workspace.charts.find(
    (tab) => tab.id === workspace.activeChartId,
  );
  if (!activeTab) return null;
  if (!membership) return workspace.chartListContext ?? null;

  const listId = resolveValidSourceListIdForTab(
    workspace,
    activeTab,
    membership,
  );
  return listId ? { listId, instrumentId: activeTab.instrumentId } : null;
}

export function reconcileWorkspaceChartMembership(
  workspace: WorkspaceDocument,
  membership: ChartListMembershipSnapshot | null,
): WorkspaceDocument {
  if (!membership) return workspace;

  let chartsChanged = false;
  const charts = workspace.charts.map((tab) => {
    const nextListId = resolveValidSourceListIdForTab(
      workspace,
      tab,
      membership,
    );
    const sourceListId = nextListId ?? undefined;
    if (tab.sourceListId === sourceListId) return tab;
    chartsChanged = true;
    return { ...tab, sourceListId };
  });

  const workspaceForContext = chartsChanged
    ? { ...workspace, charts }
    : workspace;
  const chartListContext = resolveChartListContext(
    workspaceForContext,
    membership,
  );
  const prevCtx = workspace.chartListContext;
  const contextSame =
    (prevCtx?.listId ?? null) === (chartListContext?.listId ?? null) &&
    (prevCtx?.instrumentId ?? null) ===
      (chartListContext?.instrumentId ?? null);

  if (!chartsChanged && contextSame) return workspace;
  return {
    ...workspace,
    charts: chartsChanged ? charts : workspace.charts,
    chartListContext,
  };
}

export function membershipFingerprint(
  snapshot: ChartListMembershipSnapshot,
): string {
  const apiParts = Object.keys(snapshot.api)
    .sort()
    .map(
      (listId) =>
        `${listId}:${[...(snapshot.api[listId] ?? [])].sort().join(",")}`,
    );
  const virtual = [
    [...snapshot.virtual.visualization].sort().join(","),
    [...snapshot.virtual.portfolio].sort().join(","),
    [...snapshot.virtual.pendingOrders].sort().join(","),
  ].join("|");
  const meta = snapshot.listMeta
    .map((list) => `${list.id}:${list.source}`)
    .join(",");
  return `${apiParts.join(";")}|${virtual}|${meta}`;
}
