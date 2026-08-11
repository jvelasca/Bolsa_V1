/**
 * Supervisión Estudio (ADR-024) — prefs + eventos + unsubscribe + cadencias 3 capas.
 *
 * Capas (cuando Supervisión ON) — pensadas para vela diaria al cierre:
 * - Vigilia: CORE-R (juicios / PnL paper) — default 1 día (no cada hora).
 * - Frescura: pase Lista AUTO + skip_fresh — default 1 día tras cierre.
 * - Redescubrimiento: embudo forceRescan + presupuesto — semanas/meses.
 *
 * Quitar de Estudio → dismiss colas + excluir de campaña en curso.
 */

import { ESTUDIO_LIST_ID } from "@bolsa/shared";
import {
  loadCoreRSchedulerPrefs,
  saveCoreRSchedulerPrefs,
  clampCoreRSchedulerInterval,
} from "@/features/backtests/core-r-scheduler";
import { useCoreRReviewQueueStore } from "@/stores/core-r-review-queue-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";

export const ESTUDIO_SUPERVISION_KEY = "bolsa-estudio-supervision-v1";
export const ESTUDIO_SUPERVISION_EVENT = "bolsa-estudio-supervision-changed";
export const ESTUDIO_UNSUBSCRIBE_EVENT = "bolsa-estudio-unsubscribe";
/** Tick programado capa media / lenta (lo consume BacktestsPage). */
export const ESTUDIO_LANE_TICK_EVENT = "bolsa-estudio-lane-tick";

/**
 * Presets vigilia (minutos; tope CORE-R = 24 h). En vela 1d al cierre el default
 * es 1 día; 4h/12h solo si quieres revisiones intra-sesión (p. ej. paper abierto).
 */
export const ESTUDIO_VIGILANCE_PRESETS = [240, 720, 1_440] as const;

/** Presets frescura Lab (minutos) — pase con skip_fresh. */
export const ESTUDIO_FRESHNESS_PRESETS = [
  1_440, // 1 d (nuevo cierre)
  3 * 1_440,
  7 * 1_440,
  14 * 1_440,
  30 * 1_440,
] as const;

/** Presets rediscubrimiento (minutos). 0 = desactivado. */
export const ESTUDIO_REDISCOVER_PRESETS = [
  0,
  7 * 1_440,
  14 * 1_440,
  30 * 1_440,
  90 * 1_440,
] as const;

/** v2 = defaults vela diaria (vigilia/frescura 1d; ya no 60 min / 7d). */
export const ESTUDIO_SUPERVISION_SCHEMA = 2;

export type EstudioSupervisionPrefs = {
  schemaVersion: number;
  enabled: boolean;
  /**
   * @deprecated Usar `vigilanceMinutes`. Se mantiene al leer v1 antigua.
   */
  intervalMinutes: number;
  /** Capa rápida — CORE-R (minutos). */
  vigilanceMinutes: number;
  /** Capa media — Lista AUTO + skip_fresh (minutos). */
  freshnessMinutes: number;
  /** Capa lenta — rediscubrimiento (minutos). 0 = off. */
  rediscoverMinutes: number;
  /** Máx. valores por tick de rediscubrimiento. */
  rediscoverBudgetPerTick: number;
  /** Cursor rotatorio en la lista Estudio para la capa lenta. */
  rediscoverCursor: number;
  lastFreshnessTickAt: string | null;
  lastRediscoverTickAt: string | null;
};

const DEFAULT: EstudioSupervisionPrefs = {
  schemaVersion: ESTUDIO_SUPERVISION_SCHEMA,
  enabled: false,
  intervalMinutes: 1_440,
  vigilanceMinutes: 1_440,
  freshnessMinutes: 1_440,
  rediscoverMinutes: 30 * 1_440,
  rediscoverBudgetPerTick: 5,
  rediscoverCursor: 0,
  lastFreshnessTickAt: null,
  lastRediscoverTickAt: null,
};

export type EstudioSupervisionEventDetail = {
  enabled: boolean;
  listId: string;
  intervalMinutes: number;
  vigilanceMinutes: number;
  freshnessMinutes: number;
  rediscoverMinutes: number;
};

