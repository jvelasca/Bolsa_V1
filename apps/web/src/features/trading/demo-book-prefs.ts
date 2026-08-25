/**
 * Preferencias del libro operativo de la cuenta activa DEMO — MANUAL / SEMI / AUTO.
 *
 * Slice 1 + A1 + A3-wire: localStorage. Canal SEMI = Camino C (F3 Confirm).
 * AUTO (BETA-D): UI on solo si `DEMO_BOOK_AUTO_UI_ENABLED` **y** armado local A3
 * (`loadAutoArm().armed`). Sin armado, `mode: auto` en storage se coacciona a SEMI.
 * Execute sigue detrás de `PAPER_D_EXECUTE` (server); arm ≠ execute.
 *
 * @see docs/engineering/demo-operating-modes-brief-2026-08-03.md
 * @see docs/engineering/plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md
 * @see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md §3 A3
 */

import {
  loadAutoArm,
  disarmAutoArm,
} from "@/features/trading/demo-book-auto-arm";
import { DEMO_BOOK_AUTO_UI_ENABLED } from "@/features/trading/demo-book-auto-copy";

export const DEMO_BOOK_PREFS_KEY = "bolsa-demo-book-prefs-v1";

export type DemoBookMode = "manual" | "semi" | "auto";

/** Preferencia suave de diversificación geográfica (no veto duro). */
export type DemoBookCountryPrefer = "home_first" | "europe_first" | "global_ok";

export type DemoBookPrefs = {
  /** MANUAL = aviso · SEMI = Confirm F3 · AUTO reserved (A1: UI disabled). */
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
    mode: "semi",
    maxOpenPositions: 10,
    defaultSizePctOfCash: 10,
    countryPrefer: "home_first",
  };
}

