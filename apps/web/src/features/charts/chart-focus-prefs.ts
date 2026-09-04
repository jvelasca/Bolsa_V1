/**
 * V2.30 — Chart Focus: modo Simple / Completo (menos líneas en gráfico).
 *
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 * @see docs/engineering/traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md
 */

export const CHART_FOCUS_PREFS_KEY = "bolsa-chart-focus-prefs-v1";

export type ChartFocusModeV1 = "simple" | "completo";

export type ChartFocusPrefs = {
  mode: ChartFocusModeV1;
};

export function defaultChartFocusPrefs(): ChartFocusPrefs {
  return { mode: "simple" };
}

export function isChartFocusMode(v: unknown): v is ChartFocusModeV1 {
  return v === "simple" || v === "completo";
}

export function normalizeChartFocusPrefs(raw: unknown): ChartFocusPrefs {
  const d = defaultChartFocusPrefs();
  if (!raw || typeof raw !== "object") return d;
  const o = raw as Partial<ChartFocusPrefs>;
  return {
    mode: isChartFocusMode(o.mode) ? o.mode : d.mode,
  };
}

export function loadChartFocusPrefs(): ChartFocusPrefs {
  try {
    const raw = localStorage.getItem(CHART_FOCUS_PREFS_KEY);
    if (!raw) return defaultChartFocusPrefs();
    return normalizeChartFocusPrefs(JSON.parse(raw));
  } catch {
    return defaultChartFocusPrefs();
  }
}

function prefsEqual(a: ChartFocusPrefs, b: ChartFocusPrefs): boolean {
  return a.mode === b.mode;
}

let cachedClientSnapshot: ChartFocusPrefs | null = null;

const SERVER_SNAPSHOT: ChartFocusPrefs = { mode: "simple" };

function rememberSnapshot(next: ChartFocusPrefs): ChartFocusPrefs {
  if (cachedClientSnapshot && prefsEqual(cachedClientSnapshot, next)) {
    return cachedClientSnapshot;
  }
  cachedClientSnapshot = next;
  return next;
}

export function saveChartFocusPrefs(prefs: ChartFocusPrefs): void {
  const n = normalizeChartFocusPrefs(prefs);
  localStorage.setItem(CHART_FOCUS_PREFS_KEY, JSON.stringify(n));
  rememberSnapshot(n);
  notifyChartFocusPrefs();
}

export function patchChartFocusPrefs(
  patch: Partial<ChartFocusPrefs>,
): ChartFocusPrefs {
  const next = normalizeChartFocusPrefs({
    ...loadChartFocusPrefs(),
    ...patch,
  });
  saveChartFocusPrefs(next);
  return next;
}

const listeners = new Set<() => void>();

function notifyChartFocusPrefs() {
  for (const listener of listeners) listener();
}

function onStorage(e: StorageEvent) {
  if (e.key === CHART_FOCUS_PREFS_KEY || e.key === null) {
    cachedClientSnapshot = null;
    rememberSnapshot(loadChartFocusPrefs());
    notifyChartFocusPrefs();
  }
}

export function subscribeChartFocusPrefs(listener: () => void): () => void {
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

export function getChartFocusPrefsSnapshot(): ChartFocusPrefs {
  return rememberSnapshot(loadChartFocusPrefs());
}

export function getChartFocusPrefsServerSnapshot(): ChartFocusPrefs {
  return SERVER_SNAPSHOT;
}
