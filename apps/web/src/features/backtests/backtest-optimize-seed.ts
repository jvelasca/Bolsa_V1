import {
  BACKTEST_STRATEGIES,
  presetIndicatorSpecs,
  type BacktestStrategyType,
  type ChartTimeframe,
  type OptimizeStrategyFamily,
} from '@bolsa/shared';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import {
  suggestOptimizeValidation,
  type OptimizeValidationHint,
} from '@/features/backtests/backtest-optimize-validation-hint';

/** Seed for guided optimize — prefill Jobs from explore or a run. */
export type OptimizeSeed = {
  instrumentId: string;
  symbol?: string;
  strategyType: BacktestStrategyType;
  strategyLabel: string;
  initialCash: number;
  timeframe: ChartTimeframe;
  /** Prefer matching explore/run window (optimize API uses barLimit today). */
  barLimit?: number;
  sourceRunId?: string;
  /** true = beat B&H; false = did not; null = unknown */
  beatBuyHold?: boolean | null;
  source: 'explore_best' | 'explore_row' | 'result';
  /** Prefill hold-out / WF from bar count (P6). */
  validationHint?: OptimizeValidationHint;
  /** Original operative metrics — used as comparison anchor. */
  anchorFast?: number;
  anchorSlow?: number;
  anchorSignal?: number;
  anchorPeriod?: number;
  anchorOversold?: number;
  anchorOverbought?: number;
  anchorReturnPct?: number;
  anchorMaxDrawdownPct?: number;
  anchorTradeCount?: number;
  anchorScore?: number;
};

export type { OptimizeValidationHint };
export { suggestOptimizeValidation };

export function optimizeFamilyForStrategy(
  strategyType: BacktestStrategyType | string,
): OptimizeStrategyFamily | null {
  // Dual-MA / trend grids → lab SMA (periodos). Incluye Death/Golden cross y EMA como ancla.
  if (
    strategyType === 'sma_crossover' ||
    strategyType === 'golden_cross' ||
    strategyType === 'death_cross' ||
    strategyType === 'ema_crossover' ||
    strategyType === 'ma_stack_bullish' ||
    strategyType === 'price_above_sma200' ||
    strategyType === 'bollinger_upper_breakout' ||
    strategyType === 'donchian_breakout' ||
    strategyType === 'adx_di_trend' ||
    strategyType === 'ichimoku_tk_cross' ||
    strategyType === 'vwap_reclaim' ||
    strategyType === 'supertrend_follow'
  ) {
    return 'sma_crossover';
  }
  if (
    strategyType === 'rsi_mean_reversion' ||
    strategyType === 'rsi_momentum' ||
    strategyType === 'rsi_oversold_bounce' ||
    strategyType === 'pullback_in_uptrend' ||
    strategyType === 'stoch_oversold' ||
    strategyType === 'cci_oversold' ||
    strategyType === 'bollinger_lower_bounce'
  ) {
    return 'rsi_mean_reversion';
  }
  if (strategyType === 'macd_signal_cross' || strategyType === 'macd_zero_line') {
    return 'macd_signal_cross';
  }
  return null;
}

/**
 * Nota honesta cuando el lab usa una familia genérica (SMA/RSI/MACD)
 * como aproximación al preset del coach.
 */
