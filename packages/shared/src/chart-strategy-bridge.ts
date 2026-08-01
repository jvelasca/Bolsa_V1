/**
 * BT-3b — serializar pestaña de chart → draft StrategyDefinitionV1 / backtest form.
 */

import type { ChartTabState } from './chart-defaults.js';
import type { ChartStrategySetupDraft } from './chart-strategy-bridge-api.js';
import type { ChartIndicatorInstance } from './indicators-catalog.js';
import { findIndicatorDefinition } from './indicators-catalog.js';
import { dataParametersKey, STYLE_PARAMETER_IDS } from './indicators-runtime.js';
import {
  DEFAULT_EXECUTION_MODEL,
  strategyDefinitionFromPreset,
  type IndicatorSpec,
  type StrategyDefinitionV1,
} from './research-platform.js';
import { drawingSupportsReplay } from './drawing-replay.js';
import type { BacktestStrategyType } from './types.js';
import type { StrategyDefinitionDetailDto } from './strategy-definitions.js';
import {
  createAiIndicatorVariantPreset,
  newIndicatorPresetId,
  type IndicatorPreset,
} from './indicator-presets.js';
import { DEFAULT_HYBRID_MIN_SCORE } from './hybrid-strategy.js';
import { ruleGroupHasRules } from './strategy-rules.js';

export type { ChartStrategySetupDraft } from './chart-strategy-bridge-api.js';

function indicatorInstanceToSpec(instance: ChartIndicatorInstance): IndicatorSpec | null {
  if (!instance.visible) return null;
  const definition = findIndicatorDefinition(instance.definitionId);
  if (!definition) return null;

  const parameters: Record<string, number | boolean | string> = {};
  for (const schema of definition.parameters) {
    const raw = instance.parameters[schema.id];
    if (raw === undefined) continue;
    parameters[schema.id] = raw;
  }

  return {
    definitionId: instance.definitionId,
    parameters,
  };
}

function specDataKey(spec: IndicatorSpec): string {
  const filtered = Object.fromEntries(
    Object.entries(spec.parameters).filter(
      ([key]) => !STYLE_PARAMETER_IDS.includes(key as (typeof STYLE_PARAMETER_IDS)[number]),
    ),
  );
  return `${spec.definitionId}::${dataParametersKey(filtered)}`;
}

/** Dedup visible instances → IndicatorSpec[] (sin color). */
export function chartIndicatorInstancesToSpecs(
  instances: ChartIndicatorInstance[],
): IndicatorSpec[] {
  const seen = new Set<string>();
  const specs: IndicatorSpec[] = [];
  for (const instance of instances) {
    const spec = indicatorInstanceToSpec(instance);
    if (!spec) continue;
    const key = specDataKey(spec);
    if (seen.has(key)) continue;
    seen.add(key);
    specs.push(spec);
  }
  return specs;
}

export function inferPresetFromIndicatorSpecs(
  specs: IndicatorSpec[],
): BacktestStrategyType | null {
  const hasSma = (period: number) =>
    specs.some(
      (spec) =>
        spec.definitionId === 'sma' && Number(spec.parameters.period) === period,
    );
  if (hasSma(20) && hasSma(50)) return 'sma_crossover';

  const rsiOnly =
    specs.length >= 1 &&
    specs.every((spec) => spec.definitionId === 'rsi') &&
    specs.some((spec) => Number(spec.parameters.period) === 14);
  if (rsiOnly) return 'rsi_mean_reversion';

  return null;
}

export function serializeChartTabToStrategyDraft(tab: ChartTabState): ChartStrategySetupDraft {
  const indicatorSpecs = chartIndicatorInstancesToSpecs(tab.indicatorInstances);
  const indicatorLabels = tab.indicatorInstances
    .filter((instance) => instance.visible)
    .map((instance) => {
      const definition = findIndicatorDefinition(instance.definitionId);
      const period = instance.parameters.period;
      const label = definition?.shortLabel ?? instance.definitionId;
      return period != null ? `${label} (${period})` : label;
    });

  const drawingAlertCount = tab.drawings.filter(
    (drawing) => drawingSupportsReplay(drawing) && drawing.alertOnCross === true,
  ).length;

  const inferredPresetKey = inferPresetFromIndicatorSpecs(indicatorSpecs);
  const warnings: string[] = [];

  if (indicatorSpecs.length === 0) {
    warnings.push('El gráfico no tiene indicadores visibles.');
  }
  if (!inferredPresetKey && indicatorSpecs.length > 0) {
    warnings.push(
      'No coincide con un preset ejecutable (SMA 20+50 o RSI 14). Puedes guardar indicadores para más adelante.',
    );
  }
  if (drawingAlertCount > 0) {
    warnings.push(
      `${drawingAlertCount} dibujo(s) con alerta — inclúyelos en drawing replay (BT-6); reglas formales en SC-1.`,
    );
  }

  return {
    instrumentId: tab.instrumentId,
    instrumentLabel: tab.label,
    timeframe: tab.timeframe,
    indicatorSpecs,
    indicatorLabels,
    drawingAlertCount,
    inferredPresetKey,
    canRunPresetBacktest: Boolean(inferredPresetKey && tab.instrumentId),
    warnings,
  };
}

