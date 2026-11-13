/**
 * S2 — Visibilidad de los niveles CALCULADOS en el gráfico.
 *
 * Preferencia local: no toca contrato ni configuración persistida en servidor.
 *
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

export const MARKET_STRUCTURE_PREFS_KEY = "bolsa-market-structure-prefs-v1";

export type MarketStructurePrefs = {
  /** Pinta las líneas calculadas (solo niveles `detectado`). */
  showChartLevels: boolean;
};

export function defaultMarketStructurePrefs(): MarketStructurePrefs {
  return { showChartLevels: true };
}

export function normalizeMarketStructurePrefs(
  raw: unknown,
): MarketStructurePrefs {
  const d = defaultMarketStructurePrefs();
  if (!raw || typeof raw !== "object") return d;
  const o = raw as Partial<MarketStructurePrefs>;
  return {
    showChartLevels:
      typeof o.showChartLevels === "boolean"
        ? o.showChartLevels
        : d.showChartLevels,
  };
}

export function loadMarketStructurePrefs(): MarketStructurePrefs {
  try {
    const raw = localStorage.getItem(MARKET_STRUCTURE_PREFS_KEY);
    if (!raw) return defaultMarketStructurePrefs();
    return normalizeMarketStructurePrefs(JSON.parse(raw));
  } catch {
    return defaultMarketStructurePrefs();
  }
}

function prefsEqual(
  a: MarketStructurePrefs,
  b: MarketStructurePrefs,
): boolean {
  return a.showChartLevels === b.showChartLevels;
}

let cachedClientSnapshot: MarketStructurePrefs | null = null;

const SERVER_SNAPSHOT: MarketStructurePrefs = { showChartLevels: true };

function rememberSnapshot(next: MarketStructurePrefs): MarketStructurePrefs {
  if (cachedClientSnapshot && prefsEqual(cachedClientSnapshot, next)) {
    return cachedClientSnapshot;
  }
  cachedClientSnapshot = next;
  return next;
}

export function saveMarketStructurePrefs(prefs: MarketStructurePrefs): void {
  const n = normalizeMarketStructurePrefs(prefs);
  localStorage.setItem(MARKET_STRUCTURE_PREFS_KEY, JSON.stringify(n));
  rememberSnapshot(n);
  notifyMarketStructurePrefs();
}

export function patchMarketStructurePrefs(
  patch: Partial<MarketStructurePrefs>,
): MarketStructurePrefs {
  const next = normalizeMarketStructurePrefs({
    ...loadMarketStructurePrefs(),
    ...patch,
  });
  saveMarketStructurePrefs(next);
  return next;
}

const listeners = new Set<() => void>();

function notifyMarketStructurePrefs() {
  for (const listener of listeners) listener();
}

function onStorage(e: StorageEvent) {
  if (e.key === MARKET_STRUCTURE_PREFS_KEY || e.key === null) {
    cachedClientSnapshot = null;
    rememberSnapshot(loadMarketStructurePrefs());
    notifyMarketStructurePrefs();
  }
}

export function subscribeMarketStructurePrefs(listener: () => void): () => void {
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

export function getMarketStructurePrefsSnapshot(): MarketStructurePrefs {
  return rememberSnapshot(loadMarketStructurePrefs());
}

export function getMarketStructurePrefsServerSnapshot(): MarketStructurePrefs {
  return SERVER_SNAPSHOT;
}
