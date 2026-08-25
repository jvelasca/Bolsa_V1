/**
 * P4 — cola de entradas read-only (TradePlan status → labels mesa).
 * Proyección de `buildActionQueue`; no decide ni encola.
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import { buildActionQueue } from "./hoy-queue.js";

export const MESA_ENTRY_STATUS_LABEL: Record<TradePlanStatusV1, string> = {
  WATCH: "Vigilar",
  ARMED: "Preparado",
  TRIGGERED: "Propuesto",
  BLOCKED: "Bloqueado",
  EXPIRED: "Descartado",
};

export type MesaEntryQueueRowV1 = {
  symbol: string;
  status: TradePlanStatusV1;
  statusLabel: string;
  gate: string;
};

export const MESA_ENTRY_GROUP_ORDER: TradePlanStatusV1[] = [
  "TRIGGERED",
  "ARMED",
  "WATCH",
  "BLOCKED",
  "EXPIRED",
];

export function buildMesaEntryQueue(
  board: DecisionBoardV1,
): MesaEntryQueueRowV1[] {
  return buildActionQueue(board).map((item) => ({
    symbol: item.symbol,
    status: item.status,
    statusLabel: MESA_ENTRY_STATUS_LABEL[item.status] ?? item.status,
    gate: item.gate,
  }));
}

export function groupMesaEntryQueue(
  rows: MesaEntryQueueRowV1[],
): Array<{
  status: TradePlanStatusV1;
  label: string;
  items: MesaEntryQueueRowV1[];
}> {
  const byStatus = new Map<TradePlanStatusV1, MesaEntryQueueRowV1[]>();
  for (const status of MESA_ENTRY_GROUP_ORDER) {
    byStatus.set(status, []);
  }
  for (const row of rows) {
    const bucket = byStatus.get(row.status) ?? [];
    bucket.push(row);
    byStatus.set(row.status, bucket);
  }
  return MESA_ENTRY_GROUP_ORDER.map((status) => ({
    status,
    label: MESA_ENTRY_STATUS_LABEL[status],
    items: byStatus.get(status) ?? [],
  })).filter((group) => group.items.length > 0);
}

export type MesaEntryGateFilter = "ALL" | "PASS" | "VETO" | "DEFERRED";

export type MesaEntryQueueFiltersV1 = {
  /** Empty = all status buckets. */
  statuses?: TradePlanStatusV1[];
  gate?: MesaEntryGateFilter;
  symbolQuery?: string;
};

export function filterMesaEntryQueue(
  rows: MesaEntryQueueRowV1[],
  filters: MesaEntryQueueFiltersV1 = {},
): MesaEntryQueueRowV1[] {
  const statuses = filters.statuses?.length ? new Set(filters.statuses) : null;
  const gate = filters.gate ?? "ALL";
  const q = filters.symbolQuery?.trim().toLowerCase() ?? "";

  return rows.filter((row) => {
    if (statuses && !statuses.has(row.status)) return false;
    if (gate !== "ALL" && row.gate.toUpperCase() !== gate) return false;
    if (q && !row.symbol.toLowerCase().includes(q)) return false;
    return true;
  });
}

/** Hint régimen/mesa desde Decision Board (read-only). */
export function deriveMesaRegimeHint(board: DecisionBoardV1): string | null {
  for (const session of board.decisionSessions) {
    const gate = session.gate?.toUpperCase();
    if (gate === "VETO" || gate === "DEFERRED") {
      const setup = session.wyckoffSpringAnchor as
        | { phase?: string; entrySetup?: string }
        | undefined;
      if (setup?.phase && setup.phase !== "none") {
        return `fase ${setup.phase}`;
      }
    }
  }
  const vetoed = board.buckets?.vetoed ?? 0;
  if (vetoed > 0) return `${vetoed} veto(s)`;
  return null;
}
