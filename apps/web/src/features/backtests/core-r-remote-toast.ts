/**
 * CORE-R v1.12 — toast remoto multi-dispositivo.
 *
 * El cron servidor (u otro cliente) escribe `lastRemoteEnqueueAt` /
 * `lastRemoteEnqueueAdded` en el blob scheduler. Este módulo decide si
 * hidratar → toast, sin ruido si ya vimos la señal.
 */

export const CORE_R_LAST_SEEN_REMOTE_ENQUEUE_KEY =
  'bolsa-core-r-last-seen-remote-enqueue';

export type CoreRRemoteEnqueueSignal = {
  lastRemoteEnqueueAt: string | null;
  lastRemoteEnqueueAdded: number;
};

export function loadLastSeenRemoteEnqueueAt(): string | null {
  try {
    const v = localStorage.getItem(CORE_R_LAST_SEEN_REMOTE_ENQUEUE_KEY);
    return typeof v === 'string' && v.trim() ? v : null;
  } catch {
    return null;
  }
}

export function markCoreRRemoteEnqueueSeen(at: string | null | undefined): void {
  if (!at || typeof at !== 'string') return;
  try {
    localStorage.setItem(CORE_R_LAST_SEEN_REMOTE_ENQUEUE_KEY, at);
  } catch {
    // quota
  }
}

/**
 * ¿Hay una señal de encolado remoto más nueva que `lastSeen`?
 * Pure: no toca storage.
 */
export function shouldToastRemoteEnqueue(
  signal: CoreRRemoteEnqueueSignal,
  lastSeenAt: string | null,
): { shouldToast: boolean; added: number; at: string | null } {
  const at =
    typeof signal.lastRemoteEnqueueAt === 'string' && signal.lastRemoteEnqueueAt.trim()
      ? signal.lastRemoteEnqueueAt
      : null;
  const added = Math.max(0, Math.floor(Number(signal.lastRemoteEnqueueAdded) || 0));
  if (!at || added <= 0) {
    return { shouldToast: false, added: 0, at };
  }
  if (!lastSeenAt) {
    return { shouldToast: true, added, at };
  }
  const remoteMs = Date.parse(at);
  const seenMs = Date.parse(lastSeenAt);
  if (!Number.isFinite(remoteMs)) {
    return { shouldToast: false, added: 0, at };
  }
  if (!Number.isFinite(seenMs) || remoteMs > seenMs) {
    return { shouldToast: true, added, at };
  }
  return { shouldToast: false, added, at };
}

export function parseRemoteEnqueueSignal(
  scheduler: Record<string, unknown> | null | undefined,
): CoreRRemoteEnqueueSignal {
  if (!scheduler || typeof scheduler !== 'object') {
    return { lastRemoteEnqueueAt: null, lastRemoteEnqueueAdded: 0 };
  }
  const at = scheduler.lastRemoteEnqueueAt;
  const added = Number(scheduler.lastRemoteEnqueueAdded);
  return {
    lastRemoteEnqueueAt: typeof at === 'string' && at.trim() ? at : null,
    lastRemoteEnqueueAdded: Number.isFinite(added) ? added : 0,
  };
}
