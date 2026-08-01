import type { ChartIndicatorInstance, IndicatorDefinition, IndicatorParamSchema } from './indicators-catalog.js';
import { findIndicatorDefinition } from './indicators-catalog.js';

/** Claves API legacy (fase 1) — se sustituirán por POST /indicators/compute con IndicatorSpec[]. */
export type LegacyApiIndicatorKey = 'sma20' | 'sma50' | 'ema20' | 'rsi14';

const LEGACY_API_KEYS: Record<string, Record<number, LegacyApiIndicatorKey>> = {
  sma: { 20: 'sma20', 50: 'sma50' },
  ema: { 20: 'ema20' },
  rsi: { 14: 'rsi14' },
};

export const INDICATOR_LINE_COLORS = [
  '#38bdf8',
  '#a78bfa',
  '#fbbf24',
  '#f472b6',
  '#34d399',
  '#fb923c',
  '#e879f9',
  '#22d3ee',
] as const;

/** Parámetros de estilo persistidos en `parameters` pero fuera del esquema de datos. */
export const STYLE_PARAMETER_IDS = ['color'] as const;

export type StyleParameterId = (typeof STYLE_PARAMETER_IDS)[number];

/** Clave estable para comparar parámetros (backtest, deduplicación, plantillas). */
export function parametersKey(parameters: Record<string, number | boolean | string>): string {
  const entries = Object.entries(parameters).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return 'default';
  return entries.map(([key, value]) => `${key}=${String(value)}`).join('|');
}

/** Clave de parámetros de entrada (excluye color y otros estilos). */
export function dataParametersKey(parameters: Record<string, number | boolean | string>): string {
  const entries = Object.entries(parameters)
    .filter(([key]) => !STYLE_PARAMETER_IDS.includes(key as StyleParameterId))
    .sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return 'default';
  return entries.map(([key, value]) => `${key}=${String(value)}`).join('|');
}

export function instanceSpecKey(
  definitionId: string,
  parameters: Record<string, number | boolean | string>,
): string {
  return `${definitionId}::${parametersKey(parameters)}`;
}

export function normalizeParameters(
  definition: IndicatorDefinition,
  raw: Record<string, unknown> = {},
): Record<string, number | boolean | string> {
  const out: Record<string, number | boolean | string> = {};
  for (const schema of definition.parameters) {
    out[schema.id] = coerceParameter(schema, raw[schema.id] ?? schema.default);
  }
  const color = raw.color;
  if (typeof color === 'string' && color.startsWith('#')) {
    out.color = color;
  }
  return out;
}

function coerceParameter(
  schema: IndicatorParamSchema,
  value: unknown,
): number | boolean | string {
  if (schema.type === 'number') {
    let num = typeof value === 'number' ? value : Number.parseFloat(String(value));
    if (!Number.isFinite(num)) num = Number(schema.default);
    if (schema.min != null) num = Math.max(schema.min, num);
    if (schema.max != null) num = Math.min(schema.max, num);
    if (schema.step != null && schema.step > 0) {
      num = Math.round(num / schema.step) * schema.step;
    }
    return num;
  }
  if (schema.type === 'boolean') {
    if (typeof value === 'boolean') return value;
    return Boolean(schema.default);
  }
  const text = value == null ? String(schema.default) : String(value);
  return text;
}

export function findInstanceBySpec(
  instances: ChartIndicatorInstance[],
  definitionId: string,
  parameters: Record<string, number | boolean | string>,
): ChartIndicatorInstance | undefined {
  const key = instanceSpecKey(definitionId, parameters);
  return instances.find(
    (item) => item.definitionId === definitionId && instanceSpecKey(item.definitionId, item.parameters) === key,
  );
}

export function instancesForDefinition(
  instances: ChartIndicatorInstance[],
  definitionId: string,
): ChartIndicatorInstance[] {
  return instances.filter((item) => item.definitionId === definitionId);
}

export function legacyApiKeyForInstance(
  instance: ChartIndicatorInstance,
): LegacyApiIndicatorKey | null {
  const period = Number(instance.parameters.period);
  if (!Number.isFinite(period)) {
    return instance.definitionId === 'volume' ? null : null;
  }
  return LEGACY_API_KEYS[instance.definitionId]?.[period] ?? null;
}

export function isIndicatorApiSupported(
  definitionId: string,
  parameters: Record<string, number | boolean | string>,
): boolean {
  if (definitionId === 'volume') return true;
  const instance: ChartIndicatorInstance = {
    instanceId: 'x',
    definitionId,
    parameters,
    visible: true,
  };
  return legacyApiKeyForInstance(instance) != null;
}

export function colorForInstance(
  instance: ChartIndicatorInstance,
  index = 0,
): string {
  const colorParam = instance.parameters.color;
  if (typeof colorParam === 'string' && colorParam.startsWith('#')) {
    return colorParam;
  }
  let hash = index;
  for (let i = 0; i < instance.instanceId.length; i += 1) {
    hash = (hash + instance.instanceId.charCodeAt(i) * (i + 1)) % INDICATOR_LINE_COLORS.length;
  }
  return INDICATOR_LINE_COLORS[hash] ?? INDICATOR_LINE_COLORS[0];
}

export function formatParameterSummary(
  definition: IndicatorDefinition,
  parameters: Record<string, number | boolean | string>,
): string {
  if (definition.parameters.length === 0) return '';
  return definition.parameters
    .map((schema) => {
      const value = parameters[schema.id];
      if (value == null) return null;
      return `${schema.label}: ${value}`;
    })
    .filter(Boolean)
    .join(' · ');
}

export function instanceDisplayLabel(instance: ChartIndicatorInstance): string {
  const definition = findIndicatorDefinition(instance.definitionId);
  if (!definition) return instance.definitionId;
  const summary = formatParameterSummary(definition, instance.parameters);
  return summary ? `${definition.shortLabel} (${summary})` : definition.shortLabel;
}
