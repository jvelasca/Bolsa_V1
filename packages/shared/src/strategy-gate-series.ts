/**
 * Serie bar-a-bar de gate de estrategia — paridad con bolsa_analytics.signals.rules_engine.
 */

import type { OhlcvBarDto } from './types.js';
import type { IndicatorSpec } from './research-platform.js';
import type { RuleGroupV1, RuleOperator, StrategyRuleV1 } from './strategy-rules.js';
import { ruleGroupHasRules } from './strategy-rules.js';
import { dataParametersKey } from './indicators-runtime.js';
import {
  presetIndicatorSpecs,
  presetRuleGroups,
  type BacktestStrategyType,
} from './strategy-presets.js';

type IndicatorContext = Record<string, (number | null)[]>;

function specKey(spec: IndicatorSpec): string {
  return `${spec.definitionId}::${dataParametersKey(spec.parameters)}`;
}

function computeSma(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j += 1) sum += closes[j]!;
    out.push(sum / period);
  }
  return out;
}

function computeEma(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (period + 1);
  let ema: number | null = null;
  for (let i = 0; i < closes.length; i += 1) {
    const close = closes[i]!;
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    if (ema == null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j += 1) sum += closes[j]!;
      ema = sum / period;
    } else {
      ema = close * k + ema * (1 - k);
    }
    out.push(ema);
  }
  return out;
}

function computeRsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [null];
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i < closes.length; i += 1) {
    const change = closes[i]! - closes[i - 1]!;
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    if (i < period) {
      avgGain += gain;
      avgLoss += loss;
      out.push(null);
      continue;
    }
    if (i === period) {
      avgGain = (avgGain + gain) / period;
      avgLoss = (avgLoss + loss) / period;
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
    }
    out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  }
  return out;
}

function computeMacdLine(closes: number[], fast: number, slow: number): (number | null)[] {
  const fastEma = computeEma(closes, fast);
  const slowEma = computeEma(closes, slow);
  return closes.map((_, i) => {
    const f = fastEma[i];
    const s = slowEma[i];
    if (f == null || s == null) return null;
    return f - s;
  });
}

function computeMacdSignal(closes: number[], fast: number, slow: number, signal: number): (number | null)[] {
  const macd = computeMacdLine(closes, fast, slow);
  const numeric = macd.map((v) => (v == null ? 0 : v));
  return computeEma(numeric, signal);
}

function computeBollinger(
  closes: number[],
  period: number,
  stdDev: number,
): { mid: (number | null)[]; upper: (number | null)[]; lower: (number | null)[] } {
  const mid = computeSma(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    const m = mid[i];
    if (m == null || i + 1 < period) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      const diff = closes[j]! - m;
      sumSq += diff * diff;
    }
    const sd = Math.sqrt(sumSq / period);
    upper.push(m + stdDev * sd);
    lower.push(m - stdDev * sd);
  }
  return { mid, upper, lower };
}

function computeStochK(bars: OhlcvBarDto[], kPeriod: number): (number | null)[] {
  return bars.map((_, i) => {
    if (i + 1 < kPeriod) return null;
    let highest = -Infinity;
    let lowest = Infinity;
    for (let j = i - kPeriod + 1; j <= i; j += 1) {
      highest = Math.max(highest, bars[j]!.high);
      lowest = Math.min(lowest, bars[j]!.low);
    }
    if (highest === lowest) return 50;
    return ((bars[i]!.close - lowest) / (highest - lowest)) * 100;
  });
}

function computeCci(bars: OhlcvBarDto[], period: number): (number | null)[] {
  return bars.map((_, i) => {
    if (i + 1 < period) return null;
    const slice = bars.slice(i - period + 1, i + 1);
    const typical = slice.map((bar) => (bar.high + bar.low + bar.close) / 3);
    const mean = typical.reduce((a, b) => a + b, 0) / period;
    const meanDev =
      typical.reduce((acc, value) => acc + Math.abs(value - mean), 0) / period;
    if (meanDev === 0) return 0;
    const last = typical[typical.length - 1]!;
    return (last - mean) / (0.015 * meanDev);
  });
}

function computeDonchianLine(
  bars: OhlcvBarDto[],
  period: number,
  line: string,
): (number | null)[] {
  return bars.map((_, i) => {
    if (i + 1 < period) return null;
    const slice = bars.slice(i - period + 1, i + 1);
    const hi = Math.max(...slice.map((bar) => bar.high));
    const lo = Math.min(...slice.map((bar) => bar.low));
    if (line === 'upper') return hi;
    if (line === 'lower') return lo;
    return (hi + lo) / 2;
  });
}