export type EstudioUnsubscribeEventDetail = {
  instrumentIds: string[];
};

export type EstudioLane = "freshness" | "rediscover";

export type EstudioLaneTickDetail = {
  listId: string;
  lane: EstudioLane;
  /** Ignorar skip_fresh (solo rediscover). */
  forceRescan: boolean;
  /** Confirmación de tandas automática (sin diálogo). */
  skipConfirm: boolean;
  /** Subconjunto de ids (presupuesto rediscover); vacío = lista completa. */
  instrumentIds: string[] | null;
  at: string;
};

function clampPositiveMinutes(
  value: number,
  fallback: number,
  max = 90 * 1_440,
): number {
  if (!Number.isFinite(value) || value < 1) return fallback;
  return Math.min(max, Math.round(value));
}

function clampRediscoverMinutes(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(90 * 1_440, Math.round(value));
}

export function normalizeEstudioSupervisionPrefs(
  parsed: Partial<EstudioSupervisionPrefs>,
): EstudioSupervisionPrefs {
  const schemaVersion = Number(parsed.schemaVersion) || 1;
  const legacyInterval = Number(parsed.intervalMinutes);
  const vigilanceRaw = Number(parsed.vigilanceMinutes);
  let vigilanceMinutes = clampCoreRSchedulerInterval(
    Number.isFinite(vigilanceRaw) && vigilanceRaw > 0
      ? vigilanceRaw
      : Number.isFinite(legacyInterval) && legacyInterval > 0
        ? legacyInterval
        : DEFAULT.vigilanceMinutes,
  );
  let freshnessMinutes = clampPositiveMinutes(
    Number(parsed.freshnessMinutes),
    DEFAULT.freshnessMinutes,
  );
  // v1 → v2: defaults horarios no encajan con vela 1d al cierre.
  if (schemaVersion < 2) {
    if (vigilanceMinutes === 60) vigilanceMinutes = DEFAULT.vigilanceMinutes;
    if (
      !Number.isFinite(Number(parsed.freshnessMinutes)) ||
      Number(parsed.freshnessMinutes) === 7 * 1_440
    ) {
      freshnessMinutes = DEFAULT.freshnessMinutes;
    }
  }
  const rediscoverMinutes = clampRediscoverMinutes(
    Number(parsed.rediscoverMinutes ?? DEFAULT.rediscoverMinutes),
  );
  const budget = Number(parsed.rediscoverBudgetPerTick);
  const cursor = Number(parsed.rediscoverCursor);

  return {
    schemaVersion: ESTUDIO_SUPERVISION_SCHEMA,
    enabled: Boolean(parsed.enabled),
    intervalMinutes: vigilanceMinutes,
    vigilanceMinutes,
    freshnessMinutes,
    rediscoverMinutes,
    rediscoverBudgetPerTick:
      Number.isFinite(budget) && budget >= 1
        ? Math.min(40, Math.round(budget))
        : 5,
    rediscoverCursor:
      Number.isFinite(cursor) && cursor >= 0 ? Math.floor(cursor) : 0,
    lastFreshnessTickAt:
      typeof parsed.lastFreshnessTickAt === "string"
        ? parsed.lastFreshnessTickAt
        : null,
    lastRediscoverTickAt:
      typeof parsed.lastRediscoverTickAt === "string"
        ? parsed.lastRediscoverTickAt
        : null,
  };
}

export function loadEstudioSupervisionPrefs(): EstudioSupervisionPrefs {
  try {
    const raw = localStorage.getItem(ESTUDIO_SUPERVISION_KEY);
    if (!raw) return { ...DEFAULT };
    const parsed = JSON.parse(raw) as Partial<EstudioSupervisionPrefs>;
    const next = normalizeEstudioSupervisionPrefs(parsed);
    // Persistir migración v2 si hacía falta.
    if ((parsed.schemaVersion ?? 1) < 2) {
      saveEstudioSupervisionPrefs(next);
    }
    return next;
  } catch {
    return { ...DEFAULT };
  }
}