export function optimizeFamilyProxyNote(
  strategyType: BacktestStrategyType | string,
): string | null {
  switch (strategyType) {
    case 'death_cross':
      return 'Death cross: el lab busca periodos de medias (como Golden/SMA). La señal bajista del preset se traduce aquí a un grid de cruce de medias; revisa el Mejor antes de adoptar.';
    case 'ema_crossover':
      return 'Cruce EMA: el motor de optimizar usa rejilla SMA con los periodos del EMA (12/26 u ancla). Es la aproximación soportada hoy.';
    case 'ma_stack_bullish':
      return 'Apilamiento MA: se optimizan las dos medias rápidas (p. ej. 20/50); el filtro SMA200 no entra en el grid.';
    case 'pullback_in_uptrend':
      return 'Pullback: el lab optimiza la pata RSI (periodo / umbrales); el filtro SMA50 queda fuera del grid.';
    case 'stoch_oversold':
      return 'Estocástico: aproximación con rejilla RSI (umbrales tipo sobreventa/sobrecompra). No es un grid Stoch nativo.';
    case 'cci_oversold':
      return 'CCI: aproximación con rejilla RSI (periodo + umbrales). Los niveles CCI (−100/0) no se mapean 1:1.';
    case 'bollinger_lower_bounce':
      return 'Rebote banda inferior: sin grid Bollinger nativo. El lab usa RSI (mean-reversion) como proxy; no es el mismo sistema.';
    case 'bollinger_upper_breakout':
      return 'Rotura banda superior: sin grid Bollinger nativo. El lab usa cruce SMA como proxy de impulso; revisa el Mejor.';
    case 'price_above_sma200':
      return 'Precio > SMA200: el lab busca un cruce de medias anclado en torno a 50/200 (proxy de tendencia larga).';
    case 'donchian_breakout':
      return 'Donchian: sin grid de canal nativo. El lab usa cruce SMA como proxy de breakout/tendencia.';
    case 'adx_di_trend':
      return 'ADX/+DI: sin grid ADX nativo. El lab usa cruce SMA como proxy de tendencia con fuerza.';
    case 'ichimoku_tk_cross':
      return 'Ichimoku: el lab aproxima Tenkan/Kijun con un cruce de medias (p. ej. 9/26); la nube queda fuera del grid.';
    case 'vwap_reclaim':
      return 'VWAP: sin grid VWAP nativo. El lab usa cruce SMA corto como proxy de recuperación de nivel.';
    case 'supertrend_follow':
      return 'SuperTrend: sin grid ATR nativo. El lab usa cruce SMA como proxy de seguimiento de tendencia.';
    default:
      return null;
  }
}

/** @deprecated use optimizeFamilyForStrategy */
export function isSmaGridOptimizable(strategyType: BacktestStrategyType): boolean {
  return optimizeFamilyForStrategy(strategyType) === 'sma_crossover';
}

export function isOptimizableStrategy(strategyType: BacktestStrategyType | string): boolean {
  return optimizeFamilyForStrategy(strategyType) != null;
}

export function smaAnchorPeriods(
  strategyType: BacktestStrategyType,
): { fast: number; slow: number } | null {
  if (optimizeFamilyForStrategy(strategyType) !== 'sma_crossover') return null;
  if (strategyType === 'price_above_sma200') {
    return { fast: 50, slow: 200 };
  }
  if (strategyType === 'bollinger_upper_breakout') {
    // Proxy: BB period 20 → cruce corto alrededor de esa escala.
    return { fast: 10, slow: 20 };
  }
  if (strategyType === 'donchian_breakout') {
    return { fast: 10, slow: 20 };
  }
  if (strategyType === 'adx_di_trend') {
    return { fast: 14, slow: 28 };
  }
  if (strategyType === 'ichimoku_tk_cross') {
    return { fast: 9, slow: 26 };
  }
  if (strategyType === 'vwap_reclaim') {
    return { fast: 10, slow: 20 };
  }
  if (strategyType === 'supertrend_follow') {
    return { fast: 10, slow: 20 };
  }
  const specs = presetIndicatorSpecs(strategyType);
  // SMA o EMA (ema_crossover se ancla con los mismos periodos en el grid SMA).
  const periods = specs
    .filter((spec) => spec.definitionId === 'sma' || spec.definitionId === 'ema')
    .map((spec) => Number(spec.parameters.period))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (periods.length < 2) return null;
  const sorted = [...periods].sort((a, b) => a - b);
  // ma_stack tiene 20/50/200 → usar las dos más rápidas para el cruce.
  return { fast: sorted[0]!, slow: sorted[1]! };
}

export function rsiAnchorParams(
  strategyType: BacktestStrategyType,
): { period: number; oversold: number; overbought: number } | null {
  if (optimizeFamilyForStrategy(strategyType) !== 'rsi_mean_reversion') return null;
  const specs = presetIndicatorSpecs(strategyType);
  const rsi = specs.find((spec) => spec.definitionId === 'rsi');
  const stoch = specs.find((spec) => spec.definitionId === 'stoch');
  const cci = specs.find((spec) => spec.definitionId === 'cci');

  if (strategyType === 'stoch_oversold') {
    const period = Number(stoch?.parameters.kPeriod ?? 14);
    return {
      period: Number.isFinite(period) ? period : 14,
      oversold: 20,
      overbought: 80,
    };
  }
  if (strategyType === 'cci_oversold') {
    const period = Number(cci?.parameters.period ?? 20);
    // CCI −100/0 no cabe en RSI 0–100: ancla RSI clásica alrededor del periodo CCI.
    return {
      period: Number.isFinite(period) ? period : 20,
      oversold: 30,
      overbought: 70,
    };
  }
  if (strategyType === 'pullback_in_uptrend') {
    const period = Number(rsi?.parameters.period ?? 14);
    return {
      period: Number.isFinite(period) ? period : 14,
      oversold: 42,
      overbought: 65,
    };
  }
  if (strategyType === 'bollinger_lower_bounce') {
    // Proxy mean-reversion: periodo BB (20) → RSI clásico.
    return { period: 20, oversold: 30, overbought: 70 };
  }
  if (strategyType === 'rsi_oversold_bounce') {
    const period = Number(rsi?.parameters.period ?? 14);
    return {
      period: Number.isFinite(period) ? period : 14,
      oversold: 30,
      overbought: 55,
    };
  }

  const period = Number(rsi?.parameters.period ?? 14);
  return {
    period: Number.isFinite(period) ? period : 14,
    oversold: 30,
    overbought: 70,
  };
}

