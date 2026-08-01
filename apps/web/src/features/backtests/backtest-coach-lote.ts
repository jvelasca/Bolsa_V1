/**
 * Identidad y reutilización del lote Coach (sin re-simular si no cambió el contexto).
 */

import { STRATEGY_MATRIX_MAX_SELECTED } from '@/features/backtests/backtest-strategy-matrix';

export type CoachLoteRowSnapshot = {
  rowId: string;
  status: string;
  runId?: string;
};

export function buildCoachBatteryFingerprint(opts: {
  /** instrument|period|cash|costs|TF */
  contextFingerprint: string;
  targetRowIds: readonly string[];
}): string {
  const ids = [...new Set(opts.targetRowIds.filter(Boolean))].sort().join(',');
  return `${opts.contextFingerprint}|ids:${ids}`;
}

export function canReuseCoachLote(opts: {
  preferReuse: boolean;
  fingerprint: string;
  lastFingerprint: string | null | undefined;
  rows: readonly CoachLoteRowSnapshot[];
  targetRowIds: readonly string[];
  forceResim?: boolean;
}): { reuse: boolean; reason: string } {
  if (!opts.preferReuse) return { reuse: false, reason: 'prefs_off' };
  if (opts.forceResim) return { reuse: false, reason: 'force' };
  if (opts.targetRowIds.length === 0) return { reuse: false, reason: 'empty' };
  if (!opts.lastFingerprint || opts.lastFingerprint !== opts.fingerprint) {
    return { reuse: false, reason: 'fingerprint_mismatch' };
  }
  const byId = new Map(opts.rows.map((r) => [r.rowId, r]));
  for (const id of opts.targetRowIds) {
    const row = byId.get(id);
    if (!row || row.status !== 'ok' || !row.runId) {
      return { reuse: false, reason: 'incomplete_ok' };
    }
  }
  return { reuse: true, reason: 'ok' };
}

/** Universo: genéricas ± Finalistas del valor ± Mis estrategias, tope matriz. */
export function mergeUniverseTargetIds(opts: {
  presetIds: readonly string[];
  /** `saved:<strategyDefinitionId>` de Finalistas del instrumento. */
  finalistRowIds?: readonly string[];
  includeFinalists?: boolean;
  savedRowIds: readonly string[];
  includeMine: boolean;
  max?: number;
}): string[] {
  const max = opts.max ?? STRATEGY_MATRIX_MAX_SELECTED;
  const out: string[] = [];
  const seen = new Set<string>();
  const push = (id: string) => {
    if (!id || seen.has(id) || out.length >= max) return;
    out.push(id);
    seen.add(id);
  };
  for (const id of opts.presetIds) push(id);
  if (opts.includeFinalists) {
    for (const id of opts.finalistRowIds ?? []) push(id);
  }
  if (opts.includeMine) {
    for (const id of opts.savedRowIds) push(id);
  }
  return out;
}

/** RowIds de matriz para slots Finalistas del valor. */
export function finalistMatrixRowIds(
  slots: readonly { strategyDefinitionId?: string | null }[],
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const s of slots) {
    const id = s.strategyDefinitionId?.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(`saved:${id}`);
  }
  return out;
}
