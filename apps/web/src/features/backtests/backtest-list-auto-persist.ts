/**
 * Persistencia de Lista AUTO en pausa (localStorage) y continuación tras Stop.
 *
 * Pausa: {@link LIST_AUTO_PAUSE_STORAGE_KEY} — entre tickers, Reanudar manual.
 * Stop→Play: {@link LIST_AUTO_CONTINUE_STORAGE_KEY} — el siguiente Play
 * reanuda en el índice interrumpido (no vuelve al #1).
 *
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 */

import type { ListAutoCampaign } from '@/features/backtests/backtest-list-auto';
import type { ListAutoBoardState, ListAutoBoardRow } from '@/features/backtests/backtest-list-auto-board';

export const LIST_AUTO_PAUSE_STORAGE_KEY = 'bolsa-list-auto-paused-v1';
export const LIST_AUTO_CONTINUE_STORAGE_KEY = 'bolsa-list-auto-continue-v1';

export type ListAutoPausedSnapshotV1 = {
  version: 1;
  savedAt: string;
  campaign: {
    listId: string;
    instrumentIds: string[];
    /** Índice del siguiente ticker a ejecutar al Reanudar. */
    index: number;
    forceRescan: boolean;
  };
  board: ListAutoBoardState;
  /** Fingerprints de sesión (omitidos / analizados) para no re-gastar CPU. */
  freshnessMemory?: Record<string, string>;
};

/** Tras Stop: el próximo Play de la misma lista continúa aquí. */
export type ListAutoContinueSnapshotV1 = {
  version: 1;
  savedAt: string;
  listId: string;
  instrumentIds: string[];
  /** Índice donde reanudar (el que estaba en curso o el siguiente). */
  nextIndex: number;
  board: ListAutoBoardState;
  freshnessMemory?: Record<string, string>;
};

export function buildListAutoPausedSnapshot(opts: {
  campaign: ListAutoCampaign;
  board: ListAutoBoardState;
  freshnessMemory?: Map<string, string> | Record<string, string>;
  at?: string;
}): ListAutoPausedSnapshotV1 | null {
  if (opts.campaign.aborted || !opts.campaign.paused) return null;
  if (opts.board.done || opts.board.aborted || !opts.board.paused) return null;
  if (opts.board.rows.some((r) => r.phase === 'running')) return null;
  if (opts.campaign.index >= opts.campaign.instrumentIds.length) return null;

  const freshnessMemory =
    opts.freshnessMemory instanceof Map
      ? Object.fromEntries(opts.freshnessMemory.entries())
      : opts.freshnessMemory;

  return {
    version: 1,
    savedAt: opts.at ?? new Date().toISOString(),
    campaign: {
      listId: opts.campaign.listId,
      instrumentIds: [...opts.campaign.instrumentIds],
      index: opts.campaign.index,
      forceRescan: Boolean(opts.campaign.forceRescan),
    },
    board: {
      ...opts.board,
      paused: true,
      done: false,
      aborted: false,
      rows: opts.board.rows.map((r) => ({ ...r })),
    },
    freshnessMemory,
  };
}

export function serializeListAutoPausedSnapshot(
  snap: ListAutoPausedSnapshotV1,
): string {
  return JSON.stringify(snap);
}

export function parseListAutoPausedSnapshot(
  raw: unknown,
): ListAutoPausedSnapshotV1 | null {
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Partial<ListAutoPausedSnapshotV1>;
  if (o.version !== 1) return null;
  if (!o.campaign || typeof o.campaign !== 'object') return null;
  if (!Array.isArray(o.campaign.instrumentIds) || o.campaign.instrumentIds.length === 0) {
    return null;
  }
  if (typeof o.campaign.listId !== 'string' || !o.campaign.listId) return null;
  if (typeof o.campaign.index !== 'number' || o.campaign.index < 0) return null;
  if (o.campaign.index >= o.campaign.instrumentIds.length) return null;
  if (!o.board || typeof o.board !== 'object') return null;
  if (!Array.isArray(o.board.rows) || o.board.rows.length === 0) return null;

  return {
    version: 1,
    savedAt: typeof o.savedAt === 'string' ? o.savedAt : new Date().toISOString(),
    campaign: {
      listId: o.campaign.listId,
      instrumentIds: o.campaign.instrumentIds.map(String),
      index: o.campaign.index,
      forceRescan: Boolean(o.campaign.forceRescan),
    },
    board: {
      listId: String(o.board.listId ?? o.campaign.listId),
      currentIndex: typeof o.board.currentIndex === 'number' ? o.board.currentIndex : o.campaign.index,
      aborted: false,
      done: false,
      paused: true,
      rows: o.board.rows as ListAutoBoardState['rows'],
    },
    freshnessMemory:
      o.freshnessMemory && typeof o.freshnessMemory === 'object'
        ? (o.freshnessMemory as Record<string, string>)
        : undefined,
  };
}

export function saveListAutoPausedSnapshot(snap: ListAutoPausedSnapshotV1): void {
  try {
    localStorage.setItem(
      LIST_AUTO_PAUSE_STORAGE_KEY,
      serializeListAutoPausedSnapshot(snap),
    );
  } catch {
    // quota / private mode
  }
}

