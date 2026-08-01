/**
 * Catálogo de estrategias genéricas (fuente: `strategy-presets.json`).
 * Ampliación v2 (2026-07-28): +5 presets (Donchian, ADX, Ichimoku, VWAP, Supertrend).
 * Motor Python: `rules_engine._series_for_spec` + enum Prisma `BacktestStrategyType`.
 */

import catalogJson from './strategy-presets.json' with { type: 'json' };
import type { IndicatorSpec } from './research-platform.js';
import type { RuleGroupV1 } from './strategy-rules.js';

export type StrategyPresetCategory =
  | 'trend'
  | 'momentum'
  | 'mean_reversion'
  | 'volatility'
  | 'composite';

export interface StrategyPresetDefinition {
  label: string;
  description: string;
  category: StrategyPresetCategory;
  tags: string[];
  /** Preset apto como gate en rastreadores híbridos (P10). */
  hybridGate?: boolean;
  indicatorSpecs: IndicatorSpec[];
  entries: RuleGroupV1;
  exits: RuleGroupV1;
}

interface CatalogJson {
  version: number;
  presets: Record<string, StrategyPresetDefinition>;
}

const catalog = catalogJson as CatalogJson;

export type BacktestStrategyType =
  | 'sma_crossover'
  | 'rsi_mean_reversion'
  | 'ema_crossover'
  | 'golden_cross'
  | 'death_cross'
  | 'macd_signal_cross'
  | 'macd_zero_line'
  | 'rsi_momentum'
  | 'rsi_oversold_bounce'
  | 'stoch_oversold'
  | 'bollinger_lower_bounce'
  | 'bollinger_upper_breakout'
  | 'price_above_sma200'
  | 'ma_stack_bullish'
  | 'pullback_in_uptrend'
  | 'cci_oversold'
  | 'donchian_breakout'
  | 'adx_di_trend'
  | 'ichimoku_tk_cross'
  | 'vwap_reclaim'
  | 'supertrend_follow';

export const STRATEGY_PRESET_KEYS = Object.keys(catalog.presets) as BacktestStrategyType[];

export const STRATEGY_PRESET_CATALOG = catalog.presets as Record<
  BacktestStrategyType,
  StrategyPresetDefinition
>;

/** Presets marcados con hybridGate en strategy-presets.json. */
export const HYBRID_GATE_PRESET_KEYS = STRATEGY_PRESET_KEYS.filter(
  (key) => STRATEGY_PRESET_CATALOG[key]?.hybridGate === true,
);

export const BACKTEST_STRATEGIES: Record<
  BacktestStrategyType,
  { label: string; description: string; category: StrategyPresetCategory; tags: string[] }
> = Object.fromEntries(
  STRATEGY_PRESET_KEYS.map((key) => [
    key,
    {
      label: STRATEGY_PRESET_CATALOG[key].label,
      description: STRATEGY_PRESET_CATALOG[key].description,
      category: STRATEGY_PRESET_CATALOG[key].category,
      tags: STRATEGY_PRESET_CATALOG[key].tags,
    },
  ]),
) as Record<
  BacktestStrategyType,
  { label: string; description: string; category: StrategyPresetCategory; tags: string[] }
>;

export const STRATEGY_PRESET_CATEGORY_LABELS: Record<StrategyPresetCategory, string> = {
  trend: 'Tendencia',
  momentum: 'Momentum',
  mean_reversion: 'Reversión a la media',
  volatility: 'Volatilidad',
  composite: 'Combinadas',
};

export function isBacktestStrategyType(value: string): value is BacktestStrategyType {
  return Object.prototype.hasOwnProperty.call(STRATEGY_PRESET_CATALOG, value);
}

export function presetRuleGroups(
  presetKey: BacktestStrategyType,
): { entries: RuleGroupV1; exits: RuleGroupV1 } {
  const preset = STRATEGY_PRESET_CATALOG[presetKey];
  return {
    entries: preset.entries,
    exits: preset.exits,
  };
}

export function presetIndicatorSpecs(presetKey: BacktestStrategyType): IndicatorSpec[] {
  return STRATEGY_PRESET_CATALOG[presetKey].indicatorSpecs;
}

export function presetsByCategory(): Record<
  StrategyPresetCategory,
  Array<{ key: BacktestStrategyType; label: string; description: string }>
> {
  const grouped: Record<
    StrategyPresetCategory,
    Array<{ key: BacktestStrategyType; label: string; description: string }>
  > = {
    trend: [],
    momentum: [],
    mean_reversion: [],
    volatility: [],
    composite: [],
  };

  for (const key of STRATEGY_PRESET_KEYS) {
    const preset = STRATEGY_PRESET_CATALOG[key];
    grouped[preset.category].push({
      key,
      label: preset.label,
      description: preset.description,
    });
  }

  return grouped;
}
