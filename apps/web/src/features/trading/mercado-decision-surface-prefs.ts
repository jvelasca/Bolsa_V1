/**
 * V1.63 — Ubicación de la Decision Surface en Mercado (panel vs gráfico).
 *
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 * @see docs/engineering/spec-v163-decision-surface-placement-2026-09-02.md
 */

export const MERCADO_DECISION_SURFACE_PREFS_KEY =
  "bolsa-mercado-decision-surface-v1";

export type DecisionSurfacePlacementV1 = "panel" | "chart";

export type MercadoDecisionSurfacePrefs = {
  placement: DecisionSurfacePlacementV1;
};

export function defaultMercadoDecisionSurfacePrefs(): MercadoDecisionSurfacePrefs {
  return { placement: "panel" };
}

export function normalizeMercadoDecisionSurfacePrefs(
  raw: unknown,
): MercadoDecisionSurfacePrefs {
  const d = defaultMercadoDecisionSurfacePrefs();
  if (!raw || typeof raw !== "object") return d;
  const o = raw as Partial<MercadoDecisionSurfacePrefs>;
  const placement =
    o.placement === "chart" || o.placement === "panel"
      ? o.placement
      : d.placement;
  return { placement };
}

export function loadMercadoDecisionSurfacePrefs(): MercadoDecisionSurfacePrefs {
  try {
    const raw = localStorage.getItem(MERCADO_DECISION_SURFACE_PREFS_KEY);
    if (!raw) return defaultMercadoDecisionSurfacePrefs();
    return normalizeMercadoDecisionSurfacePrefs(JSON.parse(raw));
  } catch {
    return defaultMercadoDecisionSurfacePrefs();
  }
}

function prefsEqual(
  a: MercadoDecisionSurfacePrefs,
  b: MercadoDecisionSurfacePrefs,
): boolean {
  return a.placement === b.placement;
}

let cachedClientSnapshot: MercadoDecisionSurfacePrefs | null = null;

const SERVER_SNAPSHOT: MercadoDecisionSurfacePrefs = { placement: "panel" };

function rememberSnapshot(
  next: MercadoDecisionSurfacePrefs,
): MercadoDecisionSurfacePrefs {
  if (cachedClientSnapshot && prefsEqual(cachedClientSnapshot, next)) {
    return cachedClientSnapshot;
  }
  cachedClientSnapshot = next;
  return next;
}

export function saveMercadoDecisionSurfacePrefs(
  prefs: MercadoDecisionSurfacePrefs,
): void {
  const n = normalizeMercadoDecisionSurfacePrefs(prefs);
  localStorage.setItem(MERCADO_DECISION_SURFACE_PREFS_KEY, JSON.stringify(n));
  rememberSnapshot(n);
  notifyMercadoDecisionSurfacePrefs();
}

export function patchMercadoDecisionSurfacePrefs(
  patch: Partial<MercadoDecisionSurfacePrefs>,
): MercadoDecisionSurfacePrefs {
  const next = normalizeMercadoDecisionSurfacePrefs({
    ...loadMercadoDecisionSurfacePrefs(),
    ...patch,
  });
  saveMercadoDecisionSurfacePrefs(next);
  return next;
}

const listeners = new Set<() => void>();

function notifyMercadoDecisionSurfacePrefs() {
  for (const listener of listeners) listener();
}

function onStorage(e: StorageEvent) {
  if (e.key === MERCADO_DECISION_SURFACE_PREFS_KEY || e.key === null) {
    cachedClientSnapshot = null;
    rememberSnapshot(loadMercadoDecisionSurfacePrefs());
    notifyMercadoDecisionSurfacePrefs();
  }
}

export function subscribeMercadoDecisionSurfacePrefs(
  listener: () => void,
): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

export function getMercadoDecisionSurfacePrefsSnapshot(): MercadoDecisionSurfacePrefs {
  return rememberSnapshot(loadMercadoDecisionSurfacePrefs());
}

export function getMercadoDecisionSurfacePrefsServerSnapshot(): MercadoDecisionSurfacePrefs {
  return SERVER_SNAPSHOT;
}
