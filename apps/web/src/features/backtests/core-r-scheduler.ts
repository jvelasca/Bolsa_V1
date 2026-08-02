/**
 * CORE-R scheduler — prefs + tick ejecutable desde Monitor o PlatformShell.
 *
 * v1.2 lite: solo con Monitor abierto.
 * v1.4 shell: ticks mientras la app está abierta (`CoreRSchedulerHost`).
 * v1.6: toast al encolar (host escucha `CORE_R_SCHEDULER_EVENT`).
 * No lanza Lista AUTO ni pisa TOP. Cola sigue en localStorage (≠ cron multi-dispositivo).
 */

export const CORE_R_SCHEDULER_KEY = 'bolsa-core-r-scheduler-v1';

export type CoreRSchedulerPrefs = {
  enabled: boolean;
  /** Minutos entre ticks (mín. 5). */
  intervalMinutes: number;
  lastTickAt: string | null;
  /** Lista a re-encolar (la fija el Monitor al activar). */
  listId: string | null;
  /**
   * `monitor` = solo mientras el panel Monitor está montado (legacy).
   * `shell` = PlatformShell (app abierta).
   */
  scope: 'monitor' | 'shell';
};

const DEFAULT: CoreRSchedulerPrefs = {
  enabled: false,
  intervalMinutes: 60,
  lastTickAt: null,
  listId: null,
  scope: 'shell',
};

export function loadCoreRSchedulerPrefs(): CoreRSchedulerPrefs {
  try {
    const raw = localStorage.getItem(CORE_R_SCHEDULER_KEY);
    if (!raw) return { ...DEFAULT };
    const parsed = JSON.parse(raw) as Partial<CoreRSchedulerPrefs>;
    const interval = Number(parsed.intervalMinutes);
    const scope = parsed.scope === 'monitor' ? 'monitor' : 'shell';
    return {
      enabled: Boolean(parsed.enabled),
      intervalMinutes:
        Number.isFinite(interval) && interval >= 5 ? Math.min(24 * 60, interval) : 60,
      lastTickAt: typeof parsed.lastTickAt === 'string' ? parsed.lastTickAt : null,
      listId: typeof parsed.listId === 'string' && parsed.listId ? parsed.listId : null,
      scope,
    };
  } catch {
    return { ...DEFAULT };
  }
}

export function saveCoreRSchedulerPrefs(
  prefs: CoreRSchedulerPrefs,
  opts?: { skipPush?: boolean },
): void {
  try {
    localStorage.setItem(CORE_R_SCHEDULER_KEY, JSON.stringify(prefs));
  } catch {
    // quota
  }
  if (!opts?.skipPush) {
    void import('@/features/backtests/core-r-sync').then((m) => m.scheduleCoreRPush());
  }
}

export function markCoreRSchedulerTick(prefs: CoreRSchedulerPrefs): CoreRSchedulerPrefs {
  const next = { ...prefs, lastTickAt: new Date().toISOString() };
  saveCoreRSchedulerPrefs(next);
  return next;
}

export function coreRSchedulerDue(prefs: CoreRSchedulerPrefs, nowMs = Date.now()): boolean {
  if (!prefs.enabled) return false;
  if (!prefs.lastTickAt) return true;
  const last = Date.parse(prefs.lastTickAt);
  if (!Number.isFinite(last)) return true;
  return nowMs - last >= prefs.intervalMinutes * 60_000;
}

export const CORE_R_SCHEDULER_EVENT = 'bolsa-core-r-scheduler-tick';

export type CoreRSchedulerTickDetail = {
  listId: string;
  added: number;
  at: string;
};

/** Notifica a Monitor / UI tras un tick shell. */
export function emitCoreRSchedulerTick(detail: CoreRSchedulerTickDetail): void {
  try {
    window.dispatchEvent(new CustomEvent(CORE_R_SCHEDULER_EVENT, { detail }));
  } catch {
    // SSR / tests
  }
}
