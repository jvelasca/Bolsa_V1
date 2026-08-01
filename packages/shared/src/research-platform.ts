/**
 * Contratos de la plataforma de research / backtesting (H0).
 * Alineados con docs/BACKTESTING_DATA_ARCHITECTURE.md — usados por UI, API y futura IA.
 */

import type { HybridStrategyConfigV1 } from './hybrid-strategy.js';
import type { ChartTimeframe } from './chart-timeframes.js';
import type { BacktestStrategyType } from './types.js';
import type { RuleGroupV1 } from './strategy-rules.js';
import { presetRuleGroups, STRATEGY_PRESET_CATALOG } from './strategy-presets.js';

export { type RuleGroupV1, type StrategyRuleV1 } from './strategy-rules.js';

export const RUN_MANIFEST_VERSION = '1.0' as const;

export type BacktestFillModel = 'next_bar_open' | 'bar_close';

export type StrategyDefinitionKind =
  | 'rule_based'
  | 'indicator_signals'
  | 'ml_model'
  | 'hybrid';

export type StrategyOrigin = 'manual' | 'assisted' | 'ai_generated' | 'imported' | 'preset';

export type ResearchJobType =
  | 'backtest'
  | 'optimize'
  | 'feature_build'
  | 'ml_train'
  | 'ai_strategy_draft';

export type ResearchJobStatus = 'queued' | 'running' | 'completed' | 'failed';

/** Spec estable de indicador — paridad chart / backtest / ML. */
export interface IndicatorSpec {
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
}

export interface ExecutionModel {
  fillModel: BacktestFillModel;
  commissionBps: number;
  slippageBps: number;
}

export interface StrategySizing {
  mode: 'fixed_cash' | 'percent_equity';
  value: number;
}

export interface StrategyRisk {
  stopLossPct?: number;
  takeProfitPct?: number;
  maxPositions?: number;
}

/** Referencia inmutable a los datos usados en un run. */
export interface DataSnapshotRef {
  id: string;
  instrumentIds: string[];
  timeframe: ChartTimeframe;
  from: string;
  to: string;
  barCount: number;
  dataVersion: string;
  source: 'postgres';
}

export interface RunManifestEngine {
  name: string;
  version: string;
}

export interface RunManifestProvenance {
  origin: StrategyOrigin;
  sourcePrompt?: string;
  parentRunId?: string;
}

/** Manifest JSON persistido en cada backtest / job de research. */
export interface RunManifest {
  manifestVersion: typeof RUN_MANIFEST_VERSION;
  runId: string;
  runType: 'backtest';
  createdAt: string;
  engine: RunManifestEngine;
  dataSnapshot: DataSnapshotRef;
  strategy: StrategyDefinitionV1;
  indicatorSpecs: IndicatorSpec[];
  executionParams: { initialCash: number };
  environment: Record<string, string>;
  outputs: {
    metricsHash: string;
    tradeCount: number;
    equityCurve?: Array<{ timestamp: string; equity: number }>;
  };
  provenance: RunManifestProvenance;
}

/** Definición de estrategia versionada — subset H0 (presets + futuro builder). */
export interface StrategyDefinitionV1 {
  id: string;
  version: number;
  name: string;
  kind: StrategyDefinitionKind;
  presetKey?: BacktestStrategyType;
  universe: { instrumentIds: string[] };
  timeframe: ChartTimeframe;
  dataSnapshotPolicy: 'latest' | 'pinned';
  entries: RuleGroupV1;
  exits: RuleGroupV1;
  sizing: StrategySizing;
  risk: StrategyRisk;
  indicatorSpecs: IndicatorSpec[];
  execution: ExecutionModel;
  origin: StrategyOrigin;
  sourcePrompt?: string;
  parentStrategyId?: string;
  /** Gate + scorer IA (kind === 'hybrid'). */
  hybrid?: HybridStrategyConfigV1;
}

/** Shape de job async — H0 usa sync con mismo contrato. */
export interface ResearchJobSpec {
  id: string;
  type: ResearchJobType;
  status: ResearchJobStatus;
  payload: Record<string, unknown>;
  resultRunId?: string;
  error?: string;
  createdAt: string;
  completedAt?: string;
}

export const DEFAULT_EXECUTION_MODEL: ExecutionModel = {
  fillModel: 'bar_close',
  commissionBps: 0,
  slippageBps: 0,
};

/** Presets mapeados desde catálogo central strategy-presets.json. */
export function strategyDefinitionFromPreset(
  presetKey: BacktestStrategyType,
  instrumentIds: string[],
  timeframe: ChartTimeframe = '1d',
): StrategyDefinitionV1 {
  const preset = STRATEGY_PRESET_CATALOG[presetKey];
  const ruleGroups = presetRuleGroups(presetKey);
  return {
    id: `preset:${presetKey}`,
    version: 1,
    name: preset.label,
    kind: 'indicator_signals',
    presetKey,
    universe: { instrumentIds },
    timeframe,
    dataSnapshotPolicy: 'latest',
    entries: ruleGroups.entries,
    exits: ruleGroups.exits,
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: preset.indicatorSpecs,
    execution: { ...DEFAULT_EXECUTION_MODEL },
    origin: 'preset',
  };
}
