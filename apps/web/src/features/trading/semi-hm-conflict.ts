/**
 * Conflicto H (Finalistas) ≠ M (Radar/momento) en la cola F3.
 * Mismo instrumentId con orígenes distintos → humano elige en Confirm.
 *
 * @see docs/engineering/demo-operating-modes-brief-2026-08-03.md §2
 */

import {
  resolveSupervisedQueueOrigin,
  type SupervisedQueueItem,
} from "@/stores/supervised-f3-queue-store";

export type HmConflictPair = {
  instrumentId: string;
  symbol?: string;
  /** Finalistas / histórico */
  h: SupervisedQueueItem;
  /** Alarm / momento */
  m: SupervisedQueueItem;
};

export function findHmConflicts(
  items: readonly SupervisedQueueItem[],
): HmConflictPair[] {
  const byInst = new Map<string, SupervisedQueueItem[]>();
  for (const item of items) {
    const id = item.payload.instrumentId;
    const list = byInst.get(id) ?? [];
    list.push(item);
    byInst.set(id, list);
  }
  const out: HmConflictPair[] = [];
  for (const [instrumentId, list] of byInst) {
    const h = list.find((i) => resolveSupervisedQueueOrigin(i) === "finalists");
    const m = list.find((i) => resolveSupervisedQueueOrigin(i) === "alarm");
    if (!h || !m) continue;
    out.push({
      instrumentId,
      symbol: h.symbol ?? m.symbol ?? h.payload.symbol ?? m.payload.symbol,
      h,
      m,
    });
  }
  return out;
}

export function conflictForActive(
  pairs: readonly HmConflictPair[],
  activeId: string | null,
): HmConflictPair | null {
  if (!activeId) return null;
  return pairs.find((p) => p.h.id === activeId || p.m.id === activeId) ?? null;
}
