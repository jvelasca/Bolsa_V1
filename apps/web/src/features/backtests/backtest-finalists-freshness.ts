/**
 * Frescura de Finalistas / Lista AUTO — omitir embudo si la entrada no cambió.
 *
 * Persistencia (sobrevive reinicio app + servidor):
 * - DB: `coachFacts.freshness` en InstrumentStrategyTop
 * - localStorage: `bolsa-finalists-freshness-v1` (por instrumentId|TF)
 *
 * Política (v1.3 · 2026-08-01):
 * - Omitir **solo si hay Finalistas reales** (`hasSlots`) y la huella coincide.
 * - Sin TOP / slots vacíos → **siempre analizar** (borrar Finalistas invalida el omitir).
 * - Invalidación real: periodo/costes, lote, perfil, prefs.
 * - **Histéresis lastBar:** ±N días de calendario (1d → 5) ≠ re-embudo; stamp original no se desliza.
 * - Forzar: «Reevaluar resto» / `forceRescan`.
 *
 * @see docs/engineering/product-pause-audit-2026-07-30.md §2.3
 * @see docs/engineering/list-auto-ops-2026-07-29.md § Frescura
 */

export const FINALISTS_FRESHNESS_ENGINE = 'finalists-fresh-v1';
export const FINALISTS_FRESHNESS_STORAGE_KEY = 'bolsa-finalists-freshness-v1';

/** Días de calendario de holgura en `lastBarDate` por timeframe (histéresis v1.3). */
export const FINALISTS_LAST_BAR_SLACK_DAYS: Record<string, number> = {
  '1d': 5,
  '1w': 14,
  '1h': 2,
  '5m': 1,
  '15m': 1,
  '30m': 1,
  '4h': 2,
};

export const FINALISTS_LAST_BAR_SLACK_DEFAULT = 5;

export type FinalistsFreshnessStamp = {
  engine: string;
  inputFingerprint: string;
  lastSearchAt: string;
  lastLabAt?: string | null;
};

export type LocalFreshnessEntry = {
  fingerprint: string;
  lastSearchAt: string;
  timeframe: string;
};

export type SkipFinalistsDecision = {
  skip: boolean;
  reason: string;
  adoptFingerprint?: boolean;
};

function normalizeDatePart(value: string | null | undefined): string {
  if (!value) return '';
  const s = String(value).trim();
  return s.length >= 10 ? s.slice(0, 10) : s;
}

function normalizeScalar(value: string | number | null | undefined): string {
  if (value == null || value === '') return '';
  const n = typeof value === 'number' ? value : Number(String(value).trim());
  if (Number.isFinite(n) && String(value).trim() !== '') return String(n);
  return String(value);
}

/** Índice de `lastBarDate` en la huella pipe-separated (documentado). */
const FP_LAST_BAR_INDEX = 9;
const FP_TIMEFRAME_INDEX = 2;

export function parseFinalistsFingerprintParts(fingerprint: string): string[] {
  return fingerprint.split('|');
}

export function lastBarSlackDaysForTimeframe(timeframe: string): number {
  const tf = (timeframe || '1d').trim().toLowerCase();
  return FINALISTS_LAST_BAR_SLACK_DAYS[tf] ?? FINALISTS_LAST_BAR_SLACK_DEFAULT;
}

/**
 * Diferencia absoluta en días de calendario entre dos YYYY-MM-DD.
 * NaN si falta alguna.
 */
export function calendarDaysBetween(a: string, b: string): number {
  const da = normalizeDatePart(a);
  const db = normalizeDatePart(b);
  if (!da || !db) return Number.NaN;
  const ta = Date.parse(`${da}T00:00:00Z`);
  const tb = Date.parse(`${db}T00:00:00Z`);
  if (!Number.isFinite(ta) || !Number.isFinite(tb)) return Number.NaN;
  return Math.abs(Math.round((tb - ta) / 86_400_000));
}

/**
 * Compara huellas: exacta, solo lastBar dentro de slack, o mismatch.
 * El stamp original **no** se actualiza en histéresis (ventana fija desde stamp).
 */
export function compareFinalistsFingerprints(
  candidate: string,
  current: string,
  slackDays?: number,
): 'exact' | 'bar_hysteresis' | 'mismatch' {
  if (candidate === current) return 'exact';
  const a = parseFinalistsFingerprintParts(candidate);
  const b = parseFinalistsFingerprintParts(current);
  if (a.length !== b.length || a.length <= FP_LAST_BAR_INDEX) return 'mismatch';
  for (let i = 0; i < a.length; i += 1) {
    if (i === FP_LAST_BAR_INDEX) continue;
    if (a[i] !== b[i]) return 'mismatch';
  }
  const tf = b[FP_TIMEFRAME_INDEX] || a[FP_TIMEFRAME_INDEX] || '1d';
  const slack = slackDays ?? lastBarSlackDaysForTimeframe(tf);
  const days = calendarDaysBetween(a[FP_LAST_BAR_INDEX] ?? '', b[FP_LAST_BAR_INDEX] ?? '');
  if (!Number.isFinite(days)) return 'mismatch';
  if (days <= slack) return 'bar_hysteresis';
  return 'mismatch';
}

