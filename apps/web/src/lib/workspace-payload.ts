import type {
  TradingDockLayoutPrefs,
  WorkspaceDocument,
  WorkspacePayload,
} from '@bolsa/shared';

export const LEGACY_WORKSPACE_STORAGE_KEY = 'bolsa-workspace';

const DEFAULT_LISTS_WIDTH_PCT = 26;
const DEFAULT_OPERATIONS_HEIGHT_PCT = 22;

/** Layout de paneles por defecto (API legado; el UI usa solo localStorage). */
export const DEFAULT_DOCK_LAYOUT: TradingDockLayoutPrefs = {
  listsOpen: true,
  operationsOpen: true,
  listsWidthPct: DEFAULT_LISTS_WIDTH_PCT,
  operationsHeightPct: DEFAULT_OPERATIONS_HEIGHT_PCT,
};

/**
 * Payload de guardado. `dockLayout` se envía como default fijo: el chrome de paneles
 * es por dispositivo (`bolsa-trading-layout-v1`) y no se aplica al cargar.
 */
export function buildWorkspacePayload(document: WorkspaceDocument): WorkspacePayload {
  return {
    document: {
      ...document,
      updatedAt: new Date().toISOString(),
    },
    dockLayout: DEFAULT_DOCK_LAYOUT,
  };
}

export function readLegacyWorkspaceFromStorage(): WorkspaceDocument | null {
  const raw = localStorage.getItem(LEGACY_WORKSPACE_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as {
      state?: { workspace?: WorkspaceDocument };
      workspace?: WorkspaceDocument;
    };
    return parsed.state?.workspace ?? parsed.workspace ?? null;
  } catch {
    return null;
  }
}

export function readLegacyDockFromStorage(): TradingDockLayoutPrefs | null {
  const raw = localStorage.getItem('bolsa-trading-layout-v1');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as {
      state?: {
        listsOpen?: boolean;
        operationsOpen?: boolean;
        listsWidthPct?: number;
        operationsHeightPct?: number;
      };
    };
    const s = parsed.state;
    if (!s) return null;
    return {
      listsOpen: s.listsOpen ?? true,
      operationsOpen: s.operationsOpen ?? true,
      listsWidthPct: s.listsWidthPct ?? DEFAULT_LISTS_WIDTH_PCT,
      operationsHeightPct: s.operationsHeightPct ?? DEFAULT_OPERATIONS_HEIGHT_PCT,
    };
  } catch {
    return null;
  }
}