function computeAtr(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const tr: number[] = bars.map((bar, i) => {
    if (i === 0) return bar.high - bar.low;
    const prev = bars[i - 1]!;
    return Math.max(
      bar.high - bar.low,
      Math.abs(bar.high - prev.close),
      Math.abs(bar.low - prev.close),
    );
  });
  const out: (number | null)[] = [];
  let prev: number | null = null;
  for (let i = 0; i < tr.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    if (prev == null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j += 1) sum += tr[j]!;
      prev = sum / period;
    } else {
      prev = (prev * (period - 1) + tr[i]!) / period;
    }
    out.push(prev);
  }
  return out;
}

/** SuperTrend line — paridad con compute_supertrend (Python). */
function computeSupertrend(
  bars: OhlcvBarDto[],
  atrPeriod: number,
  multiplier: number,
): (number | null)[] {
  const atr = computeAtr(bars, atrPeriod);
  const n = bars.length;
  const result: (number | null)[] = Array.from({ length: n }, () => null);
  const finalUb: (number | null)[] = Array.from({ length: n }, () => null);
  const finalLb: (number | null)[] = Array.from({ length: n }, () => null);
  let trend = 1;
  for (let i = 0; i < n; i += 1) {
    const atrV = atr[i];
    if (atrV == null) continue;
    const hl2 = (bars[i]!.high + bars[i]!.low) / 2;
    const basicUb = hl2 + multiplier * atrV;
    const basicLb = hl2 - multiplier * atrV;
    if (i === 0 || finalUb[i - 1] == null) {
      finalUb[i] = basicUb;
      finalLb[i] = basicLb;
    } else {
      const prevUb = finalUb[i - 1]!;
      const prevLb = finalLb[i - 1]!;
      const prevClose = bars[i - 1]!.close;
      finalUb[i] = basicUb < prevUb || prevClose > prevUb ? basicUb : prevUb;
      finalLb[i] = basicLb > prevLb || prevClose < prevLb ? basicLb : prevLb;
    }
    const curUb = finalUb[i]!;
    const curLb = finalLb[i]!;
    const close = bars[i]!.close;
    if (i > 0 && finalUb[i - 1] != null && close > finalUb[i - 1]!) trend = 1;
    else if (i > 0 && finalLb[i - 1] != null && close < finalLb[i - 1]!) trend = -1;
    result[i] = trend === 1 ? curLb : curUb;
  }
  return result;
}

function seriesForSpec(bars: OhlcvBarDto[], spec: IndicatorSpec): (number | null)[] | null {
  const closes = bars.map((bar) => bar.close);
  const period = Number(spec.parameters.period ?? 14);
  const line = String(spec.parameters.line ?? 'main');

  switch (spec.definitionId) {
    case 'sma':
      return computeSma(closes, period);
    case 'ema':
      return computeEma(closes, period);
    case 'rsi':
      return computeRsi(closes, period);
    case 'cci':
      return computeCci(bars, period);
    case 'stoch':
      return computeStochK(bars, Number(spec.parameters.kPeriod ?? period));
    case 'bb': {
      const stdDev = Number(spec.parameters.stdDev ?? 2);
      const bands = computeBollinger(closes, period, stdDev);
      if (line === 'upper') return bands.upper;
      if (line === 'lower') return bands.lower;
      return bands.mid;
    }
    case 'macd': {
      const fast = Number(spec.parameters.fastPeriod ?? 12);
      const slow = Number(spec.parameters.slowPeriod ?? 26);
      const signal = Number(spec.parameters.signalPeriod ?? 9);
      if (line === 'signal') return computeMacdSignal(closes, fast, slow, signal);
      return computeMacdLine(closes, fast, slow);
    }
    case 'dc':
      return computeDonchianLine(bars, period, line);
    case 'st': {
      const atrPeriod = Number(spec.parameters.atrPeriod ?? 10);
      const multiplier = Number(spec.parameters.multiplier ?? 3);
      return computeSupertrend(bars, atrPeriod, multiplier);
    }
    default:
      return null;
  }
}

export function buildIndicatorContext(bars: OhlcvBarDto[], specs: IndicatorSpec[]): IndicatorContext {
  const context: IndicatorContext = {};
  for (const spec of specs) {
    const series = seriesForSpec(bars, spec);
    if (series) context[specKey(spec)] = series;
  }
  return context;
}

