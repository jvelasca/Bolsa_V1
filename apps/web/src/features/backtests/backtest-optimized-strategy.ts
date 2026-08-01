import type { ChartTimeframe, StrategyDefinitionV1 } from '@bolsa/shared';
import { DEFAULT_EXECUTION_MODEL } from '@bolsa/shared';

/** Suggest a distinct name so optimized variants don't collide with presets. */
export function suggestOptimizedSmaName(opts: {
  fastPeriod: number;
  slowPeriod: number;
  symbol?: string | null;
}): string {
  const symbol = opts.symbol?.trim() ? ` · ${opts.symbol.trim()}` : '';
  return `SMA ${opts.fastPeriod}/${opts.slowPeriod} · opt${symbol}`;
}

export function suggestOptimizedRsiName(opts: {
  period: number;
  oversold: number;
  overbought: number;
  symbol?: string | null;
}): string {
  const symbol = opts.symbol?.trim() ? ` · ${opts.symbol.trim()}` : '';
  return `RSI ${opts.period} · ${opts.oversold}/${opts.overbought} · opt${symbol}`;
}

export function suggestOptimizedMacdName(opts: {
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod: number;
  symbol?: string | null;
}): string {
  const symbol = opts.symbol?.trim() ? ` · ${opts.symbol.trim()}` : '';
  return `MACD ${opts.fastPeriod}/${opts.slowPeriod}/${opts.signalPeriod} · opt${symbol}`;
}

/** Build a reusable StrategyDefinitionV1 from an optimized SMA pair. */
export function strategyDefinitionFromOptimizedSma(opts: {
  name: string;
  fastPeriod: number;
  slowPeriod: number;
  timeframe?: ChartTimeframe;
  instrumentIds?: string[];
}): StrategyDefinitionV1 {
  const fast = opts.fastPeriod;
  const slow = opts.slowPeriod;
  const leftSpec = { definitionId: 'sma' as const, parameters: { period: fast } };
  const rightSpec = { definitionId: 'sma' as const, parameters: { period: slow } };

  return {
    id: `opt:sma:${fast}-${slow}`,
    version: 1,
    name: opts.name,
    kind: 'indicator_signals',
    // Keep presetKey for H0 engine compatibility; name/params mark it as optimized.
    presetKey: 'sma_crossover',
    universe: { instrumentIds: opts.instrumentIds ?? [] },
    timeframe: opts.timeframe ?? '1d',
    dataSnapshotPolicy: 'latest',
    entries: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_cross',
          leftSpec,
          rightSpec,
          direction: 'bullish',
          signalKind: 'entry_long',
        },
      ],
    },
    exits: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_cross',
          leftSpec,
          rightSpec,
          direction: 'bearish',
          signalKind: 'exit',
        },
      ],
    },
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: [leftSpec, rightSpec],
    execution: { ...DEFAULT_EXECUTION_MODEL },
    origin: 'manual',
  };
}

/** Build reusable StrategyDefinitionV1 from optimized RSI levels. */
export function strategyDefinitionFromOptimizedRsi(opts: {
  name: string;
  period: number;
  oversold: number;
  overbought: number;
  timeframe?: ChartTimeframe;
  instrumentIds?: string[];
}): StrategyDefinitionV1 {
  const period = opts.period;
  const oversold = opts.oversold;
  const overbought = opts.overbought;
  const rsiSpec = { definitionId: 'rsi' as const, parameters: { period } };

  return {
    id: `opt:rsi:${period}-${oversold}-${overbought}`,
    version: 1,
    name: opts.name,
    kind: 'indicator_signals',
    presetKey: 'rsi_mean_reversion',
    universe: { instrumentIds: opts.instrumentIds ?? [] },
    timeframe: opts.timeframe ?? '1d',
    dataSnapshotPolicy: 'latest',
    entries: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_compare',
          leftSpec: rsiSpec,
          operator: 'lt',
          rightValue: oversold,
          signalKind: 'entry_long',
        },
      ],
    },
    exits: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_compare',
          leftSpec: rsiSpec,
          operator: 'gt',
          rightValue: overbought,
          signalKind: 'exit',
        },
      ],
    },
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: [rsiSpec],
    execution: { ...DEFAULT_EXECUTION_MODEL },
    origin: 'manual',
  };
}

/** Build reusable StrategyDefinitionV1 from optimized MACD triple. */
export function strategyDefinitionFromOptimizedMacd(opts: {
  name: string;
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod: number;
  timeframe?: ChartTimeframe;
  instrumentIds?: string[];
}): StrategyDefinitionV1 {
  const fast = opts.fastPeriod;
  const slow = opts.slowPeriod;
  const signal = opts.signalPeriod;
  const mainSpec = {
    definitionId: 'macd' as const,
    parameters: { fastPeriod: fast, slowPeriod: slow, signalPeriod: signal, line: 'main' },
  };
  const signalSpec = {
    definitionId: 'macd' as const,
    parameters: { fastPeriod: fast, slowPeriod: slow, signalPeriod: signal, line: 'signal' },
  };

  return {
    id: `opt:macd:${fast}-${slow}-${signal}`,
    version: 1,
    name: opts.name,
    kind: 'indicator_signals',
    presetKey: 'macd_signal_cross',
    universe: { instrumentIds: opts.instrumentIds ?? [] },
    timeframe: opts.timeframe ?? '1d',
    dataSnapshotPolicy: 'latest',
    entries: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_cross',
          leftSpec: mainSpec,
          rightSpec: signalSpec,
          direction: 'bullish',
          signalKind: 'entry_long',
        },
      ],
    },
    exits: {
      operator: 'all',
      rules: [
        {
          type: 'indicator_cross',
          leftSpec: mainSpec,
          rightSpec: signalSpec,
          direction: 'bearish',
          signalKind: 'exit',
        },
      ],
    },
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: [mainSpec, signalSpec],
    execution: { ...DEFAULT_EXECUTION_MODEL },
    origin: 'manual',
  };
}

/** Estimate grid size for progress UI (fast×slow with fast < slow, capped). */
export function estimateOptimizeTrialTotal(
  fastPeriods: number[],
  slowPeriods: number[],
  maxTrials = 200,
): number {
  let count = 0;
  for (const fast of fastPeriods) {
    for (const slow of slowPeriods) {
      if (fast >= slow) continue;
      count += 1;
      if (count >= maxTrials) return maxTrials;
    }
  }
  return Math.max(1, count);
}