export function saveEstudioSupervisionPrefs(
  prefs: EstudioSupervisionPrefs,
): void {
  try {
    localStorage.setItem(ESTUDIO_SUPERVISION_KEY, JSON.stringify(prefs));
  } catch {
    // quota
  }
}

export function emitEstudioSupervisionChanged(
  detail: EstudioSupervisionEventDetail,
): void {
  try {
    window.dispatchEvent(
      new CustomEvent(ESTUDIO_SUPERVISION_EVENT, { detail }),
    );
  } catch {
    // SSR / tests
  }
}

export function emitEstudioUnsubscribe(instrumentIds: string[]): void {
  if (instrumentIds.length === 0) return;
  try {
    window.dispatchEvent(
      new CustomEvent(ESTUDIO_UNSUBSCRIBE_EVENT, {
        detail: { instrumentIds } satisfies EstudioUnsubscribeEventDetail,
      }),
    );
  } catch {
    // SSR / tests
  }
}

/** Último tick pendiente si BacktestsPage aún no estaba montado (keep-alive). */
let pendingEstudioLaneTick: EstudioLaneTickDetail | null = null;

export function emitEstudioLaneTick(detail: EstudioLaneTickDetail): void {
  pendingEstudioLaneTick = detail;
  try {
    window.dispatchEvent(new CustomEvent(ESTUDIO_LANE_TICK_EVENT, { detail }));
  } catch {
    // SSR / tests
  }
}

/** Consume tick encolado (p. ej. al montar BacktestsPage tras Actualizar/alta). */
export function takePendingEstudioLaneTick(): EstudioLaneTickDetail | null {
  const next = pendingEstudioLaneTick;
  pendingEstudioLaneTick = null;
  return next;
}

/** Marca el tick como entregado (listener vivo recibió el evento). */
export function clearPendingEstudioLaneTick(): void {
  pendingEstudioLaneTick = null;
}

function laneDue(
  lastAt: string | null,
  intervalMinutes: number,
  nowMs: number,
): boolean {
  if (intervalMinutes <= 0) return false;
  if (!lastAt) return true;
  const last = Date.parse(lastAt);
  if (!Number.isFinite(last)) return true;
  return nowMs - last >= intervalMinutes * 60_000;
}

export function estudioFreshnessDue(
  prefs: EstudioSupervisionPrefs,
  nowMs = Date.now(),
): boolean {
  if (!prefs.enabled) return false;
  return laneDue(prefs.lastFreshnessTickAt, prefs.freshnessMinutes, nowMs);
}

export function estudioRediscoverDue(
  prefs: EstudioSupervisionPrefs,
  nowMs = Date.now(),
): boolean {
  if (!prefs.enabled) return false;
  if (prefs.rediscoverMinutes <= 0) return false;
  return laneDue(prefs.lastRediscoverTickAt, prefs.rediscoverMinutes, nowMs);
}

/** Toma un slice rotatorio de la lista para el presupuesto de rediscubrimiento. */
export function sliceRediscoverBudget(
  instrumentIds: readonly string[],
  cursor: number,
  budget: number,
): { ids: string[]; nextCursor: number } {
  if (instrumentIds.length === 0 || budget <= 0) {
    return { ids: [], nextCursor: 0 };
  }
  const start =
    ((cursor % instrumentIds.length) + instrumentIds.length) %
    instrumentIds.length;
  const ids: string[] = [];
  for (let i = 0; i < Math.min(budget, instrumentIds.length); i += 1) {
    ids.push(instrumentIds[(start + i) % instrumentIds.length]!);
  }
  const nextCursor = (start + ids.length) % instrumentIds.length;
  return { ids, nextCursor };
}

export function markEstudioFreshnessTick(
  prefs: EstudioSupervisionPrefs,
  at = new Date().toISOString(),
): EstudioSupervisionPrefs {
  const next = { ...prefs, lastFreshnessTickAt: at };
  saveEstudioSupervisionPrefs(next);
  return next;
}

