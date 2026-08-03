/**
 * Preferencias del «libro operativo» DEMO — MANUAL / SEMI (/ AUTO reserved).
 *
 * Slice 1: localStorage. Canal de ejecución SEMI = Camino C (F3 Confirm).
 *
 * @see docs/engineering/demo-operating-modes-brief-2026-08-03.md
 * @see docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
 */

export const DEMO_BOOK_PREFS_KEY = 'bolsa-demo-book-prefs-v1';

export type DemoBookMode = 'manual' | 'semi' | 'auto';

/** Preferencia suave de diversificación geográfica (no veto duro). */
export type DemoBookCountryPrefer = 'home_first' | 'europe_first' | 'global_ok';

export type DemoBookPrefs = {
  /** MANUAL = aviso · SEMI = Confirm F3 · AUTO reserved (UI disabled slice 1). */
  mode: DemoBookMode;
  /** Máximo de posiciones abiertas en la cuenta DEMO. */
  maxOpenPositions: number;
  /** % del cash disponible sugerido por operación (editable en Confirm). */
  defaultSizePctOfCash: number;
  countryPrefer: DemoBookCountryPrefer;
};

export const DEMO_BOOK_MAX_OPEN_MIN = 1;
export const DEMO_BOOK_MAX_OPEN_MAX = 40;
export const DEMO_BOOK_SIZE_PCT_MIN = 1;
export const DEMO_BOOK_SIZE_PCT_MAX = 100;

export function defaultDemoBookPrefs(): DemoBookPrefs {
  return {
    mode: 'semi',
    maxOpenPositions: 10,
    defaultSizePctOfCash: 10,
    countryPrefer: 'home_first',
  };
}

function clampInt(n: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

export function normalizeDemoBookPrefs(raw: unknown): DemoBookPrefs {
  const d = defaultDemoBookPrefs();
  if (!raw || typeof raw !== 'object') return d;
  const o = raw as Partial<DemoBookPrefs>;
  const mode: DemoBookMode =
    o.mode === 'manual' || o.mode === 'semi' || o.mode === 'auto' ? o.mode : d.mode;
  const countryPrefer: DemoBookCountryPrefer =
    o.countryPrefer === 'home_first' ||
    o.countryPrefer === 'europe_first' ||
    o.countryPrefer === 'global_ok'
      ? o.countryPrefer
      : d.countryPrefer;
  return {
    mode,
    maxOpenPositions: clampInt(
      typeof o.maxOpenPositions === 'number' ? o.maxOpenPositions : d.maxOpenPositions,
      DEMO_BOOK_MAX_OPEN_MIN,
      DEMO_BOOK_MAX_OPEN_MAX,
      d.maxOpenPositions,
    ),
    defaultSizePctOfCash: clampInt(
      typeof o.defaultSizePctOfCash === 'number'
        ? o.defaultSizePctOfCash
        : d.defaultSizePctOfCash,
      DEMO_BOOK_SIZE_PCT_MIN,
      DEMO_BOOK_SIZE_PCT_MAX,
      d.defaultSizePctOfCash,
    ),
    countryPrefer,
  };
}

export function loadDemoBookPrefs(): DemoBookPrefs {
  try {
    const raw = localStorage.getItem(DEMO_BOOK_PREFS_KEY);
    if (!raw) return defaultDemoBookPrefs();
    return normalizeDemoBookPrefs(JSON.parse(raw));
  } catch {
    return defaultDemoBookPrefs();
  }
}

export function saveDemoBookPrefs(prefs: DemoBookPrefs): void {
  const n = normalizeDemoBookPrefs(prefs);
  localStorage.setItem(DEMO_BOOK_PREFS_KEY, JSON.stringify(n));
}

export function patchDemoBookPrefs(patch: Partial<DemoBookPrefs>): DemoBookPrefs {
  const next = normalizeDemoBookPrefs({ ...loadDemoBookPrefs(), ...patch });
  saveDemoBookPrefs(next);
  return next;
}

/** SEMI permite encolar Confirm; MANUAL solo aviso; AUTO reserved. */
export function demoBookAllowsEnqueueConfirm(mode: DemoBookMode): boolean {
  return mode === 'semi' || mode === 'auto';
}

export function demoBookAllowsExecute(mode: DemoBookMode): boolean {
  return mode === 'semi';
}

/**
 * Cantidad entera sugerida: floor((cash * pct/100) / price).
 * Mínimo 1 si hay presupuesto ≥ precio; 0 si no alcanza.
 */
export function suggestQuantityFromCash(opts: {
  cash: number;
  price: number;
  sizePctOfCash: number;
}): number {
  const cash = Number(opts.cash);
  const price = Number(opts.price);
  const pct = clampInt(opts.sizePctOfCash, DEMO_BOOK_SIZE_PCT_MIN, DEMO_BOOK_SIZE_PCT_MAX, 10);
  if (!(cash > 0) || !(price > 0)) return 0;
  const budget = cash * (pct / 100);
  if (budget < price) return 0;
  return Math.max(1, Math.floor(budget / price));
}
