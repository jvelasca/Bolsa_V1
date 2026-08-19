/**
 * Sync SEMI Confirm F3 cola ↔ PostgreSQL.
 * sessionStorage = cache; BD = SoT multi-dispositivo / multi-cuenta.
 *
 * @see docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
 */

import { api } from "@/lib/api";
import { getActiveAccountId } from "@/stores/active-account-store";
import {
  type SupervisedQueueItem,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";

let syncTimer: number | null = null;
const hydratedAccounts = new Set<string>();
let pushWired = false;
let hydrating = false;

function asItems(raw: unknown): SupervisedQueueItem[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (x): x is SupervisedQueueItem =>
      !!x &&
      typeof x === "object" &&
      typeof (x as SupervisedQueueItem).id === "string" &&
      !!(x as SupervisedQueueItem).payload &&
      typeof (x as SupervisedQueueItem).payload === "object",
  );
}

/**
 * P2.8: serialización tipada → DTO de wire sin scattered `as unknown as`.
 * P2.6 (R-2): `SupervisedQueueItem` y `SupervisedF3QueueItemDto` son ahora el
 * mismo tipo compartido (hogar canónico en @bolsa/shared), por lo que la
 * asignación de `payload` es directa, sin cast. El wire sigue siendo un blob
 * JSON opaco round-trip del BE: tipar no cambia el valor serializado.
 */
function toF3ItemDto(item: SupervisedQueueItem) {
  return {
    id: item.id,
    enqueuedAt: item.enqueuedAt,
    scanId: item.scanId,
    symbol: item.symbol,
    origin: item.origin,
    payload: item.payload,
  };
}

function localBundle() {
  const s = useSupervisedF3QueueStore.getState();
  return {
    items: s.items.map(toF3ItemDto),
    activeId: s.activeId,
  };
}

/** Pull BD → store (BD gana). */
export async function hydrateSupervisedF3FromServer(
  accountId: string,
): Promise<void> {
  if (!accountId) return;
  hydrating = true;
  try {
    const res = await api.getAccountSupervisedF3(accountId);
    const items = asItems(res.data.items);
    const activeId =
      typeof res.data.activeId === "string" &&
      items.some((i) => i.id === res.data.activeId)
        ? res.data.activeId
        : (items[0]?.id ?? null);
    useSupervisedF3QueueStore.setState({ items, activeId });
    hydratedAccounts.add(accountId);
  } catch {
    // Offline / API down: keep local cache.
  } finally {
    hydrating = false;
  }
}

export async function pushSupervisedF3ToServer(
  accountId: string,
): Promise<void> {
  if (!accountId || hydrating) return;
  try {
    await api.syncAccountSupervisedF3(accountId, localBundle());
  } catch {
    // Retry on next write / hydrate.
  }
}

export function scheduleSupervisedF3Push(accountId?: string | null): void {
  if (hydrating) return;
  const id = accountId ?? getActiveAccountId();
  if (!id) return;
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = window.setTimeout(() => {
    void pushSupervisedF3ToServer(id);
  }, 450);
}

/**
 * Primera visita: si BD vacía y hay cola local, push; luego hydrate (BD gana).
 */
export async function ensureSupervisedF3Hydrated(
  accountId: string,
): Promise<void> {
  if (!accountId || hydratedAccounts.has(accountId)) return;
  const localItems = useSupervisedF3QueueStore.getState().items.length;
  try {
    const res = await api.getAccountSupervisedF3(accountId);
    const remoteEmpty = (res.data.items?.length ?? 0) === 0;
    if (remoteEmpty && localItems > 0) {
      await pushSupervisedF3ToServer(accountId);
    }
  } catch {
    // ignore
  }
  await hydrateSupervisedF3FromServer(accountId);
}

export function wireSupervisedF3PushSubscriptions(): void {
  if (pushWired || typeof window === "undefined") return;
  pushWired = true;
  useSupervisedF3QueueStore.subscribe(() => {
    scheduleSupervisedF3Push();
  });
}

/** Test helper: reset module flags. */
export function _resetSupervisedF3SyncForTests(): void {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = null;
  hydratedAccounts.clear();
  pushWired = false;
  hydrating = false;
}
