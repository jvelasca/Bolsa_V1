/**
 * Cola humana CORE-R (localStorage vía zustand persist).
 *
 * Sync desde informe `bolsa-core-r-report-v1` (filas con `coreRNeedsAction`)
 * + filas extra PnL DEMO (`extraRows` / `syncFromReport`).
 * Deep-links Lab / Finalistas / Checklist / F3 — no muta TOP ni paper.
 * Cap 40 · dedupe open por listId+instrumentId.
 *
 * @see research/observations/ISSUES.md · CORE-R
 * @see docs/engineering/list-auto-ops-2026-07-29.md § CORE-R
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  type CoreRAction,
  type CoreRReport,
  type CoreRReportRow,
  type CoreRVerdict,
  coreRNeedsAction,
  listCoreRActionRows,
  readCoreRReport,
} from '@/features/backtests/core-r-judgment';

export const CORE_R_REVIEW_QUEUE_KEY = 'bolsa-core-r-review-queue-v1';
export const CORE_R_REVIEW_QUEUE_MAX = 40;

export type CoreRReviewQueueStatus = 'open' | 'done';

export type CoreRReviewQueueItem = {
  id: string;
  listId: string;
  instrumentId: string;
  symbol: string;
  verdict: CoreRVerdict;
  reason: string;
  actions: CoreRAction[];
  timeframe: string;
  enqueuedAt: string;
  status: CoreRReviewQueueStatus;
};

type CoreRReviewQueueState = {
  items: CoreRReviewQueueItem[];
  /**
   * Sync open items from report (+ filas extra p.ej. PnL demo).
   * Returns # newly enqueued.
   */
  syncFromReport: (
    listId: string,
    report?: CoreRReport | null,
    extraRows?: CoreRReportRow[],
  ) => number;
  dismiss: (id: string) => void;
  /** Marca open→done (opcionalmente filtrado por listId). Returns # cerrados. */
  dismissOpen: (listId?: string) => number;
  clearDone: () => void;
  clearList: (listId: string) => void;
  openForList: (listId: string) => CoreRReviewQueueItem[];
  openCount: (listId?: string) => number;
};

function itemKey(listId: string, instrumentId: string): string {
  return `${listId}:${instrumentId}`;
}

export function primaryCoreRAction(
  actions: ReadonlyArray<CoreRAction>,
): CoreRAction | null {
  const withHref = actions.find((a) => a.href && a.id !== 'none');
  return withHref ?? null;
}

export const useCoreRReviewQueueStore = create<CoreRReviewQueueState>()(
  persist(
    (set, get) => ({
      items: [],
      syncFromReport: (listId, reportArg, extraRows) => {
        if (!listId) return 0;
        const report = reportArg ?? readCoreRReport(listId);
        const actionRows = [
          ...listCoreRActionRows(report),
          ...(extraRows ?? []).filter((r) => coreRNeedsAction(r.verdict)),
        ];
        if (actionRows.length === 0) return 0;

        const timeframe = report?.timeframe ?? '1d';
        const now = new Date().toISOString();
        let added = 0;
        set((s) => {
          const openKeys = new Set(
            s.items
              .filter((i) => i.status === 'open')
              .map((i) => itemKey(i.listId, i.instrumentId)),
          );
          const next = [...s.items];
          for (const row of actionRows) {
            if (!coreRNeedsAction(row.verdict)) continue;
            const key = itemKey(listId, row.instrumentId);
            if (openKeys.has(key)) continue;
            openKeys.add(key);
            next.unshift({
              id: `crq-${listId.slice(0, 8)}-${row.instrumentId.slice(0, 8)}-${Date.now()}-${added}`,
              listId,
              instrumentId: row.instrumentId,
              symbol: row.symbol,
              verdict: row.verdict,
              reason: row.reason,
              actions: row.actions,
              timeframe,
              enqueuedAt: now,
              status: 'open',
            });
            added += 1;
          }
          const open = next.filter((i) => i.status === 'open');
          const done = next.filter((i) => i.status === 'done');
          const trimmed = [...open, ...done].slice(0, CORE_R_REVIEW_QUEUE_MAX);
          return { items: trimmed };
        });
        return added;
      },
      dismiss: (id) =>
        set((s) => ({
          items: s.items.map((i) =>
            i.id === id ? { ...i, status: 'done' as const } : i,
          ),
        })),
      dismissOpen: (listId) => {
        let n = 0;
        set((s) => ({
          items: s.items.map((i) => {
            if (i.status !== 'open') return i;
            if (listId && i.listId !== listId) return i;
            n += 1;
            return { ...i, status: 'done' as const };
          }),
        }));
        return n;
      },
      clearDone: () =>
        set((s) => ({ items: s.items.filter((i) => i.status !== 'done') })),
      clearList: (listId) =>
        set((s) => ({ items: s.items.filter((i) => i.listId !== listId) })),
      openForList: (listId) =>
        get().items.filter((i) => i.listId === listId && i.status === 'open'),
      openCount: (listId) => {
        const items = get().items;
        if (!listId) return items.filter((i) => i.status === 'open').length;
        return items.filter((i) => i.listId === listId && i.status === 'open')
          .length;
      },
    }),
    { name: CORE_R_REVIEW_QUEUE_KEY },
  ),
);
