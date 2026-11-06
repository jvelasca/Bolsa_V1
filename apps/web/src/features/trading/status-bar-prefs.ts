/**
 * Preferencias de la barra de estado del terminal Mercado (persistidas).
 *
 * Antes vivían en un `useState` dentro de `TradingStatusBar`: se perdían al recargar.
 * Aquí se persisten por dispositivo, igual que el resto de «chrome» de UI
 * (`docs/UI_PREFS_LOCALSTORAGE.md`).
 *
 * Clave `bolsa-status-bar-prefs-v1`:
 *  - `visibleItems`: métricas de la cuenta que se muestran a la izquierda.
 *  - `showProviderHealth`: icono de servidores de datos en el rail derecho; clic →
 *    Configuración → Sync / proveedores.
 */

export const STATUS_BAR_PREFS_KEY = "bolsa-status-bar-prefs-v1";

/** Métricas de la cuenta Activa que la barra puede mostrar a la izquierda. */
export type StatusItemId =
  | "equity"
  | "cash"
  | "marketValue"
  | "pnl"
  | "positions";

export const STATUS_ITEM_IDS: readonly StatusItemId[] = [
  "equity",
  "cash",
  "marketValue",
  "pnl",
  "positions",
];

export type StatusBarPrefs = {
  visibleItems: StatusItemId[];
  /** Icono de servidores de datos (verde OK / rojo si alguno cae). */
  showProviderHealth: boolean;
};

export function defaultStatusBarPrefs(): StatusBarPrefs {
  return {
    visibleItems: ["marketValue", "cash", "pnl", "equity"],
    showProviderHealth: true,
  };
}

function normalizeVisibleItems(raw: unknown): StatusItemId[] {
  if (!Array.isArray(raw)) return defaultStatusBarPrefs().visibleItems;
  const seen = new Set<StatusItemId>();
  const items: StatusItemId[] = [];
  // Se respeta el orden guardado (es el orden de la barra); solo se sanea.
  for (const value of raw) {
    if (!STATUS_ITEM_IDS.includes(value as StatusItemId)) continue;
    const id = value as StatusItemId;
    if (seen.has(id)) continue;
    seen.add(id);
    items.push(id);
  }
  return items;
}

export function normalizeStatusBarPrefs(raw: unknown): StatusBarPrefs {
  const defaults = defaultStatusBarPrefs();
  if (!raw || typeof raw !== "object") return defaults;
  const source = raw as Partial<StatusBarPrefs>;
  return {
    visibleItems: normalizeVisibleItems(source.visibleItems),
    showProviderHealth:
      typeof source.showProviderHealth === "boolean"
        ? source.showProviderHealth
        : defaults.showProviderHealth,
  };
}

export function loadStatusBarPrefs(): StatusBarPrefs {
  try {
    const raw = localStorage.getItem(STATUS_BAR_PREFS_KEY);
    if (!raw) return defaultStatusBarPrefs();
    return normalizeStatusBarPrefs(JSON.parse(raw));
  } catch {
    return defaultStatusBarPrefs();
  }
}

function prefsEqual(a: StatusBarPrefs, b: StatusBarPrefs): boolean {
  return (
    a.showProviderHealth === b.showProviderHealth &&
    a.visibleItems.length === b.visibleItems.length &&
    a.visibleItems.every((id, index) => id === b.visibleItems[index])
  );
}

let cachedClientSnapshot: StatusBarPrefs | null = null;

const SERVER_SNAPSHOT: StatusBarPrefs = defaultStatusBarPrefs();

function rememberSnapshot(next: StatusBarPrefs): StatusBarPrefs {
  if (cachedClientSnapshot && prefsEqual(cachedClientSnapshot, next)) {
    return cachedClientSnapshot;
  }
  cachedClientSnapshot = next;
  return next;
}

export function saveStatusBarPrefs(prefs: StatusBarPrefs): void {
  const next = normalizeStatusBarPrefs(prefs);
  try {
    localStorage.setItem(STATUS_BAR_PREFS_KEY, JSON.stringify(next));
  } catch {
    // Sin almacenamiento (modo privado): la preferencia vale para esta sesión.
  }
  rememberSnapshot(next);
  notifyStatusBarPrefs();
}

export function patchStatusBarPrefs(
  patch: Partial<StatusBarPrefs>,
): StatusBarPrefs {
  const next = normalizeStatusBarPrefs({ ...loadStatusBarPrefs(), ...patch });
  saveStatusBarPrefs(next);
  return next;
}

export function toggleStatusItem(
  id: StatusItemId,
  visible: boolean,
): StatusBarPrefs {
  const current = loadStatusBarPrefs();
  const visibleItems = visible
    ? [...current.visibleItems, id]
    : current.visibleItems.filter((item) => item !== id);
  return patchStatusBarPrefs({ visibleItems });
}

export function setShowProviderHealth(show: boolean): StatusBarPrefs {
  return patchStatusBarPrefs({ showProviderHealth: show });
}

const listeners = new Set<() => void>();

function notifyStatusBarPrefs() {
  for (const listener of listeners) listener();
}

function onStorage(event: StorageEvent) {
  if (event.key === STATUS_BAR_PREFS_KEY || event.key === null) {
    cachedClientSnapshot = null;
    rememberSnapshot(loadStatusBarPrefs());
    notifyStatusBarPrefs();
  }
}

export function subscribeStatusBarPrefs(listener: () => void): () => void {
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

export function getStatusBarPrefsSnapshot(): StatusBarPrefs {
  return rememberSnapshot(loadStatusBarPrefs());
}

export function getStatusBarPrefsServerSnapshot(): StatusBarPrefs {
  return SERVER_SNAPSHOT;
}
