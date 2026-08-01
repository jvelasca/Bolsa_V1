/**
 * Strategy rules v1 (ADR-010 P7) — condiciones tipadas en StrategyDefinitionV1.
 * Paridad TS / Python en bolsa_analytics.signals.rules_engine.
 */

import type { IndicatorSpec } from './research-platform.js';
import type { SignalKind } from './signal-events.js';

export type RuleOperator = 'lt' | 'lte' | 'gt' | 'gte' | 'eq';

export type IndicatorCrossDirection = 'bullish' | 'bearish';

export interface IndicatorCrossRuleV1 {
  type: 'indicator_cross';
  leftSpec: IndicatorSpec;
  rightSpec: IndicatorSpec;
  direction: IndicatorCrossDirection;
  signalKind: SignalKind;
}

export interface IndicatorCompareRuleV1 {
  type: 'indicator_compare';
  leftSpec: IndicatorSpec;
  operator: RuleOperator;
  rightValue: number;
  signalKind: SignalKind;
}

export interface PriceCompareRuleV1 {
  type: 'price_compare';
  operator: RuleOperator;
  value: number;
  signalKind: SignalKind;
}

export interface PriceVsIndicatorRuleV1 {
  type: 'price_vs_indicator';
  indicatorSpec: IndicatorSpec;
  operator: RuleOperator;
  signalKind: SignalKind;
}

export interface IndicatorVsIndicatorRuleV1 {
  type: 'indicator_vs_indicator';
  leftSpec: IndicatorSpec;
  operator: RuleOperator;
  rightSpec: IndicatorSpec;
  signalKind: SignalKind;
}

export type StrategyRuleV1 =
  | IndicatorCrossRuleV1
  | IndicatorCompareRuleV1
  | PriceCompareRuleV1
  | PriceVsIndicatorRuleV1
  | IndicatorVsIndicatorRuleV1;

export interface RuleGroupV1 {
  operator: 'all' | 'any';
  rules: StrategyRuleV1[];
}

export function ruleGroupHasRules(group: RuleGroupV1 | undefined | null): boolean {
  return Boolean(group?.rules?.length);
}

/** @deprecated Import from strategy-presets.js */
export { presetRuleGroups } from './strategy-presets.js';