export function macdAnchorParams(
  strategyType: BacktestStrategyType,
): { fast: number; slow: number; signal: number } | null {
  if (optimizeFamilyForStrategy(strategyType) !== 'macd_signal_cross') return null;
  const macd = presetIndicatorSpecs(strategyType).find((spec) => spec.definitionId === 'macd');
  const fast = Number(macd?.parameters.fastPeriod ?? 12);
  const slow = Number(macd?.parameters.slowPeriod ?? 26);
  const signal = Number(macd?.parameters.signalPeriod ?? 9);
  return {
    fast: Number.isFinite(fast) ? fast : 12,
    slow: Number.isFinite(slow) ? slow : 26,
    signal: Number.isFinite(signal) ? signal : 9,
  };
}

function uniqueSorted(values: number[]): number[] {
  return [...new Set(values.filter((v) => Number.isFinite(v) && v >= 2))]
    .map((v) => Math.round(v))
    .sort((a, b) => a - b);
}

/** Neighbourhood grid around catalog defaults (honest, not a mega-search). */
export function buildSmaPeriodLists(strategyType: BacktestStrategyType): {
  fastPeriods: string;
  slowPeriods: string;
  anchorFast: number;
  anchorSlow: number;
} {
  const anchor = smaAnchorPeriods(strategyType) ?? { fast: 20, slow: 50 };
  const longHorizon =
    strategyType === 'golden_cross' || strategyType === 'death_cross';
  const fastOffsets = longHorizon ? [-20, -10, 0, 10, 20] : [-10, -5, 0, 5, 10];
  const slowOffsets = longHorizon
    ? [-50, -20, 0, 20, 50]
    : [-20, -10, 0, 10, 20, 30];

  const fast = uniqueSorted(fastOffsets.map((d) => anchor.fast + d));
  const slow = uniqueSorted(
    slowOffsets
      .map((d) => anchor.slow + d)
      .filter((value) => value > Math.min(...fast)),
  );

  return {
    fastPeriods: fast.join(','),
    slowPeriods: slow.join(','),
    anchorFast: anchor.fast,
    anchorSlow: anchor.slow,
  };
}

function scoreFrom(ret?: number, dd?: number): number | undefined {
  if (ret == null || dd == null || !Number.isFinite(ret) || !Number.isFinite(dd)) {
    return undefined;
  }
  return ret - dd * 0.25;
}

export function buildOptimizeSeedFromExploreRow(
  row: ExplorePresetRow,
  opts: {
    instrumentId: string;
    symbol?: string;
    initialCash: number;
    timeframe: ChartTimeframe;
    barLimit?: number;
    source: OptimizeSeed['source'];
  },
): OptimizeSeed {
  const family = optimizeFamilyForStrategy(row.strategyType);
  const sma = family === 'sma_crossover' ? smaAnchorPeriods(row.strategyType) : null;
  const rsi = family === 'rsi_mean_reversion' ? rsiAnchorParams(row.strategyType) : null;
  const macd = family === 'macd_signal_cross' ? macdAnchorParams(row.strategyType) : null;
  const ret = row.totalReturnPct;
  const dd = row.maxDrawdownPct;
  const barLimit = opts.barLimit ?? row.barCount;
  return {
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    strategyType: row.strategyType,
    strategyLabel: row.label,
    initialCash: opts.initialCash,
    timeframe: opts.timeframe,
    barLimit,
    sourceRunId: row.runId,
    beatBuyHold: row.excessReturnPct == null ? null : row.excessReturnPct > 0,
    source: opts.source,
    validationHint: suggestOptimizeValidation(barLimit),
    anchorFast: sma?.fast ?? macd?.fast,
    anchorSlow: sma?.slow ?? macd?.slow,
    anchorSignal: macd?.signal,
    anchorPeriod: rsi?.period,
    anchorOversold: rsi?.oversold,
    anchorOverbought: rsi?.overbought,
    anchorReturnPct: ret,
    anchorMaxDrawdownPct: dd,
    anchorTradeCount: row.tradeCount,
    anchorScore: scoreFrom(ret, dd),
  };
}

