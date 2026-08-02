/**
 * Sync CORE-R cliente ↔ PostgreSQL (Q3.4).
 * localStorage = cache offline; BD = SoT multi-dispositivo.
 * No auto-paper · no pisa TOP.
 */

import { api } from '@/lib/api';
import {
  CORE_R_ENGINE,
  type CoreRReport,
  readAllCoreRReports,
  replaceAllCoreRReports,
} from '@/features/backtests/core-r-judgment';
import {
  loadCoreRSchedulerPrefs,
  saveCoreRSchedulerPrefs,
  type CoreRSchedulerPrefs,
} from '@/features/backtests/core-r-scheduler';
import {
  type CoreRReviewQueueItem,
  useCoreRReviewQueueStore,
} from '@/stores/core-r-review-queue-store';
import { getActiveAccountId } from '@/stores/active-account-store';

let syncTimer: ReturnType<typeof setTimeout> | null = null;
const hydratedAccounts = new Set<string>();
let pushWired = false;

function asQueue(raw: unknown): CoreRReviewQueueItem[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((x): x is CoreRReviewQueueItem => !!x && typeof x === 'object');
}

function asReports(raw: unknown): Record<string, CoreRReport> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out: Record<string, CoreRReport> = {};
  for (const [listId, rec] of Object.entries(raw as Record<string, unknown>)) {
    if (!rec || typeof rec !== 'object') continue;
    const r = rec as CoreRReport;
    if (r.engine === CORE_R_ENGINE && r.listId) out[listId] = r;
  }
  return out;
}

function asScheduler(raw: unknown): CoreRSchedulerPrefs | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const p = raw as Partial<CoreRSchedulerPrefs>;
  const interval = Number(p.intervalMinutes);
  return {
    enabled: Boolean(p.enabled),
    intervalMinutes:
      Number.isFinite(interval) && interval >= 5 ? Math.min(24 * 60, interval) : 60,
    lastTickAt: typeof p.lastTickAt === 'string' ? p.lastTickAt : null,
    listId: typeof p.listId === 'string' && p.listId ? p.listId : null,
    scope: p.scope === 'monitor' ? 'monitor' : 'shell',
  };
}

function localBundle() {
  return {
    queue: useCoreRReviewQueueStore.getState().items as unknown as Array<
      Record<string, unknown>
    >,
    reports: readAllCoreRReports() as unknown as Record<string, unknown>,
    scheduler: loadCoreRSchedulerPrefs() as unknown as Record<string, unknown>,
  };
}

/** Pull BD → localStorage (BD gana). */
export async function hydrateCoreRFromServer(accountId: string): Promise<void> {
  if (!accountId) return;
  try {
    const res = await api.getAccountCoreR(accountId);
    const data = res.data;
    useCoreRReviewQueueStore.setState({ items: asQueue(data.queue) });
    replaceAllCoreRReports(asReports(data.reports));
    const sched = asScheduler(data.scheduler);
    if (sched) saveCoreRSchedulerPrefs(sched, { skipPush: true });
    hydratedAccounts.add(accountId);
  } catch {
    // Offline / API down: keep local cache.
  }
}

export async function pushCoreRToServer(accountId: string): Promise<void> {
  if (!accountId) return;
  try {
    await api.syncAccountCoreR(accountId, localBundle());
  } catch {
    // Retry on next write / hydrate.
  }
}

export function scheduleCoreRPush(accountId?: string | null): void {
  const id = accountId ?? getActiveAccountId();
  if (!id) return;
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    void pushCoreRToServer(id);
  }, 450);
}

export async function ensureCoreRHydrated(accountId: string): Promise<void> {
  if (!accountId || hydratedAccounts.has(accountId)) return;
  const localItems = useCoreRReviewQueueStore.getState().items.length;
  const localReports = Object.keys(readAllCoreRReports()).length;
  try {
    const res = await api.getAccountCoreR(accountId);
    const remoteEmpty =
      (res.data.queue?.length ?? 0) === 0 &&
      Object.keys(res.data.reports ?? {}).length === 0;
    if (remoteEmpty && (localItems > 0 || localReports > 0)) {
      await pushCoreRToServer(accountId);
    }
  } catch {
    // ignore
  }
  await hydrateCoreRFromServer(accountId);
}

/** Wire mutaciones locales → push (una vez). */
export function wireCoreRPushSubscriptions(): void {
  if (pushWired || typeof window === 'undefined') return;
  pushWired = true;
  useCoreRReviewQueueStore.subscribe(() => {
    scheduleCoreRPush();
  });
}