export function markEstudioRediscoverTick(
  prefs: EstudioSupervisionPrefs,
  opts?: { cursor?: number; at?: string },
): EstudioSupervisionPrefs {
  const next = {
    ...prefs,
    lastRediscoverTickAt: opts?.at ?? new Date().toISOString(),
    rediscoverCursor:
      opts?.cursor !== undefined
        ? Math.max(0, Math.floor(opts.cursor))
        : prefs.rediscoverCursor,
  };
  saveEstudioSupervisionPrefs(next);
  return next;
}

export type PatchEstudioSupervision = Partial<
  Pick<
    EstudioSupervisionPrefs,
    | "enabled"
    | "vigilanceMinutes"
    | "freshnessMinutes"
    | "rediscoverMinutes"
    | "rediscoverBudgetPerTick"
  >
>;

/**
 * Actualiza prefs de supervisión; si cambia vigilia/enabled, sincroniza CORE-R.
 */
export function patchEstudioSupervision(
  patch: PatchEstudioSupervision,
  opts?: { listId?: string | null },
): EstudioSupervisionPrefs {
  const prev = loadEstudioSupervisionPrefs();
  let next = normalizeEstudioSupervisionPrefs({ ...prev, ...patch });
  // Al armar: el arranque inicial lo hace BacktestsPage; no dispares frescura al instante.
  if (next.enabled && !prev.enabled) {
    const at = new Date().toISOString();
    next = {
      ...next,
      lastFreshnessTickAt: next.lastFreshnessTickAt ?? at,
    };
  }
  saveEstudioSupervisionPrefs(next);

  const listId = opts?.listId || ESTUDIO_LIST_ID;
  const sched = loadCoreRSchedulerPrefs();
  saveCoreRSchedulerPrefs({
    ...sched,
    enabled: next.enabled,
    intervalMinutes: next.vigilanceMinutes,
    listId: next.enabled ? listId : sched.listId,
    scope: "shell",
  });

  emitEstudioSupervisionChanged({
    enabled: next.enabled,
    listId,
    intervalMinutes: next.vigilanceMinutes,
    vigilanceMinutes: next.vigilanceMinutes,
    freshnessMinutes: next.freshnessMinutes,
    rediscoverMinutes: next.rediscoverMinutes,
  });
  return next;
}

/**
 * Activa/desactiva supervisión: prefs + CORE-R Auto-sync + evento para Lista AUTO.
 */
export function setEstudioSupervisionEnabled(
  enabled: boolean,
  opts?: {
    listId?: string | null;
    intervalMinutes?: number;
    vigilanceMinutes?: number;
    freshnessMinutes?: number;
    rediscoverMinutes?: number;
    rediscoverBudgetPerTick?: number;
  },
): EstudioSupervisionPrefs {
  return patchEstudioSupervision(
    {
      enabled,
      vigilanceMinutes: opts?.vigilanceMinutes ?? opts?.intervalMinutes,
      freshnessMinutes: opts?.freshnessMinutes,
      rediscoverMinutes: opts?.rediscoverMinutes,
      rediscoverBudgetPerTick: opts?.rediscoverBudgetPerTick,
    },
    { listId: opts?.listId },
  );
}

/**
 * Al quitar de Estudio: dismiss CORE-R + F3; notifica Lista AUTO para excluir.
 * No cierra mandato ni posiciones.
 */
export function unsubscribeInstrumentFromSupervision(
  instrumentIds: ReadonlyArray<string>,
): void {
  const ids = [...new Set(instrumentIds.filter(Boolean))];
  if (ids.length === 0) return;

  const coreR = useCoreRReviewQueueStore.getState();
  for (const id of ids) coreR.dismissOpenForInstrument(id);

  const f3 = useSupervisedF3QueueStore.getState();
  for (const id of ids) f3.removeForInstrument(id);

  emitEstudioUnsubscribe(ids);
}

export function formatEstudioCadenceMinutes(minutes: number): string {
  if (minutes <= 0) return "off";
  if (minutes >= 1_440 && minutes % 1_440 === 0) {
    const days = minutes / 1_440;
    return days === 1 ? "1 día" : `${days} días`;
  }
  if (minutes >= 60 && minutes % 60 === 0) {
    const hours = minutes / 60;
    return hours === 1 ? "1 h" : `${hours} h`;
  }
  return `${minutes} min`;
}