function clampInt(
  n: number,
  min: number,
  max: number,
  fallback: number,
): number {
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

export function normalizeDemoBookPrefs(raw: unknown): DemoBookPrefs {
  const d = defaultDemoBookPrefs();
  if (!raw || typeof raw !== "object") return d;
  const o = raw as Partial<DemoBookPrefs>;
  const modeRaw: DemoBookMode =
    o.mode === "manual" || o.mode === "semi" || o.mode === "auto"
      ? o.mode
      : d.mode;
  // A1 + A3-wire: AUTO solo si UI flag on **y** armado local.
  const autoAllowed = DEMO_BOOK_AUTO_UI_ENABLED && loadAutoArm().armed === true;
  const mode: DemoBookMode =
    modeRaw === "auto" && !autoAllowed ? "semi" : modeRaw;
  const countryPrefer: DemoBookCountryPrefer =
    o.countryPrefer === "home_first" ||
    o.countryPrefer === "europe_first" ||
    o.countryPrefer === "global_ok"
      ? o.countryPrefer
      : d.countryPrefer;
  return {
    mode,
    maxOpenPositions: clampInt(
      typeof o.maxOpenPositions === "number"
        ? o.maxOpenPositions
        : d.maxOpenPositions,
      DEMO_BOOK_MAX_OPEN_MIN,
      DEMO_BOOK_MAX_OPEN_MAX,
      d.maxOpenPositions,
    ),
    defaultSizePctOfCash: clampInt(
      typeof o.defaultSizePctOfCash === "number"
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

function prefsEqual(a: DemoBookPrefs, b: DemoBookPrefs): boolean {
  return (
    a.mode === b.mode &&
    a.maxOpenPositions === b.maxOpenPositions &&
    a.defaultSizePctOfCash === b.defaultSizePctOfCash &&
    a.countryPrefer === b.countryPrefer
  );
}

/** Snapshot estable para `useSyncExternalStore` (misma ref si no cambia el valor). */
let cachedClientSnapshot: DemoBookPrefs | null = null;

const SERVER_SNAPSHOT: DemoBookPrefs = {
  mode: "semi",
  maxOpenPositions: 10,
  defaultSizePctOfCash: 10,
  countryPrefer: "home_first",
};

function rememberSnapshot(next: DemoBookPrefs): DemoBookPrefs {
  if (cachedClientSnapshot && prefsEqual(cachedClientSnapshot, next)) {
    return cachedClientSnapshot;
  }
  cachedClientSnapshot = next;
  return next;
}

export function saveDemoBookPrefs(prefs: DemoBookPrefs): void {
  const n = normalizeDemoBookPrefs(prefs);
  localStorage.setItem(DEMO_BOOK_PREFS_KEY, JSON.stringify(n));
  rememberSnapshot(n);
  notifyDemoBookPrefs();
}

export function patchDemoBookPrefs(
  patch: Partial<DemoBookPrefs>,
): DemoBookPrefs {
  const current = loadDemoBookPrefs();
  const next = normalizeDemoBookPrefs({ ...current, ...patch });
  // D3: salir de Auto desarma el armado local (no deja armed huérfano).
  if (current.mode === "auto" && next.mode !== "auto") {
    disarmAutoArm();
  }
  saveDemoBookPrefs(next);
  return next;
}

const demoBookPrefsListeners = new Set<() => void>();

function notifyDemoBookPrefs() {
  for (const listener of demoBookPrefsListeners) listener();
}

function onDemoBookPrefsStorage(e: StorageEvent) {
  if (e.key === DEMO_BOOK_PREFS_KEY || e.key === null) {
    // Otra pestaña: invalidar caché y releer.
    cachedClientSnapshot = null;
    rememberSnapshot(loadDemoBookPrefs());
    notifyDemoBookPrefs();
  }
}

/** Suscripción misma-pestaña; también reacciona a `storage` entre pestañas. */
export function subscribeDemoBookPrefs(listener: () => void): () => void {
  demoBookPrefsListeners.add(listener);
  if (demoBookPrefsListeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", onDemoBookPrefsStorage);
  }
  return () => {
    demoBookPrefsListeners.delete(listener);
    if (demoBookPrefsListeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onDemoBookPrefsStorage);
    }
  };
}

/**
 * Snapshot client para `useSyncExternalStore`.
 * Debe devolver la misma referencia si el valor no cambió (si no → bucle de renders).
 */
export function getDemoBookPrefsSnapshot(): DemoBookPrefs {
  return rememberSnapshot(loadDemoBookPrefs());
}

export function getDemoBookPrefsServerSnapshot(): DemoBookPrefs {
  return SERVER_SNAPSHOT;
}

/** SEMI permite encolar Confirm; MANUAL solo aviso; AUTO reserved (execute nunca hasta thaw). */
export function demoBookAllowsEnqueueConfirm(mode: DemoBookMode): boolean {
  return mode === "semi" || mode === "auto";
}

/** Solo SEMI ejecuta Confirm hoy. AUTO → false aunque el modo exista en tipos. */
export function demoBookAllowsExecute(mode: DemoBookMode): boolean {
  return mode === "semi";
}

/**
 * SEMI/AUTO exigen que el instrumento esté en la lista Estudio.
 * MANUAL no lo exige (puedes operar sin meterlo en el universo).
 */
export function demoBookRequiresEstudioMembership(mode: DemoBookMode): boolean {
  return mode === "semi" || mode === "auto";
}

export const ESTUDIO_MEMBERSHIP_REQUIRED_MSG =
  "SEMI/AUTO requieren el valor en la lista Estudio. Añádelo desde Listas (selección → A Estudio) o abriendo el gráfico.";

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
  const pct = clampInt(
    opts.sizePctOfCash,
    DEMO_BOOK_SIZE_PCT_MIN,
    DEMO_BOOK_SIZE_PCT_MAX,
    10,
  );
  if (!(cash > 0) || !(price > 0)) return 0;
  const budget = cash * (pct / 100);
  if (budget < price) return 0;
  return Math.max(1, Math.floor(budget / price));
}