export function loadListAutoPausedSnapshot(): ListAutoPausedSnapshotV1 | null {
  try {
    const raw = localStorage.getItem(LIST_AUTO_PAUSE_STORAGE_KEY);
    if (!raw) return null;
    return parseListAutoPausedSnapshot(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function clearListAutoPausedSnapshot(): void {
  try {
    localStorage.removeItem(LIST_AUTO_PAUSE_STORAGE_KEY);
  } catch {
    // ignore
  }
}

/** Campaña restaurada desde snapshot (siempre paused). */
export function campaignFromPausedSnapshot(
  snap: ListAutoPausedSnapshotV1,
): ListAutoCampaign {
  return {
    listId: snap.campaign.listId,
    instrumentIds: snap.campaign.instrumentIds,
    index: snap.campaign.index,
    aborted: false,
    paused: true,
    forceRescan: snap.campaign.forceRescan,
  };
}

function sameIdList(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((id, i) => id === b[i]);
}

export function buildListAutoContinueSnapshot(opts: {
  listId: string;
  instrumentIds: string[];
  nextIndex: number;
  board: ListAutoBoardState;
  freshnessMemory?: Map<string, string> | Record<string, string>;
  at?: string;
}): ListAutoContinueSnapshotV1 | null {
  if (opts.nextIndex < 0 || opts.nextIndex >= opts.instrumentIds.length) return null;
  if (opts.instrumentIds.length === 0) return null;
  const freshnessMemory =
    opts.freshnessMemory instanceof Map
      ? Object.fromEntries(opts.freshnessMemory.entries())
      : opts.freshnessMemory;
  return {
    version: 1,
    savedAt: opts.at ?? new Date().toISOString(),
    listId: opts.listId,
    instrumentIds: [...opts.instrumentIds],
    nextIndex: opts.nextIndex,
    board: {
      ...opts.board,
      aborted: false,
      done: false,
      paused: false,
      currentIndex: opts.nextIndex,
      rows: opts.board.rows.map((r) => ({ ...r })),
    },
    freshnessMemory,
  };
}

export function parseListAutoContinueSnapshot(
  raw: unknown,
): ListAutoContinueSnapshotV1 | null {
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Partial<ListAutoContinueSnapshotV1>;
  if (o.version !== 1) return null;
  if (typeof o.listId !== 'string' || !o.listId) return null;
  if (!Array.isArray(o.instrumentIds) || o.instrumentIds.length === 0) return null;
  if (typeof o.nextIndex !== 'number' || o.nextIndex < 0) return null;
  if (o.nextIndex >= o.instrumentIds.length) return null;
  if (!o.board || typeof o.board !== 'object' || !Array.isArray(o.board.rows)) return null;
  return {
    version: 1,
    savedAt: typeof o.savedAt === 'string' ? o.savedAt : new Date().toISOString(),
    listId: o.listId,
    instrumentIds: o.instrumentIds.map(String),
    nextIndex: o.nextIndex,
    board: {
      listId: String(o.board.listId ?? o.listId),
      currentIndex: o.nextIndex,
      aborted: false,
      done: false,
      paused: false,
      rows: o.board.rows as ListAutoBoardRow[],
    },
    freshnessMemory:
      o.freshnessMemory && typeof o.freshnessMemory === 'object'
        ? (o.freshnessMemory as Record<string, string>)
        : undefined,
  };
}

export function saveListAutoContinueSnapshot(snap: ListAutoContinueSnapshotV1): void {
  try {
    localStorage.setItem(LIST_AUTO_CONTINUE_STORAGE_KEY, JSON.stringify(snap));
  } catch {
    // ignore
  }
}

export function loadListAutoContinueSnapshot(): ListAutoContinueSnapshotV1 | null {
  try {
    const raw = localStorage.getItem(LIST_AUTO_CONTINUE_STORAGE_KEY);
    if (!raw) return null;
    return parseListAutoContinueSnapshot(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function clearListAutoContinueSnapshot(): void {
  try {
    localStorage.removeItem(LIST_AUTO_CONTINUE_STORAGE_KEY);
  } catch {
    // ignore
  }
}

/**
 * ¿El próximo Play debe continuar tras un Stop en esta lista?
 * Devuelve el snapshot solo si listId + cola de ids coinciden.
 */
export function matchListAutoContinueSnapshot(
  snap: ListAutoContinueSnapshotV1 | null,
  opts: { listId: string; instrumentIds: string[] },
): ListAutoContinueSnapshotV1 | null {
  if (!snap) return null;
  if (snap.listId !== opts.listId) return null;
  if (!sameIdList(snap.instrumentIds, opts.instrumentIds)) return null;
  if (snap.nextIndex >= opts.instrumentIds.length) return null;
  return snap;
}

/**
 * Tablero tras Stop→Play: conserva filas ya settled; desde nextIndex en cola.
 */
export function boardFromContinueSnapshot(
  snap: ListAutoContinueSnapshotV1,
): ListAutoBoardState {
  const nextIndex = snap.nextIndex;
  return {
    listId: snap.listId,
    currentIndex: nextIndex,
    aborted: false,
    done: false,
    paused: false,
    rows: snap.board.rows.map((row) => {
      if (row.index < nextIndex) {
        if (
          row.phase === 'saved' ||
          row.phase === 'omitted' ||
          row.phase === 'same' ||
          row.phase === 'skipped'
        ) {
          return { ...row };
        }
        return {
          ...row,
          phase: 'omitted',
          detail: 'continuación · ya pasado',
          change: 'same',
          settleReason: 'skip_fresh',
        };
      }
      return {
        ...row,
        phase: 'queued',
        detail: undefined,
        settleReason: undefined,
        change: 'unknown',
        beforeTopKey: undefined,
        afterTopKey: undefined,
      };
    }),
  };
}

