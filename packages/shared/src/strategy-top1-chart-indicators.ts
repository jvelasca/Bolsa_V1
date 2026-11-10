/**
 * Finalistas TOP #1 → IndicatorSpec[] para overlay en el chart Trading.
 *
 * Prefer definition.indicatorSpecs; fallback presetIndicatorSpecs(strategyType).
 *
 * @see ChartTabState.showFinalistTop1Indicators
 */

import type { InstrumentStrategyTopSlotV1 } from "./instrument-strategy-top.js";
import type {
  IndicatorSpec,
  StrategyDefinitionV1,
} from "./research-platform.js";
import {
  isBacktestStrategyType,
  presetIndicatorSpecs,
  type BacktestStrategyType,
} from "./strategy-presets.js";
import { findIndicatorDefinition } from "./indicators-catalog.js";

export type StrategyTop1ChartSource = "definition" | "preset" | "empty";

export type StrategyTop1ChartResult = {
  specs: IndicatorSpec[];
  source: StrategyTop1ChartSource;
  presetKey?: BacktestStrategyType;
  label?: string;
};

export type StrategyTop1ChartInput = {
  slot: InstrumentStrategyTopSlotV1 | null | undefined;
  /** Preferido cuando el slot trae strategyDefinitionId. */
  definition?: Pick<
    StrategyDefinitionV1,
    "indicatorSpecs" | "presetKey"
  > | null;
  /** Si true, solo specs de panel overlay (precio). Default: todos (overlay + sub). */
  overlayOnly?: boolean;
};

function filterKnownSpecs(
  specs: IndicatorSpec[],
  overlayOnly: boolean,
): IndicatorSpec[] {
  const out: IndicatorSpec[] = [];
  for (const spec of specs) {
    const def = findIndicatorDefinition(spec.definitionId);
    if (!def) continue;
    if (overlayOnly && def.panel !== "overlay") continue;
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
    return { specs: [], source: "empty" };
  }

  const fromDef = input.definition?.indicatorSpecs;
  if (Array.isArray(fromDef) && fromDef.length > 0) {
    const specs = filterKnownSpecs(fromDef, overlayOnly);
    const presetKey =
      (input.definition?.presetKey &&
      isBacktestStrategyType(input.definition.presetKey)
        ? input.definition.presetKey
        : undefined) ??
      (slot.strategyType && isBacktestStrategyType(slot.strategyType)
        ? slot.strategyType
        : undefined);
    return {
      specs,
      source: specs.length > 0 ? "definition" : "empty",
      presetKey,
      label: slot.label,
    };
  }

  const typeKey =
    (slot.strategyType && isBacktestStrategyType(slot.strategyType)
      ? slot.strategyType
      : null) ??
    (input.definition?.presetKey &&
    isBacktestStrategyType(input.definition.presetKey)
      ? input.definition.presetKey
      : null);

  if (typeKey) {
    const specs = filterKnownSpecs(presetIndicatorSpecs(typeKey), overlayOnly);
    return {
      specs,
      source: specs.length > 0 ? "preset" : "empty",
      presetKey: typeKey,
      label: slot.label,
    };
  }

  return { specs: [], source: "empty", label: slot.label };
}

export function isFinalistTop1Indicator(instance: {
  origin?: string | null;
}): boolean {
  return instance.origin === "finalist-top1";
}

export type StrategySlotIndicatorsSource = "definition" | "preset" | "empty";

export type StrategySlotIndicatorsResult = {
  /** Nombres legibles (p. ej. `SMA`, `RSI`, `MACD`), sin duplicados. */
  labels: string[];
  source: StrategySlotIndicatorsSource;
  presetKey?: BacktestStrategyType;
};

/**
 * S3 — indicadores que **sustentan** una estrategia del TOP (cualquier rank), en
 * nombres legibles. Fuente: `definition.indicatorSpecs` (si el caller la tiene) →
 * `presetIndicatorSpecs(strategyType)` como fallback.
 *
 * NO usa el catálogo de indicadores del gráfico (eso sería deducir, no evidenciar):
 * si no hay fuente, devuelve `[]` y la superficie declara «Sin dato todavía».
 */
type ResolvedSlotSpecs = {
  specs: IndicatorSpec[];
  source: StrategySlotIndicatorsSource;
  presetKey?: BacktestStrategyType;
};

/**
 * Fuente única de specs de un slot: `definition.indicatorSpecs` → preset del
 * `strategyType`/`presetKey` → `[]`. Nunca se deduce del catálogo del gráfico.
 */