export function buildFinalistsInputFingerprint(opts: {
  instrumentId: string;
  timeframe: string;
  periodPreset: string;
  dateFrom?: string;
  dateTo?: string;
  initialCash: string | number;
  commissionBps: string | number;
  slippageBps: string | number;
  lastBarDate?: string | null;
  loteRowIds: readonly string[];
  profilePolicyVersion?: string | null;
  engine?: string;
}): string {
  const ids = [...new Set(opts.loteRowIds.filter(Boolean))].sort().join(',');
  const engine = opts.engine ?? FINALISTS_FRESHNESS_ENGINE;
  return [
    engine,
    opts.instrumentId,
    opts.timeframe,
    opts.periodPreset,
    normalizeDatePart(opts.dateFrom),
    normalizeDatePart(opts.dateTo),
    normalizeScalar(opts.initialCash),
    normalizeScalar(opts.commissionBps),
    normalizeScalar(opts.slippageBps),
    normalizeDatePart(opts.lastBarDate),
    opts.profilePolicyVersion ?? '',
    `lote:${ids}`,
  ].join('|');
}

export function readFinalistsFreshness(
  coachFacts: Record<string, unknown> | null | undefined,
): FinalistsFreshnessStamp | null {
  if (!coachFacts || typeof coachFacts !== 'object') return null;
  const raw = coachFacts.freshness;
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Partial<FinalistsFreshnessStamp>;
  if (typeof o.inputFingerprint !== 'string' || !o.inputFingerprint) return null;
  if (typeof o.lastSearchAt !== 'string' || !o.lastSearchAt) return null;
  return {
    engine: typeof o.engine === 'string' ? o.engine : FINALISTS_FRESHNESS_ENGINE,
    inputFingerprint: o.inputFingerprint,
    lastSearchAt: o.lastSearchAt,
    lastLabAt: typeof o.lastLabAt === 'string' ? o.lastLabAt : null,
  };
}

export function buildFinalistsFreshnessStamp(opts: {
  inputFingerprint: string;
  at?: string;
  lab?: boolean;
}): FinalistsFreshnessStamp {
  const at = opts.at ?? new Date().toISOString();
  return {
    engine: FINALISTS_FRESHNESS_ENGINE,
    inputFingerprint: opts.inputFingerprint,
    lastSearchAt: at,
    lastLabAt: opts.lab ? at : null,
  };
}

export function mergeFreshnessIntoCoachFacts(
  coachFacts: Record<string, unknown> | null | undefined,
  stamp: FinalistsFreshnessStamp,
): Record<string, unknown> {
  return {
    ...(coachFacts ?? {}),
    freshness: stamp,
  };
}

function localFreshnessKey(instrumentId: string, timeframe: string): string {
  return `${instrumentId}|${timeframe || '1d'}`;
}

/** Mapa completo instrumentId|TF → entry (para columna Procesos / timestamps). */
export function loadLocalFinalistsFreshnessMap(): Record<string, LocalFreshnessEntry> {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(FINALISTS_FRESHNESS_STORAGE_KEY);
    if (!raw) return {};
    const map = JSON.parse(raw) as Record<string, LocalFreshnessEntry>;
    return map && typeof map === 'object' ? map : {};
  } catch {
    return {};
  }
}

export function readLocalFreshnessFingerprint(
  instrumentId: string,
  timeframe: string,
): LocalFreshnessEntry | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const map = loadLocalFinalistsFreshnessMap();
    const entry = map[localFreshnessKey(instrumentId, timeframe)];
    if (!entry || typeof entry.fingerprint !== 'string' || !entry.fingerprint) return null;
    return {
      fingerprint: entry.fingerprint,
      lastSearchAt:
        typeof entry.lastSearchAt === 'string' ? entry.lastSearchAt : new Date().toISOString(),
      timeframe: entry.timeframe || timeframe,
    };
  } catch {
    return null;
  }
}

