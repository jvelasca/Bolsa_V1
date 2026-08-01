/**
 * Tablero de progreso Lista AUTO — estado puro por instrumento.
 *
 * Una fila por ticker: cola → en curso → settle
 * (saved / igual / omitido-fresco / skip) + Δ Finalistas.
 *
 * UI: `backtest-list-auto-board-panel.tsx`.
 * Orquestación: `backtests-page.tsx` (queue / settle / pause / stop).
 *
 * @see docs/engineering/research-lifecycle.md § Lista AUTO
 */

import type { FullCycleSettleReason } from '@/features/backtests/backtest-list-auto';
import type { CoreRJudgment } from '@/features/backtests/core-r-judgment';

export type ListAutoRowPhase =
  | 'queued'
  | 'running'
  | 'saved'
  | 'same'
  | 'omitted'
  | 'skipped'
  | 'aborted';

/** Δ Finalistas respecto al TOP previo al ciclo de ese ticker. */
export type ListAutoChangeKind = 'unknown' | 'changed' | 'same' | 'new';

export type ListAutoBoardRow = {
  instrumentId: string;
  symbol: string;
  name?: string;
  index: number;
  phase: ListAutoRowPhase;
  settleReason?: FullCycleSettleReason;
  detail?: string;
  beforeTopKey?: string | null;
  afterTopKey?: string | null;
  change: ListAutoChangeKind;
  /** ISO última búsqueda (stamp frescura), si se conoce. */
  lastSearchAt?: string | null;
  /** CORE-R: juicio post-settle (no pisa TOP). */
  reeval?: CoreRJudgment | null;
};

export type ListAutoBoardState = {
  listId: string;
  rows: ListAutoBoardRow[];
  currentIndex: number;
  aborted: boolean;
  done: boolean;
  paused: boolean;
};

export type ListAutoBoardSeed = {
  instrumentId: string;
  symbol: string;
  name?: string;
};

/** Fingerprint ligero del TOP para detectar cambio de Finalistas. */
export function listAutoTopFingerprint(
  top:
    | {
        status?: string | null;
        slots?: ReadonlyArray<{
          strategyDefinitionId?: string | null;
          stars?: number | null;
        }> | null;
      }
    | null
    | undefined,
): string | null {
  if (!top?.slots?.length) return null;
  const parts = top.slots.map(
    (s) => `${s.strategyDefinitionId ?? ''}:${s.stars ?? ''}`,
  );
  return `${top.status ?? '?'}|${parts.join(',')}`;
}

export function resolveListAutoChange(opts: {
  reason: FullCycleSettleReason;
  beforeTopKey?: string | null;
  afterTopKey?: string | null;
}): ListAutoChangeKind {
  if (opts.reason === 'saved') {
    if (!opts.beforeTopKey) return 'new';
    return 'changed';
  }
  // skip_lab / skip_finalists / skip_fresh → TOP intacto
  return 'same';
}

export function phaseFromSettleReason(
  reason: FullCycleSettleReason,
): ListAutoRowPhase {
  if (reason === 'saved') return 'saved';
  if (reason === 'skip_lab') return 'skipped';
  if (reason === 'skip_fresh') return 'omitted';
  return 'same';
}

export function createListAutoBoard(opts: {
  listId: string;
  instruments: ListAutoBoardSeed[];
}): ListAutoBoardState {
  return {
    listId: opts.listId,
    currentIndex: 0,
    aborted: false,
    done: false,
    paused: false,
    rows: opts.instruments.map((inst, index) => ({
      instrumentId: inst.instrumentId,
      symbol: inst.symbol,
      name: inst.name,
      index,
      phase: 'queued',
      change: 'unknown',
    })),
  };
}

/** Actualiza symbol/name cuando llegan quotes (evita IDs truncados en columna VALOR). */
export function enrichListAutoBoardLabels(
  board: ListAutoBoardState,
  labels: Record<string, { symbol: string; name?: string | null }>,
): ListAutoBoardState {
  let changed = false;
  const rows = board.rows.map((row) => {
    const label = labels[row.instrumentId];
    if (!label?.symbol) return row;
    const nextName = label.name ?? row.name;
    if (row.symbol === label.symbol && (row.name ?? undefined) === (nextName ?? undefined)) {
      return row;
    }
    changed = true;
    return {
      ...row,
      symbol: label.symbol,
      name: nextName ?? undefined,
    };
  });
  return changed ? { ...board, rows } : board;
}