function valueAt(context: IndicatorContext, spec: IndicatorSpec, index: number): number | null {
  const series = context[specKey(spec)];
  if (!series || index >= series.length) return null;
  return series[index] ?? null;
}

function compare(left: number, operator: RuleOperator, right: number): boolean {
  if (operator === 'lt') return left < right;
  if (operator === 'lte') return left <= right;
  if (operator === 'gt') return left > right;
  if (operator === 'gte') return left >= right;
  return left === right;
}

function detectCross(
  left: (number | null)[],
  right: (number | null)[],
  index: number,
  direction: 'bullish' | 'bearish',
): boolean {
  if (index < 1) return false;
  const prevLeft = left[index - 1];
  const prevRight = right[index - 1];
  const currLeft = left[index];
  const currRight = right[index];
  if (
    prevLeft == null ||
    prevRight == null ||
    currLeft == null ||
    currRight == null
  ) {
    return false;
  }
  if (direction === 'bullish') return prevLeft <= prevRight && currLeft > currRight;
  return prevLeft >= prevRight && currLeft < currRight;
}

function evaluateRule(
  rule: StrategyRuleV1,
  index: number,
  context: IndicatorContext,
  closes: number[],
): boolean {
  switch (rule.type) {
    case 'indicator_cross': {
      const left = context[specKey(rule.leftSpec)];
      const right = context[specKey(rule.rightSpec)];
      if (!left || !right) return false;
      return detectCross(left, right, index, rule.direction);
    }
    case 'indicator_compare': {
      const left = valueAt(context, rule.leftSpec, index);
      if (left == null) return false;
      return compare(left, rule.operator, rule.rightValue);
    }
    case 'price_vs_indicator': {
      const indicator = valueAt(context, rule.indicatorSpec, index);
      if (indicator == null) return false;
      return compare(closes[index]!, rule.operator, indicator);
    }
    case 'indicator_vs_indicator': {
      const left = valueAt(context, rule.leftSpec, index);
      const right = valueAt(context, rule.rightSpec, index);
      if (left == null || right == null) return false;
      return compare(left, rule.operator, right);
    }
    case 'price_compare':
      return compare(closes[index]!, rule.operator, rule.value);
    default:
      return false;
  }
}

export function evaluateRuleGroupAtIndex(
  group: RuleGroupV1,
  index: number,
  context: IndicatorContext,
  closes: number[],
): boolean {
  if (!group.rules.length) return true;
  if (group.operator === 'all') {
    return group.rules.every((rule) => evaluateRule(rule, index, context, closes));
  }
  return group.rules.some((rule) => evaluateRule(rule, index, context, closes));
}

export function resolveGateRuleGroup(
  gatePresetKey: string | null | undefined,
  entries?: RuleGroupV1 | null,
): RuleGroupV1 | null {
  if (gatePresetKey) {
    const preset = presetRuleGroups(gatePresetKey as BacktestStrategyType);
    if (ruleGroupHasRules(preset.entries)) return preset.entries;
  }
  if (entries && ruleGroupHasRules(entries)) return entries;
  return null;
}

export function resolveGateIndicatorSpecs(
  gatePresetKey: string | null | undefined,
  indicatorSpecs: IndicatorSpec[] = [],
): IndicatorSpec[] {
  if (gatePresetKey) {
    return presetIndicatorSpecs(gatePresetKey as BacktestStrategyType);
  }
  return indicatorSpecs;
}

/** 100 = gate abierto, 0 = cerrado, null = sin datos. */
export function computeGatePassSeries(
  bars: OhlcvBarDto[],
  ruleGate: RuleGroupV1 | null,
  indicatorSpecs: IndicatorSpec[] = [],
): (number | null)[] {
  if (!ruleGate || !ruleGroupHasRules(ruleGate)) {
    return bars.map(() => 100);
  }
  const context = buildIndicatorContext(bars, indicatorSpecs);
  const closes = bars.map((bar) => bar.close);
  return bars.map((_, index) =>
    evaluateRuleGroupAtIndex(ruleGate, index, context, closes) ? 100 : 0,
  );
}

export function computeGatePassSeriesFromPreset(
  bars: OhlcvBarDto[],
  gatePresetKey: string | null | undefined,
  entries?: RuleGroupV1 | null,
): (number | null)[] {
  const ruleGate = resolveGateRuleGroup(gatePresetKey, entries);
  const specs = resolveGateIndicatorSpecs(gatePresetKey, []);
  return computeGatePassSeries(bars, ruleGate, specs);
}
