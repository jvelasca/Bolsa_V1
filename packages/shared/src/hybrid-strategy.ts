/**
 * Rastreadores híbridos — gate determinista + scorer IA explicable (P10a).
 */

import type { ChartTimeframe } from './chart-timeframes.js';
import type {
  ExecutionModel,
  IndicatorSpec,
  StrategyDefinitionV1,
} from './research-platform.js';
import type { RuleGroupV1 } from './strategy-rules.js';
import type { FundamentalGateV1 } from './fundamentals-gate.js';
import { buildFundamentalGate } from './fundamentals-gate.js';
import {
  presetIndicatorSpecs,
  presetRuleGroups,
  HYBRID_GATE_PRESET_KEYS,
  type BacktestStrategyType,
} from './strategy-presets.js';

export const TECHNICAL_RATING_V1_VERSION = '1.1.0';

export type AiScorerModelId = 'technical_rating_v1';

export interface AiScorerConfigV1 {
  modelId: AiScorerModelId;
  minScore: number;
  version?: string;
}

export interface HybridStrategyConfigV1 {
  /** Condiciones obligatorias en la última barra (hard filter). */
  ruleGate: RuleGroupV1;
  aiScorer: AiScorerConfigV1;
  /** Preset usado para construir el gate (trazabilidad). */
  gatePresetKey?: BacktestStrategyType;
  /** Filtro fundamental opcional (P12). */
  fundamentalGate?: FundamentalGateV1;
  /** Calidad mínima de datos OHLCV/sync (0 = sin filtro). */
  minDataQuality?: number;
}

export interface DataQualityBreakdownV1 {
  freshness: number;
  barDepth: number;
  sync: number;
  gaps: number;
  fundamentals: number;
  total: number;
  modelId?: string;
  modelVersion: string;
}

export interface TechnicalRatingBreakdownV1 {
  trend: number;
  momentum: number;
  volatility: number;
  meanReversion: number;
  pattern?: number;
  total: number;
  modelId: AiScorerModelId;
  modelVersion: string;
}

/** Indicadores adicionales para rating técnico completo. */
export const TECHNICAL_RATING_INDICATOR_SPECS: IndicatorSpec[] = [
  { definitionId: 'sma', parameters: { period: 20 } },
  { definitionId: 'sma', parameters: { period: 50 } },
  { definitionId: 'sma', parameters: { period: 200 } },
  { definitionId: 'rsi', parameters: { period: 14 } },
  {
    definitionId: 'macd',
    parameters: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9, line: 'main' },
  },
  { definitionId: 'bb', parameters: { period: 20, stdDev: 2, line: 'mid' } },
  { definitionId: 'bb', parameters: { period: 20, stdDev: 2, line: 'upper' } },
  { definitionId: 'bb', parameters: { period: 20, stdDev: 2, line: 'lower' } },
  { definitionId: 'stoch', parameters: { kPeriod: 14 } },
  { definitionId: 'cci', parameters: { period: 20 } },
  { definitionId: 'atr', parameters: { period: 14 } },
];

function mergeIndicatorSpecs(...groups: IndicatorSpec[][]): IndicatorSpec[] {
  const seen = new Set<string>();
  const merged: IndicatorSpec[] = [];
  for (const spec of groups.flat()) {
    const key = `${spec.definitionId}::${JSON.stringify(spec.parameters)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(spec);
  }
  return merged;
}

export function strategyDefinitionFromHybrid(options: {
  name: string;
  gatePresetKey: BacktestStrategyType;
  minScore: number;
  instrumentIds: string[];
  timeframe?: ChartTimeframe;
  execution?: ExecutionModel;
  maxTrailingPe?: number | null;
  minMarketCapMillions?: number | null;
  minRoe?: number | null;
  maxDebtToEquity?: number | null;
  minCurrentRatio?: number | null;
  minAltmanZ?: number | null;
  minFcfYield?: number | null;
  minOperatingMargin?: number | null;
  minRevenueGrowth?: number | null;
  minPiotroski?: number | null;
  minDcfUpside?: number | null;
  minGrahamUpside?: number | null;
  useSectorBands?: boolean;
  sectors?: string[];
  minDataQuality?: number;
}): StrategyDefinitionV1 {
  const gateRules = presetRuleGroups(options.gatePresetKey).entries;
  const fundamentalGate = buildFundamentalGate({
    maxTrailingPe: options.maxTrailingPe,
    minMarketCapMillions: options.minMarketCapMillions,
    minRoe: options.minRoe,
    maxDebtToEquity: options.maxDebtToEquity,
    minCurrentRatio: options.minCurrentRatio,
    minAltmanZ: options.minAltmanZ,
    minFcfYield: options.minFcfYield,
    minOperatingMargin: options.minOperatingMargin,
    minRevenueGrowth: options.minRevenueGrowth,
    minPiotroski: options.minPiotroski,
    minDcfUpside: options.minDcfUpside,
    minGrahamUpside: options.minGrahamUpside,
    useSectorBands: options.useSectorBands,
    sectors: options.sectors,
  });

  return {
    id: `hybrid:${options.gatePresetKey}:${options.minScore}`,
    version: 1,
    name: options.name,
    kind: 'hybrid',
    universe: { instrumentIds: options.instrumentIds },
    timeframe: options.timeframe ?? '1d',
    dataSnapshotPolicy: 'latest',
    entries: { operator: 'all', rules: [] },
    exits: { operator: 'all', rules: [] },
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: mergeIndicatorSpecs(
      presetIndicatorSpecs(options.gatePresetKey),
      TECHNICAL_RATING_INDICATOR_SPECS,
    ),
    execution: options.execution ?? { fillModel: 'bar_close', commissionBps: 0, slippageBps: 0 },
    origin: 'assisted',
    hybrid: {
      ruleGate: gateRules,
      aiScorer: {
        modelId: 'technical_rating_v1',
        minScore: options.minScore,
        version: TECHNICAL_RATING_V1_VERSION,
      },
      gatePresetKey: options.gatePresetKey,
      ...(fundamentalGate ? { fundamentalGate } : {}),
      ...(options.minDataQuality != null && options.minDataQuality > 0
        ? { minDataQuality: options.minDataQuality }
        : {}),
    },
  };
}

export const DEFAULT_HYBRID_MIN_SCORE = 60;
export const DEFAULT_HYBRID_MIN_DATA_QUALITY = 0;

export { HYBRID_GATE_PRESET_KEYS };