/** Pull numeric params from a research trial / manifest bag. */
export function anchorParamsFromTrialBag(params: Record<string, unknown> | null | undefined): {
  anchorFast?: number;
  anchorSlow?: number;
  anchorSignal?: number;
  anchorPeriod?: number;
  anchorOversold?: number;
  anchorOverbought?: number;
} {
  if (!params) return {};
  const num = (key: string) => {
    const value = params[key];
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  };
  return {
    anchorFast: num('fastPeriod'),
    anchorSlow: num('slowPeriod'),
    anchorSignal: num('signalPeriod'),
    anchorPeriod: num('period'),
    anchorOversold: num('oversold'),
    anchorOverbought: num('overbought'),
  };
}

export function buildOptimizeSeedFromRun(opts: {
  instrumentId: string;
  symbol?: string;
  strategyType: string;
  strategyLabel?: string;
  initialCash: number;
  timeframe: ChartTimeframe;
  barCount?: number;
  runId?: string;
  excessReturnPct?: number | null;
  totalReturnPct?: number;
  maxDrawdownPct?: number;
  tradeCount?: number;
  anchorFast?: number;
  anchorSlow?: number;
  anchorSignal?: number;
  anchorPeriod?: number;
  anchorOversold?: number;
  anchorOverbought?: number;
  /** Optional trial/definition params (optimized periods, RSI levels, …). */
  trialParams?: Record<string, unknown> | null;
}): OptimizeSeed {
  const fromTrial = anchorParamsFromTrialBag(opts.trialParams);
  const rawType = opts.strategyType;
  const known = (BACKTEST_STRATEGIES as Record<string, { label: string } | undefined>)[rawType];
  const strategyType = (known ? rawType : 'sma_crossover') as BacktestStrategyType;
  const strategyLabel =
    opts.strategyLabel ?? known?.label ?? (rawType ? String(rawType) : 'Estrategia');
  const family = optimizeFamilyForStrategy(strategyType) ?? 'sma_crossover';
  const catalogSma = family === 'sma_crossover' ? smaAnchorPeriods(strategyType) : null;
  const catalogRsi = family === 'rsi_mean_reversion' ? rsiAnchorParams(strategyType) : null;
  const catalogMacd = family === 'macd_signal_cross' ? macdAnchorParams(strategyType) : null;
  const ret = opts.totalReturnPct;
  const dd = opts.maxDrawdownPct;
  const barLimit = opts.barCount && opts.barCount > 0 ? opts.barCount : undefined;
  return {
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    strategyType,
    strategyLabel,
    initialCash: opts.initialCash,
    timeframe: opts.timeframe,
    barLimit,
    sourceRunId: opts.runId,
    beatBuyHold: opts.excessReturnPct == null ? null : opts.excessReturnPct > 0,
    source: 'result',
    validationHint: suggestOptimizeValidation(barLimit),
    anchorFast: opts.anchorFast ?? fromTrial.anchorFast ?? catalogSma?.fast ?? catalogMacd?.fast,
    anchorSlow: opts.anchorSlow ?? fromTrial.anchorSlow ?? catalogSma?.slow ?? catalogMacd?.slow,
    anchorSignal: opts.anchorSignal ?? fromTrial.anchorSignal ?? catalogMacd?.signal,
    anchorPeriod: opts.anchorPeriod ?? fromTrial.anchorPeriod ?? catalogRsi?.period,
    anchorOversold: opts.anchorOversold ?? fromTrial.anchorOversold ?? catalogRsi?.oversold,
    anchorOverbought: opts.anchorOverbought ?? fromTrial.anchorOverbought ?? catalogRsi?.overbought,
    anchorReturnPct: ret,
    anchorMaxDrawdownPct: dd,
    anchorTradeCount: opts.tradeCount,
    anchorScore: scoreFrom(ret, dd),
  };
}

export function suggestBarLimit(barCount: number | undefined, fallback = 500): number {
  if (barCount == null || !Number.isFinite(barCount) || barCount <= 0) return fallback;
  return Math.min(10_000, Math.max(50, Math.round(barCount)));
}
