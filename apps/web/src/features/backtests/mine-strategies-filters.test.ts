import { describe, expect, it } from 'vitest';

import {
  defaultMineStrategiesFilters,
  filterMineStrategies,
  formatStrategyScopeBadge,
  isMineStrategiesFilterActive,
  strategyScopeKind,
} from '@/features/backtests/mine-strategies-filters';

const rows = [
  {
    id: '1',
    name: 'SMA cruz genérica',
    presetKey: 'sma_cross',
    kind: 'indicator_signals',
    timeframe: '1d',
    origin: 'manual',
    instrumentIds: [] as string[],
  },
  {
    id: '2',
    name: 'RSI AAPL lab',
    presetKey: 'rsi_mean_reversion',
    kind: 'indicator_signals',
    timeframe: '1h',
    origin: 'assisted',
    instrumentIds: ['inst-aapl'],
  },
  {
    id: '3',
    name: 'MACD multi',
    kind: 'indicator_signals',
    timeframe: '1d',
    origin: 'ai_generated',
    instrumentIds: ['inst-aapl', 'inst-msft'],
  },
];

describe('strategyScopeKind', () => {
  it('empty = reusable', () => {
    expect(strategyScopeKind([])).toBe('reusable');
    expect(strategyScopeKind(null)).toBe('reusable');
    expect(strategyScopeKind(undefined)).toBe('reusable');
  });

  it('non-empty = fitted', () => {
    expect(strategyScopeKind(['x'])).toBe('fitted');
  });
});

describe('filterMineStrategies', () => {
  it('filters by scope reusable / fitted', () => {
    expect(
      filterMineStrategies(rows, { ...defaultMineStrategiesFilters(), scope: 'reusable' }).map(
        (r) => r.id,
      ),
    ).toEqual(['1']);
    expect(
      filterMineStrategies(rows, { ...defaultMineStrategiesFilters(), scope: 'fitted' }).map(
        (r) => r.id,
      ),
    ).toEqual(['2', '3']);
  });

  it('filters fitted_current by instrument', () => {
    expect(
      filterMineStrategies(
        rows,
        { ...defaultMineStrategiesFilters(), scope: 'fitted_current' },
        { currentInstrumentId: 'inst-aapl' },
      ).map((r) => r.id),
    ).toEqual(['2', '3']);
    expect(
      filterMineStrategies(
        rows,
        { ...defaultMineStrategiesFilters(), scope: 'fitted_current' },
        { currentInstrumentId: 'inst-other' },
      ),
    ).toHaveLength(0);
  });

  it('filters by timeframe, origin and query', () => {
    expect(
      filterMineStrategies(rows, {
        ...defaultMineStrategiesFilters(),
        timeframe: '1h',
      }).map((r) => r.id),
    ).toEqual(['2']);
    expect(
      filterMineStrategies(rows, {
        ...defaultMineStrategiesFilters(),
        origin: 'ai_generated',
      }).map((r) => r.id),
    ).toEqual(['3']);
    expect(
      filterMineStrategies(rows, {
        ...defaultMineStrategiesFilters(),
        query: 'aapl',
      }).map((r) => r.id),
    ).toEqual(['2', '3']);
  });
});

describe('formatStrategyScopeBadge', () => {
  it('labels reusable and fitted', () => {
    const symbols = new Map([
      ['inst-aapl', 'AAPL'],
      ['inst-msft', 'MSFT'],
    ]);
    expect(formatStrategyScopeBadge([], symbols)).toBe('Reutilizable');
    expect(formatStrategyScopeBadge(['inst-aapl'], symbols)).toBe('Ajuste · AAPL');
    expect(formatStrategyScopeBadge(['inst-aapl', 'inst-msft'], symbols)).toBe(
      'Ajuste · 2 valores',
    );
  });
});

describe('isMineStrategiesFilterActive', () => {
  it('detects non-default filters', () => {
    expect(isMineStrategiesFilterActive(defaultMineStrategiesFilters())).toBe(false);
    expect(
      isMineStrategiesFilterActive({ ...defaultMineStrategiesFilters(), query: 'x' }),
    ).toBe(true);
  });
});
