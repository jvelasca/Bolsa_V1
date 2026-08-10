/**
 * CORE-R scheduler — prefs + tick ejecutable desde Monitor o PlatformShell.
 *
 * v1.2 lite: solo con Monitor abierto.
 * v1.4 shell: ticks mientras la app está abierta (`CoreRSchedulerHost`).
 * v1.6: toast al encolar (host escucha `CORE_R_SCHEDULER_EVENT`).
 * v1.12: `lastRemoteEnqueue*` para toast multi-dispositivo tras cron/BD.
 * v1.13: Auto-sync prefería «Estudio personal».
 * ADR-024: prefiere lista API canónica «Estudio» (`estudioListId`).
 * No lanza Lista AUTO ni pisa TOP (eso lo arma Supervisión ON).
 */

export const CORE_R_SCHEDULER_KEY = "bolsa-core-r-scheduler-v1";

/** Presets de cadencia (minutos) en UI Monitor. */
export const CORE_R_SCHEDULER_INTERVAL_PRESETS = [
  15, 30, 60, 120, 240, 1440,
] as const;

export type CoreRSchedulerPrefs = {
  enabled: boolean;
  /** Minutos entre ticks (mín. 5). */
  intervalMinutes: number;
  lastTickAt: string | null;
  /**
   * Lista a re-encolar.
   * Al activar Auto-sync: «Estudio» canónica si existe; si no, lista del Monitor.
   */
  listId: string | null;
  /**
   * `monitor` = solo mientras el panel Monitor está montado (legacy).
   * `shell` = PlatformShell (app abierta).
   */
  scope: "monitor" | "shell";
  /** Origen del último tick que escribió el blob (shell | server_cron). */
  lastTickSource?: "shell" | "server_cron" | null;
  /** Señal multi-dispositivo: último encolado remoto (ISO). */
  lastRemoteEnqueueAt?: string | null;
  lastRemoteEnqueueAdded?: number;
};

const DEFAULT: CoreRSchedulerPrefs = {
  enabled: false,
  intervalMinutes: 60,
  lastTickAt: null,
  listId: null,
  scope: "shell",
  lastTickSource: null,
  lastRemoteEnqueueAt: null,
  lastRemoteEnqueueAdded: 0,
};

function normalizePrefs(
  parsed: Partial<CoreRSchedulerPrefs>,
): CoreRSchedulerPrefs {
  const interval = Number(parsed.intervalMinutes);
  const scope = parsed.scope === "monitor" ? "monitor" : "shell";
  const source =
    parsed.lastTickSource === "server_cron" || parsed.lastTickSource === "shell"
      ? parsed.lastTickSource
      : null;
  const remoteAdded = Number(parsed.lastRemoteEnqueueAdded);
  return {
    enabled: Boolean(parsed.enabled),
    intervalMinutes:
      Number.isFinite(interval) && interval >= 5
        ? Math.min(24 * 60, interval)
        : 60,
    lastTickAt:
      typeof parsed.lastTickAt === "string" ? parsed.lastTickAt : null,
    listId:
      typeof parsed.listId === "string" && parsed.listId ? parsed.listId : null,
    scope,
    lastTickSource: source,
    lastRemoteEnqueueAt:
      typeof parsed.lastRemoteEnqueueAt === "string" &&
      parsed.lastRemoteEnqueueAt
        ? parsed.lastRemoteEnqueueAt
        : null,
    lastRemoteEnqueueAdded: Number.isFinite(remoteAdded)
      ? Math.max(0, remoteAdded)
      : 0,
  };
}

export function loadCoreRSchedulerPrefs(): CoreRSchedulerPrefs {
  try {
    const raw = localStorage.getItem(CORE_R_SCHEDULER_KEY);
    if (!raw) return { ...DEFAULT };
    return normalizePrefs(JSON.parse(raw) as Partial<CoreRSchedulerPrefs>);
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
    void import("@/features/backtests/core-r-sync").then((m) =>
      m.scheduleCoreRPush(),
    );
  }
}

export function markCoreRSchedulerTick(
  prefs: CoreRSchedulerPrefs,
): CoreRSchedulerPrefs {
  const next = { ...prefs, lastTickAt: new Date().toISOString() };
  saveCoreRSchedulerPrefs(next);
  return next;
}

export function coreRSchedulerDue(
  prefs: CoreRSchedulerPrefs,
  nowMs = Date.now(),
): boolean {
  if (!prefs.enabled) return false;
  if (!prefs.lastTickAt) return true;
  const last = Date.parse(prefs.lastTickAt);
  if (!Number.isFinite(last)) return true;
  return nowMs - last >= prefs.intervalMinutes * 60_000;
}

/** Normaliza minutos al rango válido del scheduler. */
export function clampCoreRSchedulerInterval(minutes: number): number {
  if (!Number.isFinite(minutes)) return 60;
  return Math.min(24 * 60, Math.max(5, Math.round(minutes)));
}

/**
 * Lista a fijar al activar Auto-sync: Estudio canónica > Monitor > prefs previas.
 */
export function resolveCoreRSchedulerListId(opts: {
  estudioListId?: string | null;
  /** @deprecated usar estudioListId */
  estudioPersonalListId?: string | null;
  monitorListId?: string | null;
  previousListId?: string | null;
}): string | null {
  return (
    opts.estudioListId ||
    opts.estudioPersonalListId ||
    opts.monitorListId ||
    opts.previousListId ||
    null
  );
}

export const CORE_R_SCHEDULER_EVENT = "bolsa-core-r-scheduler-tick";

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