export function writeLocalFreshnessFingerprint(opts: {
  instrumentId: string;
  timeframe: string;
  fingerprint: string;
  at?: string;
}): void {
  if (typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(FINALISTS_FRESHNESS_STORAGE_KEY);
    const map = (raw ? JSON.parse(raw) : {}) as Record<string, LocalFreshnessEntry>;
    map[localFreshnessKey(opts.instrumentId, opts.timeframe)] = {
      fingerprint: opts.fingerprint,
      lastSearchAt: opts.at ?? new Date().toISOString(),
      timeframe: opts.timeframe || '1d',
    };
    localStorage.setItem(FINALISTS_FRESHNESS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore
  }
}

/** Invalida huella local (p. ej. tras borrar Finalistas / TOP). */
export function clearLocalFreshnessFingerprint(
  instrumentId: string,
  timeframe: string,
): void {
  if (typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(FINALISTS_FRESHNESS_STORAGE_KEY);
    if (!raw) return;
    const map = JSON.parse(raw) as Record<string, LocalFreshnessEntry>;
    delete map[localFreshnessKey(instrumentId, timeframe)];
    localStorage.setItem(FINALISTS_FRESHNESS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore
  }
}

function matchFingerprint(
  candidate: string | null | undefined,
  current: string,
): 'exact' | 'bar_hysteresis' | null {
  if (!candidate) return null;
  const cmp = compareFinalistsFingerprints(candidate, current);
  if (cmp === 'mismatch') return null;
  return cmp;
}

/**
 * ¿Omitir embudo?
 *
 * Orden: prefs → force → (sesión|local|DB) **solo con Finalistas (hasSlots)** → adoptar active.
 * Sin slots → no omitir (borrar TOP debe forzar reanálisis).
 * Histéresis lastBar (v1.3): omite con reason `bar_hysteresis` sin deslizar el stamp.
 */
export function shouldSkipFinalistsSearch(opts: {
  preferSkip: boolean;
  forceRescan?: boolean;
  topStatus?: string | null;
  evidenceLevel?: string | null;
  stored: FinalistsFreshnessStamp | null;
  currentFingerprint: string;
  memoryFingerprint?: string | null;
  localFingerprint?: string | null;
  /** true si el TOP tiene al menos 1 slot (Finalistas reales). */
  hasSlots?: boolean;
}): SkipFinalistsDecision {
  if (!opts.preferSkip) return { skip: false, reason: 'prefs_off' };
  if (opts.forceRescan) return { skip: false, reason: 'force' };

  const hasFinalistSlots = opts.hasSlots === true;

  // Sin Finalistas reales: no omitir (aunque quede huella local de un análisis previo).
  if (!hasFinalistSlots) {
    return { skip: false, reason: 'no_finalists_slots' };
  }

  const mem = matchFingerprint(opts.memoryFingerprint, opts.currentFingerprint);
  if (mem === 'exact') return { skip: true, reason: 'session_fresh' };
  if (mem === 'bar_hysteresis') return { skip: true, reason: 'bar_hysteresis' };

  const local = matchFingerprint(opts.localFingerprint, opts.currentFingerprint);
  if (local === 'exact') return { skip: true, reason: 'local_fresh' };
  if (local === 'bar_hysteresis') return { skip: true, reason: 'bar_hysteresis' };

  if (opts.stored) {
    if (opts.stored.engine !== FINALISTS_FRESHNESS_ENGINE) {
      return { skip: false, reason: 'engine_mismatch' };
    }
    const db = matchFingerprint(opts.stored.inputFingerprint, opts.currentFingerprint);
    if (db === 'exact') return { skip: true, reason: 'fresh' };
    if (db === 'bar_hysteresis') return { skip: true, reason: 'bar_hysteresis' };
    return { skip: false, reason: 'fingerprint_mismatch' };
  }

  // Legacy: Finalistas active con slots y sin stamp → adoptar.
  if (opts.topStatus === 'active') {
    return { skip: true, reason: 'adopt_existing_top', adoptFingerprint: true };
  }

  if (opts.topStatus !== 'active' && opts.topStatus !== 'semifinal') {
    return { skip: false, reason: 'no_active_top' };
  }

  return { skip: false, reason: 'no_stamp' };
}

export function instrumentLastBarDate(
  instrument:
    | { meta?: { lastBarDate?: string | null } | null; lastBarDate?: string | null }
    | null
    | undefined,
): string | null {
  if (!instrument) return null;
  if (instrument.meta && 'lastBarDate' in instrument.meta) {
    return instrument.meta.lastBarDate ?? null;
  }
  return instrument.lastBarDate ?? null;
}

export function formatFreshnessAge(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return '—';
  const mins = Math.max(0, Math.round((now - t) / 60_000));
  if (mins < 1) return 'ahora';
  if (mins < 60) return `hace ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `hace ${hours} h`;
  const days = Math.round(hours / 24);
  return `hace ${days} d`;
}

export function freshnessSkipDenialLabel(reason: string): string {
  switch (reason) {
    case 'prefs_off':
      return 'frescura OFF';
    case 'force':
      return 'forzar reanálisis';
    case 'no_active_top':
      return 'sin Finalistas / sin huella previa';
    case 'no_finalists_slots':
      return 'sin Finalistas (slots vacíos · hay que analizar)';
    case 'no_stamp':
      return 'sin stamp de frescura';
    case 'fingerprint_mismatch':
      return 'datos/contexto distintos';
    case 'engine_mismatch':
      return 'motor de frescura distinto';
    case 'context_not_ready':
      return 'esperando perfil/datos';
    case 'top_fetch_error':
      return 'error leyendo TOP';
    case 'bar_hysteresis':
      return 'barra reciente (histéresis)';
    default:
      return reason;
  }
}

/** ¿Podemos calcular huella estable (sin carrera pid:none)? */
export function isFinalistsFreshnessContextReady(opts: {
  instrumentsFetched: boolean;
  /** false mientras carga el perfil de la cuenta activa. */
  accountProfileReady: boolean;
  /** false mientras cargan estrategias guardadas si Optimizadas o Mis están ON. */
  strategiesReady: boolean;
}): boolean {
  return opts.instrumentsFetched && opts.accountProfileReady && opts.strategiesReady;
}
