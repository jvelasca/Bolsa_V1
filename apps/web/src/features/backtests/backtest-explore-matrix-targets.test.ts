import { describe, expect, it } from 'vitest';
import { resolveMatrixCoachTargetIds } from '@/features/backtests/backtest-explore-value';
import type { StrategyMatrixRow } from '@/features/backtests/backtest-strategy-matrix';

function row(
  partial: Pick<StrategyMatrixRow, 'rowId' | 'kind'> &
    Partial<StrategyMatrixRow> & { topRank?: 1 | 2 | 3 },
): StrategyMatrixRow {
  return {
    label: partial.rowId,
    subtitle: '',
    status: 'idle',
    ...partial,
  };
}

describe('resolveMatrixCoachTargetIds', () => {
  const rows: StrategyMatrixRow[] = [
    row({ rowId: 'preset:sma', kind: 'preset', presetKey: 'sma_crossover' }),
    row({ rowId: 'preset:rsi', kind: 'preset', presetKey: 'rsi_mean_reversion' }),
    row({
      rowId: 'saved:1',
      kind: 'saved',
      strategyDefinitionId: '1',
      topRank: 1,
    }),
  ];

  it('sin selección → todas las del filtro Finalistas', () => {
    const ids = resolveMatrixCoachTargetIds(rows, 'finalists', new Set());
    expect(ids).toEqual(['saved:1']);
  });

  it('sin selección → todas las Genéricas', () => {
    const ids = resolveMatrixCoachTargetIds(rows, 'preset', new Set());
    expect(ids).toEqual(['preset:sma', 'preset:rsi']);
  });

  it('con selección en el filtro → solo las marcadas', () => {
    const ids = resolveMatrixCoachTargetIds(
      rows,
      'preset',
      new Set(['preset:rsi', 'saved:1']),
    );
    expect(ids).toEqual(['preset:rsi']);
  });

  it('selección fuera del filtro se ignora → cae al lote del filtro', () => {
    const ids = resolveMatrixCoachTargetIds(rows, 'finalists', new Set(['preset:sma']));
    expect(ids).toEqual(['saved:1']);
  });
});
