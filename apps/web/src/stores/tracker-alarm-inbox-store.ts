/**
 * Inbox cliente de alarmas Radar (B1) — entrada/salida de trackers.
 * Persistido en session/local; filtrado por cuenta activa DEMO.
 *
 * @see docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
 * @see docs/engineering/research-radar-unification-2026-07-31.md §3b
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ScanHitDto, ScanRunResultDto } from "@bolsa/shared";
import { isAlarmSafeMode } from "@/features/screeners/tracker-alarms";

export type TrackerAlarmInboxItem = {
  id: string;
  accountId: string;
  scanId: string;
  instrumentId: string;
  symbol: string;
  signalKind: string;
  price: number | null;
  mode: string;
  policyId: string | null;
  listId: string | null;
  timeframe: string | null;
  strategyDefinitionId: string | null;
  createdAt: string;
  ackedAt: string | null;
};

type TrackerAlarmInboxState = {
  items: TrackerAlarmInboxItem[];
  /** Escans ya ingeridos (evita duplicar al remount). */
  ingestedScanIds: string[];
  pushFromScan: (
    result: ScanRunResultDto,
    accountId: string,
    opts?: { listId?: string | null; maxHits?: number },
  ) => number;
  ack: (id: string) => void;
  ackAllForAccount: (accountId: string) => void;
  clearForAccount: (accountId: string) => void;
};

const MAX_ITEMS = 50;
const MAX_INGESTED = 80;

export function unreadCountForAccount(
  items: TrackerAlarmInboxItem[],
  accountId: string | null | undefined,
): number {
  if (!accountId) return 0;
  return items.filter((i) => i.accountId === accountId && !i.ackedAt).length;
}

export function itemsForAccount(
  items: TrackerAlarmInboxItem[],
  accountId: string | null | undefined,
): TrackerAlarmInboxItem[] {
  if (!accountId) return [];
  return items.filter((i) => i.accountId === accountId);
}

function hitToItem(
  hit: ScanHitDto,
  meta: {
    accountId: string;
    scanId: string;
    mode: string;
    policyId: string | null;
    listId: string | null;
    timeframe: string | null;
    createdAt: string;
  },
): TrackerAlarmInboxItem {
  return {
    id: `${meta.scanId}:${hit.instrumentId}:${hit.signal.kind}:${hit.signal.barIndex ?? 0}`,
    accountId: meta.accountId,
    scanId: meta.scanId,
    instrumentId: hit.instrumentId,
    symbol: hit.symbol,
    signalKind: hit.signal.kind,
    price:
      typeof hit.signal.price === "number" && Number.isFinite(hit.signal.price)
        ? hit.signal.price
        : null,
    mode: meta.mode,
    policyId: meta.policyId,
    listId: meta.listId,
    timeframe: meta.timeframe,
    strategyDefinitionId:
      typeof hit.signal.strategyDefinitionId === "string" &&
      hit.signal.strategyDefinitionId.trim()
        ? hit.signal.strategyDefinitionId.trim()
        : null,
    createdAt: meta.createdAt,
    ackedAt: null,
  };
}

export const useTrackerAlarmInboxStore = create<TrackerAlarmInboxState>()(
  persist(
    (set, get) => ({
      items: [],
      ingestedScanIds: [],
      pushFromScan: (result, accountId, opts) => {
        if (!accountId || !result.scanId) return 0;
        const route = result.alarmRoute;
        if (!route || !(route.actions?.length ?? 0)) return 0;
        if (!isAlarmSafeMode(route.mode)) return 0;
        if (get().ingestedScanIds.includes(result.scanId)) return 0;

        const maxHits = opts?.maxHits ?? 12;
        const createdAt = new Date().toISOString();
        const listId = opts?.listId ?? result.listId ?? null;
        const timeframe = result.timeframe ?? null;
        const incoming = result.hits.slice(0, maxHits).map((hit) =>
          hitToItem(hit, {
            accountId,
            scanId: result.scanId,
            mode: route.mode,
            policyId: route.policyId ?? null,
            listId,
            timeframe,
            createdAt,
          }),
        );
        if (incoming.length === 0) return 0;

        set((s) => {
          const existingIds = new Set(s.items.map((i) => i.id));
          const fresh = incoming.filter((i) => !existingIds.has(i.id));
          return {
            items: [...fresh, ...s.items].slice(0, MAX_ITEMS),
            ingestedScanIds: [result.scanId, ...s.ingestedScanIds].slice(
              0,
              MAX_INGESTED,
            ),
          };
        });
        return incoming.length;
      },
      ack: (id) => {
        const at = new Date().toISOString();
        set((s) => ({
          items: s.items.map((i) =>
            i.id === id ? { ...i, ackedAt: i.ackedAt ?? at } : i,
          ),
        }));
      },
      ackAllForAccount: (accountId) => {
        const at = new Date().toISOString();
        set((s) => ({
          items: s.items.map((i) =>
            i.accountId === accountId && !i.ackedAt ? { ...i, ackedAt: at } : i,
          ),
        }));
      },
      clearForAccount: (accountId) => {
        set((s) => ({
          items: s.items.filter((i) => i.accountId !== accountId),
        }));
      },
    }),
    {
      name: "bolsa-tracker-alarm-inbox-v1",
      partialize: (s) => ({
        items: s.items,
        ingestedScanIds: s.ingestedScanIds,
      }),
    },
  ),
);
