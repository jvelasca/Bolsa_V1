import type { ChartIndicatorInstance, IndicatorDefinition, IndicatorSource } from './indicators-catalog.js';
import { AI_INDICATOR_DEFINITIONS } from './ai-indicators-catalog.js';
import {
  BUILTIN_INDICATORS,
  defaultParameters,
  findIndicatorDefinition,
  instanceLabel,
  newIndicatorInstanceId,
} from './indicators-catalog.js';
import { normalizeParameters } from './indicators-runtime.js';

/**
 * Variante guardada de un indicador (params + estilo + nombre).
 * Independiente de si está en algún gráfico o grupo.
 */
export interface IndicatorPreset {
  id: string;
  /** Nombre visible en catálogo y paneles. */
  name: string;
  source: IndicatorSource;
  /** Presets de sistema / software propio: no borrables. */
  locked: boolean;
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
  lineWidth?: number;
  showLastValue?: boolean;
  /** Si el preset deriva de otro preset o definición de sistema. */
  derivedFromPresetId?: string;
  derivedFromDefinitionId?: string;
}

export function newIndicatorPresetId(): string {
  return `ipre-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function systemPresetId(definitionId: string, suffix = 'default'): string {
  return `preset-sys-${definitionId}-${suffix}`;
}

function buildSystemPreset(
  definition: IndicatorDefinition,
  options?: {
    id?: string;
    name?: string;
    parameters?: Record<string, number | boolean | string>;
    lineWidth?: number;
  },
): IndicatorPreset {
  const parameters = normalizeParameters(
    definition,
    options?.parameters ?? defaultParameters(definition),
  );
  const paramSummary =
    definition.parameters.length > 0
      ? ` ${definition.parameters
          .map((p) => parameters[p.id])
          .filter((v) => v != null)
          .join('/')}`
      : '';
  return {
    id: options?.id ?? systemPresetId(definition.id),
    name: options?.name ?? `${definition.shortLabel}${paramSummary}`.trim(),
    source: 'builtin',
    locked: true,
    definitionId: definition.id,
    parameters,
    lineWidth: options?.lineWidth ?? 2,
    derivedFromDefinitionId: definition.id,
  };
}

/** Presets de sistema sembrados por código (no borrables). */
export function buildDefaultSystemPresets(): IndicatorPreset[] {
  const presets: IndicatorPreset[] = [];
  for (const definition of BUILTIN_INDICATORS) {
    presets.push(buildSystemPreset(definition));
  }
  const sma = findIndicatorDefinition('sma');
  if (sma) {
    presets.push(
      buildSystemPreset(sma, {
        id: 'preset-sys-sma-50',
        name: 'SMA 50',
        parameters: { period: 50 },
      }),
    );
  }
  return presets;
}

export const DEFAULT_SYSTEM_PRESETS: IndicatorPreset[] = buildDefaultSystemPresets();

function aiPresetId(definitionId: string, suffix = 'default'): string {
  return `preset-ai-${definitionId}-${suffix}`;
}

function buildAiPreset(
  definition: IndicatorDefinition,
  options?: {
    id?: string;
    name?: string;
    parameters?: Record<string, number | boolean | string>;
    lineWidth?: number;
  },
): IndicatorPreset {
  const parameters = normalizeParameters(
    definition,
    options?.parameters ?? defaultParameters(definition),
  );
  return {
    id: options?.id ?? aiPresetId(definition.id),
    name: options?.name ?? definition.shortLabel,
    source: 'ai',
    locked: true,
    definitionId: definition.id,
    parameters,
    lineWidth: options?.lineWidth ?? 2,
    derivedFromDefinitionId: definition.id,
  };
}

export function buildDefaultAiPresets(): IndicatorPreset[] {
  return AI_INDICATOR_DEFINITIONS.filter(
    (definition) => definition.id !== 'strategy_hybrid_score_v1',
  ).map((definition) => buildAiPreset(definition));
}

export const DEFAULT_AI_PRESETS: IndicatorPreset[] = buildDefaultAiPresets();

export function createAiIndicatorVariantPreset(options: {
  definitionId: string;
  name: string;
  parameters?: Record<string, number | boolean | string>;
  lineWidth?: number;
}): IndicatorPreset | null {
  const definition = findIndicatorDefinition(options.definitionId);
  if (!definition || definition.source !== 'ai') return null;
  const parameters = normalizeParameters(
    definition,
    options.parameters ?? defaultParameters(definition),
  );
  return {
    id: newIndicatorPresetId(),
    name: options.name.trim() || definition.shortLabel,
    source: 'ai',
    locked: false,
    definitionId: definition.id,
    parameters,
    lineWidth: options.lineWidth ?? 2,
    derivedFromDefinitionId: definition.id,
  };
}

export function normalizeIndicatorPresets(
  raw: IndicatorPreset[] | undefined,
): IndicatorPreset[] {
  const merged: IndicatorPreset[] = raw?.length
    ? raw.map((preset) => ({
        ...preset,
        parameters: { ...preset.parameters },
      }))
    : [];

  for (const builtin of DEFAULT_SYSTEM_PRESETS) {
    if (!merged.some((p) => p.id === builtin.id)) {
      merged.unshift({ ...builtin, parameters: { ...builtin.parameters } });
    }
  }
  for (const aiPreset of DEFAULT_AI_PRESETS) {
    if (!merged.some((p) => p.id === aiPreset.id)) {
      merged.unshift({ ...aiPreset, parameters: { ...aiPreset.parameters } });
    }
  }
  return merged;
}

export function findIndicatorPreset(
  presets: IndicatorPreset[],
  presetId: string,
): IndicatorPreset | undefined {
  return presets.find((p) => p.id === presetId);
}

export function presetLabel(preset: IndicatorPreset): string {
  return preset.name;
}

export function presetDerivedHint(preset: IndicatorPreset, presets: IndicatorPreset[]): string | null {
  if (preset.derivedFromPresetId) {
    const parent = findIndicatorPreset(presets, preset.derivedFromPresetId);
    if (parent) return `Basado en ${parent.name}`;
  }
  if (preset.derivedFromDefinitionId && preset.derivedFromDefinitionId !== preset.definitionId) {
    const def = findIndicatorDefinition(preset.derivedFromDefinitionId);
    if (def) return `Basado en ${def.shortLabel}`;
  }
  if (preset.derivedFromDefinitionId) {
    const def = findIndicatorDefinition(preset.derivedFromDefinitionId);
    if (def && preset.source === 'custom' && !preset.locked) {
      return `Edición de ${def.shortLabel}`;
    }
  }
  return null;
}

export function instanceFromPreset(preset: IndicatorPreset): ChartIndicatorInstance {
  return {
    instanceId: newIndicatorInstanceId(preset.definitionId, preset.parameters),
    presetId: preset.id,
    definitionId: preset.definitionId,
    parameters: { ...preset.parameters },
    visible: true,
    lineWidth: preset.lineWidth,
    showLastValue: preset.showLastValue,
  };
}

export function instanceMatchesPreset(
  instance: ChartIndicatorInstance,
  preset: IndicatorPreset,
): boolean {
  return instance.presetId === preset.id;
}

export function findInstanceByPreset(
  instances: ChartIndicatorInstance[],
  presetId: string,
): ChartIndicatorInstance | undefined {
  return instances.find((item) => item.presetId === presetId);
}

export function instanceDisplayName(
  instance: ChartIndicatorInstance,
  presets?: IndicatorPreset[],
): string {
  let base: string;
  if (instance.presetId && presets) {
    const preset = findIndicatorPreset(presets, instance.presetId);
    if (preset) base = preset.name;
    else base = instanceLabel(instance);
  } else {
    base = instanceLabel(instance);
  }
  if (instance.origin === 'finalist-top1') {
    return `TOP 1: ${base}`;
  }
  return base;
}

export function presetFromInstance(
  instance: ChartIndicatorInstance,
  name: string,
  options?: { source?: IndicatorSource; locked?: boolean; derivedFromPresetId?: string },
): IndicatorPreset {
  const definition = findIndicatorDefinition(instance.definitionId);
  return {
    id: newIndicatorPresetId(),
    name: name.trim() || instanceLabel(instance),
    source: options?.source ?? 'custom',
    locked: options?.locked ?? false,
    definitionId: instance.definitionId,
    parameters: { ...instance.parameters },
    lineWidth: instance.lineWidth,
    showLastValue: instance.showLastValue,
    derivedFromPresetId: options?.derivedFromPresetId ?? instance.presetId,
    derivedFromDefinitionId: instance.definitionId,
  };
}

/** Fork explícito: preset sistema → personal editable. */
export function forkIndicatorPreset(
  source: IndicatorPreset,
  patch: {
    name: string;
    parameters?: Record<string, number | boolean | string>;
    lineWidth?: number;
    showLastValue?: boolean;
    source?: IndicatorSource;
    locked?: boolean;
  },
): IndicatorPreset {
  const definition = findIndicatorDefinition(source.definitionId);
  const parameters = definition
    ? normalizeParameters(definition, { ...source.parameters, ...patch.parameters })
    : { ...source.parameters, ...patch.parameters };
  return {
    id: newIndicatorPresetId(),
    name: patch.name.trim() || `${source.name} (copia)`,
    source: patch.source ?? (source.source === 'ai' ? 'custom' : 'custom'),
    locked: patch.locked ?? false,
    definitionId: source.definitionId,
    parameters,
    lineWidth: patch.lineWidth ?? source.lineWidth,
    showLastValue: patch.showLastValue ?? source.showLastValue,
    derivedFromPresetId: source.id,
    derivedFromDefinitionId: source.derivedFromDefinitionId ?? source.definitionId,
  };
}

export function duplicateIndicatorPreset(source: IndicatorPreset, name?: string): IndicatorPreset {
  return forkIndicatorPreset(source, {
    name: name?.trim() || `${source.name} (copia)`,
    parameters: { ...source.parameters },
    lineWidth: source.lineWidth,
    showLastValue: source.showLastValue,
  });
}

export function forkPresetFromDefinition(
  definitionId: string,
  name: string,
  parameters?: Record<string, number | boolean | string>,
): IndicatorPreset | null {
  const definition = findIndicatorDefinition(definitionId);
  if (!definition) return null;
  const normalized = normalizeParameters(definition, parameters ?? defaultParameters(definition));
  return {
    id: newIndicatorPresetId(),
    name: name.trim() || definition.shortLabel,
    source: 'custom',
    locked: false,
    definitionId,
    parameters: normalized,
    lineWidth: 2,
    derivedFromDefinitionId: definitionId,
  };
}

export function collectPresetIdsFromInstances(
  instances: ChartIndicatorInstance[],
  presets: IndicatorPreset[],
): string[] {
  const ids: string[] = [];
  for (const instance of instances) {
    if (instance.presetId) {
      if (!ids.includes(instance.presetId)) ids.push(instance.presetId);
      continue;
    }
    const match = presets.find(
      (p) =>
        p.definitionId === instance.definitionId &&
        JSON.stringify(p.parameters) === JSON.stringify(instance.parameters),
    );
    if (match && !ids.includes(match.id)) ids.push(match.id);
  }
  return ids;
}
