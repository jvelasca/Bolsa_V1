import { describe, expect, it } from 'vitest';
import { annotateStrategyMatrixRowsWithTop } from '@/features/backtests/backtest-strategy-matrix';
import type { StrategyMatrixRow } from '@/features/backtests/backtest-strategy-matrix';

function row(partial: Partial<StrategyMatrixRow> & Pick<StrategyMatrixRow, 'rowId' | 'kind'>): StrategyMatrixRow {
  return {
    label: partial.rowId,
    subtitle: '',
    status: 'idle',
    ...partial,
  };
}

describe('annotateStrategyMatrixRowsWithTop', () => {
  it('marca saved finalistas y rellena presetKey desde el slot (sin duplicar la genérica)', () => {
    const rows = [
      row({
        rowId: 'saved:abc',
        kind: 'saved',
        strategyDefinitionId: 'abc',
      }),
      row({
        rowId: 'preset:golden_cross',
        kind: 'preset',
        presetKey: 'golden_cross',
      }),
    ];
    const annotated = annotateStrategyMatrixRowsWithTop(rows, {
      slots: [
        {
          rank: 1,
          strategyDefinitionId: 'abc',
          strategyType: 'golden_cross',
        },
      ],
    });
    expect(annotated[0]?.topRank).toBe(1);
    expect(annotated[0]?.presetKey).toBe('golden_cross');
    // La genérica equivalente NO es finalista (evita 3→6)
    expect(annotated[1]?.topRank).toBeUndefined();
  });

  it('también marca genéricas por strategyType cuando el slot no tiene def', () => {
    const rows = [
      row({
        rowId: 'preset:macd_signal_cross',
        kind: 'preset',
        presetKey: 'macd_signal_cross',
      }),
    ];
    const annotated = annotateStrategyMatrixRowsWithTop(rows, {
      slots: [{ rank: 2, strategyType: 'macd_signal_cross' }],
    });
    expect(annotated[0]?.topRank).toBe(2);
  });
});