export function markListAutoBoardRunning(
  board: ListAutoBoardState,
  index: number,
): ListAutoBoardState {
  return {
    ...board,
    currentIndex: index,
    done: false,
    paused: false,
    rows: board.rows.map((row) => {
      if (row.index === index) {
        return {
          ...row,
          phase: 'running',
          detail: 'Universo → Coach → Lab…',
          settleReason: undefined,
          change: 'unknown',
          reeval: undefined,
        };
      }
      if (row.phase === 'running') {
        return { ...row, phase: 'queued', detail: undefined };
      }
      return row;
    }),
  };
}

/** Captura TOP previo una sola vez (antes de que el ciclo lo reescriba). */
export function captureListAutoBeforeTop(
  board: ListAutoBoardState,
  index: number,
  beforeTopKey: string | null,
): ListAutoBoardState {
  return {
    ...board,
    rows: board.rows.map((row) => {
      if (row.index !== index) return row;
      if (row.beforeTopKey !== undefined) return row;
      return { ...row, beforeTopKey };
    }),
  };
}

export function markListAutoBoardSettled(
  board: ListAutoBoardState,
  index: number,
  reason: FullCycleSettleReason,
  opts?: {
    detail?: string;
    afterTopKey?: string | null;
    lastSearchAt?: string | null;
    reeval?: CoreRJudgment | null;
  },
): ListAutoBoardState {
  const row = board.rows[index];
  const beforeTopKey = row?.beforeTopKey;
  const afterTopKey =
    opts?.afterTopKey !== undefined ? opts.afterTopKey : row?.afterTopKey ?? null;
  const change = resolveListAutoChange({
    reason,
    beforeTopKey,
    afterTopKey,
  });
  const phase = phaseFromSettleReason(reason);

  return {
    ...board,
    rows: board.rows.map((r) =>
      r.index === index
        ? {
            ...r,
            phase,
            settleReason: reason,
            detail: opts?.detail ?? r.detail,
            afterTopKey,
            change,
            lastSearchAt:
              opts?.lastSearchAt !== undefined ? opts.lastSearchAt : r.lastSearchAt,
            reeval: opts?.reeval !== undefined ? opts.reeval : r.reeval,
          }
        : r,
    ),
  };
}

export function markListAutoBoardPaused(
  board: ListAutoBoardState,
  paused: boolean,
): ListAutoBoardState {
  return { ...board, paused };
}

export function markListAutoBoardDone(
  board: ListAutoBoardState,
): ListAutoBoardState {
  return { ...board, done: true, paused: false, currentIndex: board.rows.length };
}

export function markListAutoBoardAborted(
  board: ListAutoBoardState,
): ListAutoBoardState {
  return {
    ...board,
    aborted: true,
    done: true,
    paused: false,
    rows: board.rows.map((row) =>
      row.phase === 'queued' || row.phase === 'running'
        ? { ...row, phase: 'aborted', detail: 'Stop', change: 'unknown' }
        : row,
    ),
  };
}

export function listAutoBoardProgress(board: ListAutoBoardState): {
  doneCount: number;
  total: number;
  pct: number;
  changedCount: number;
  sameCount: number;
  skippedCount: number;
  omittedCount: number;
} {
  const total = board.rows.length;
  const settled = board.rows.filter((r) =>
    ['saved', 'same', 'skipped', 'omitted'].includes(r.phase),
  );
  const doneCount = settled.length;
  const pct = total === 0 ? 0 : Math.round((doneCount / total) * 100);
  return {
    doneCount,
    total,
    pct,
    changedCount: board.rows.filter((r) => r.change === 'changed' || r.change === 'new')
      .length,
    sameCount: board.rows.filter(
      (r) => r.change === 'same' && r.phase !== 'skipped' && r.phase !== 'omitted',
    ).length,
    skippedCount: board.rows.filter((r) => r.phase === 'skipped').length,
    omittedCount: board.rows.filter((r) => r.phase === 'omitted').length,
  };
}

export function listAutoPhaseLabel(phase: ListAutoRowPhase): string {
  switch (phase) {
    case 'queued':
      return 'En cola';
    case 'running':
      return 'En curso';
    case 'saved':
      return 'Finalistas';
    case 'same':
      return 'Sin cambio';
    case 'omitted':
      return 'Omitido';
    case 'skipped':
      return 'Skip Lab';
    case 'aborted':
      return 'Anulado (Stop)';
    default:
      return phase;
  }
}

export function listAutoChangeLabel(change: ListAutoChangeKind): string {
  switch (change) {
    case 'changed':
      return 'Cambió';
    case 'new':
      return 'Nuevo TOP';
    case 'same':
      return 'Igual';
    default:
      return '—';
  }
}