function resolveSlotSpecs(input: {
  slot: InstrumentStrategyTopSlotV1 | null | undefined;
  definition?: Pick<
    StrategyDefinitionV1,
    "indicatorSpecs" | "presetKey"
  > | null;
}): ResolvedSlotSpecs {
  const slot = input.slot;
  if (!slot) return { specs: [], source: "empty" };

  const fromDef = input.definition?.indicatorSpecs;
  const hasDef = Array.isArray(fromDef) && fromDef.length > 0;
  const typeKey =
    (slot.strategyType && isBacktestStrategyType(slot.strategyType)
      ? slot.strategyType
      : null) ??
    (input.definition?.presetKey &&
    isBacktestStrategyType(input.definition.presetKey)
      ? input.definition.presetKey
      : null);

  const specs: IndicatorSpec[] = hasDef
    ? fromDef
    : typeKey
      ? presetIndicatorSpecs(typeKey)
      : [];

  return {
    specs,
    source: hasDef ? "definition" : specs.length > 0 ? "preset" : "empty",
    presetKey: typeKey ?? undefined,
  };
}

export function strategySlotToIndicatorLabels(input: {
  slot: InstrumentStrategyTopSlotV1 | null | undefined;
  definition?: Pick<
    StrategyDefinitionV1,
    "indicatorSpecs" | "presetKey"
  > | null;
}): StrategySlotIndicatorsResult {
  const { specs, source: resolvedSource, presetKey } = resolveSlotSpecs(input);
  const hasDef = resolvedSource === "definition";
  const typeKey = presetKey ?? null;

  const labels = Array.from(
    new Set(
      specs
        .map((spec) => findIndicatorDefinition(spec.definitionId)?.shortLabel)
        .filter((label): label is string => Boolean(label && label.trim())),
    ),
  );

  const source: StrategySlotIndicatorsSource = hasDef
    ? "definition"
    : labels.length > 0
      ? "preset"
      : "empty";

  return { labels, source, presetKey: typeKey ?? undefined };
}

export type StrategySlotIndicatorDetailV1 = {
  definitionId: string;
  /** Etiqueta corta del catálogo (`SMA`, `RSI`, `MACD`) o el id si no se reconoce. */
  label: string;
  /** Etiqueta con parámetros en orden de catálogo (`SMA 20/50`, `MACD 12/26/9`). */
  display: string;
};

export type StrategySlotIndicatorDetailsResult = {
  items: StrategySlotIndicatorDetailV1[];
  source: StrategySlotIndicatorsSource;
  presetKey?: BacktestStrategyType;
};

function formatParamValue(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toFixed(4)));
}

/**
 * S3 — indicadores que **sustentan** una estrategia del TOP, con parámetros.
 *
 * Misma fuente que `strategySlotToIndicatorLabels` (definición → preset → `[]`).
 * Los specs se agrupan por `definitionId` y sus parámetros numéricos se concatenan
 * en el orden del catálogo: dos SMA (20 y 50) ⇒ `SMA 20/50`; MACD ⇒ `MACD 12/26/9`.
 * Una definición desconocida conserva su id como etiqueta, sin parámetros.
 * Sin specs devuelve `[]` (la superficie declara «Sin dato todavía»).
 */
export function strategySlotToIndicatorDetails(input: {
  slot: InstrumentStrategyTopSlotV1 | null | undefined;
  definition?: Pick<
    StrategyDefinitionV1,
    "indicatorSpecs" | "presetKey"
  > | null;
}): StrategySlotIndicatorDetailsResult {
  const { specs, source, presetKey } = resolveSlotSpecs(input);
  const grouped = new Map<string, { label: string; params: number[] }>();

  for (const spec of specs) {
    const def = findIndicatorDefinition(spec.definitionId);
    const label = def?.shortLabel?.trim() || spec.definitionId;
    const entry = grouped.get(spec.definitionId) ?? { label, params: [] };
    for (const param of def?.parameters ?? []) {
      const raw = spec.parameters?.[param.id];
      if (typeof raw === "number" && Number.isFinite(raw)) {
        entry.params.push(raw);
      }
    }
    grouped.set(spec.definitionId, entry);
  }

  const items: StrategySlotIndicatorDetailV1[] = Array.from(
    grouped.entries(),
  ).map(([definitionId, entry]) => ({
    definitionId,
    label: entry.label,
    display:
      entry.params.length > 0
        ? `${entry.label} ${entry.params.map(formatParamValue).join("/")}`
        : entry.label,
  }));

  return { items, source, presetKey };
}