export function strategyDefinitionFromChartDraft(
  draft: ChartStrategySetupDraft,
  name: string,
): StrategyDefinitionV1 {
  if (draft.inferredPresetKey) {
    const base = strategyDefinitionFromPreset(
      draft.inferredPresetKey,
      [draft.instrumentId],
      draft.timeframe,
    );
    return { ...base, name, origin: 'assisted' };
  }

  return {
    id: 'draft',
    version: 1,
    name,
    kind: 'indicator_signals',
    universe: { instrumentIds: [draft.instrumentId] },
    timeframe: draft.timeframe,
    dataSnapshotPolicy: 'latest',
    entries: { operator: 'all', rules: [] },
    exits: { operator: 'all', rules: [] },
    sizing: { mode: 'fixed_cash', value: 1 },
    risk: {},
    indicatorSpecs: draft.indicatorSpecs,
    execution: { ...DEFAULT_EXECUTION_MODEL },
    origin: 'assisted',
  };
}

function resolveStrategyGatePresetKey(
  strategy: StrategyDefinitionDetailDto,
): BacktestStrategyType | '' {
  if (strategy.kind === 'hybrid') {
    return strategy.definition.hybrid?.gatePresetKey ?? '';
  }
  if (strategy.presetKey) return strategy.presetKey;
  return '';
}

function resolveStrategyMinScore(strategy: StrategyDefinitionDetailDto): number {
  if (strategy.kind === 'hybrid') {
    return strategy.definition.hybrid?.aiScorer?.minScore ?? DEFAULT_HYBRID_MIN_SCORE;
  }
  return DEFAULT_HYBRID_MIN_SCORE;
}

export function canPublishStrategyScoreAsIndicator(
  strategy: Pick<StrategyDefinitionDetailDto, 'kind' | 'presetKey' | 'definition'>,
): boolean {
  if (strategy.kind === 'hybrid') {
    const hybrid = strategy.definition.hybrid;
    return hybrid?.aiScorer?.modelId === 'technical_rating_v1';
  }
  if (strategy.kind === 'indicator_signals' && strategy.presetKey) return true;
  if (strategy.kind === 'rule_based' && ruleGroupHasRules(strategy.definition.entries)) {
    return true;
  }
  return false;
}

/** Preset IA vinculado al rating de una estrategia guardada (híbrida o clásica). */
export function presetFromStrategyScore(
  strategy: StrategyDefinitionDetailDto,
): IndicatorPreset | null {
  if (!canPublishStrategyScoreAsIndicator(strategy)) return null;
  const gatePresetKey = resolveStrategyGatePresetKey(strategy);
  const minScore = resolveStrategyMinScore(strategy);
  const preset = createAiIndicatorVariantPreset({
    definitionId: 'strategy_hybrid_score_v1',
    name: `${strategy.name} · Score`,
    parameters: {
      linkedStrategyId: strategy.id,
      strategyName: strategy.name,
      minScore,
      showMinScoreLine: strategy.kind === 'hybrid',
      gatePresetKey,
      showGateLine: Boolean(gatePresetKey) || ruleGroupHasRules(strategy.definition.entries),
      showComponents: true,
      warmupBars: 50,
    },
  });
  if (!preset) return null;
  return { ...preset, id: newIndicatorPresetId() };
}

/** @deprecated Usa presetFromStrategyScore */
export function presetFromHybridStrategyScore(
  strategy: StrategyDefinitionDetailDto,
): IndicatorPreset | null {
  return presetFromStrategyScore(strategy);
}
