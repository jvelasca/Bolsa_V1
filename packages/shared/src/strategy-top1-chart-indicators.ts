/**
 * Finalistas TOP #1 → IndicatorSpec[] para overlay en el chart Trading.
 *
 * Prefer definition.indicatorSpecs; fallback presetIndicatorSpecs(strategyType).
 *
 * @see ChartTabState.showFinalistTop1Indicators
 */

import type { InstrumentStrategyTopSlotV1 } from './instrument-strategy-top.js';
import type { IndicatorSpec, StrategyDefinitionV1 } from './research-platform.js';
import {
  isBacktestStrategyType,
  presetIndicatorSpecs,
  type BacktestStrategyType,
} from './strategy-presets.js';
import { findIndicatorDefinition } from './indicators-catalog.js';

export type StrategyTop1ChartSource = 'definition' | 'preset' | 'empty';

export type StrategyTop1ChartResult = {
  specs: IndicatorSpec[];
  source: StrategyTop1ChartSource;
  presetKey?: BacktestStrategyType;
  label?: string;
};

export type StrategyTop1ChartInput = {
  slot: InstrumentStrategyTopSlotV1 | null | undefined;
  /** Preferido cuando el slot trae strategyDefinitionId. */
  definition?: Pick<StrategyDefinitionV1, 'indicatorSpecs' | 'presetKey'> | null;
  /** Si true, solo specs de panel overlay (precio). Default: todos (overlay + sub). */
  overlayOnly?: boolean;
};

function filterKnownSpecs(specs: IndicatorSpec[], overlayOnly: boolean): IndicatorSpec[] {
  const out: IndicatorSpec[] = [];
  for (const spec of specs) {
    const def = findIndicatorDefinition(spec.definitionId);
    if (!def) continue;
    if (overlayOnly && def.panel !== 'overlay') continue;
    out.push({
      definitionId: spec.definitionId,
      parameters: { ...spec.parameters },
    });
  }
  return out;
}

/**
 * Resuelve indicadores del Finalista #1 para pintar en el gráfico.
 * No muta estado; el workspace aplica/limpia instancias `origin: 'finalist-top1'`.
 */
export function strategyTop1ToChartIndicators(
  input: StrategyTop1ChartInput,
): StrategyTop1ChartResult {
  const overlayOnly = Boolean(input.overlayOnly);
  const slot = input.slot;
  if (!slot || slot.rank !== 1) {
    return { specs: [], source: 'empty' };
  }

  const fromDef = input.definition?.indicatorSpecs;
  if (Array.isArray(fromDef) && fromDef.length > 0) {
    const specs = filterKnownSpecs(fromDef, overlayOnly);
    const presetKey =
      (input.definition?.presetKey && isBacktestStrategyType(input.definition.presetKey)
        ? input.definition.presetKey
        : undefined) ??
      (slot.strategyType && isBacktestStrategyType(slot.strategyType)
        ? slot.strategyType
        : undefined);
    return {
      specs,
      source: specs.length > 0 ? 'definition' : 'empty',
      presetKey,
      label: slot.label,
    };
  }

  const typeKey =
    (slot.strategyType && isBacktestStrategyType(slot.strategyType)
      ? slot.strategyType
      : null) ??
    (input.definition?.presetKey && isBacktestStrategyType(input.definition.presetKey)
      ? input.definition.presetKey
      : null);

  if (typeKey) {
    const specs = filterKnownSpecs(presetIndicatorSpecs(typeKey), overlayOnly);
    return {
      specs,
      source: specs.length > 0 ? 'preset' : 'empty',
      presetKey: typeKey,
      label: slot.label,
    };
  }

  return { specs: [], source: 'empty', label: slot.label };
}

export function isFinalistTop1Indicator(
  instance: { origin?: string | null },
): boolean {
  return instance.origin === 'finalist-top1';
}
