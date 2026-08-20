import type {
  ChartIndicatorInstance,
  IndicatorSource,
} from "./indicators-catalog.js";
import {
  findIndicatorDefinition,
  instanceLabel,
  newIndicatorInstanceId,
} from "./indicators-catalog.js";
import {
  collectPresetIdsFromInstances,
  instanceFromPreset,
  type IndicatorPreset,
} from "./indicator-presets.js";
import { instanceSpecKey } from "./indicators-runtime.js";

/** @deprecated Usar presetIds en plantillas nuevas. */
export interface IndicatorTemplateItem {
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
  visible: boolean;
}

/**
 * Plantilla / grupo de presets para aplicar al gráfico.
 * Las estrategias referencian sus propios IndicatorSpec[]; no heredan plantillas automáticamente.
 */
export interface IndicatorTemplate {
  id: string;
  name: string;
  source?: IndicatorSource;
  /** No borrable (sistema o semilla). */
  locked?: boolean;
  /** @deprecated Compatibilidad — usar presetIds. */
  builtin?: boolean;
  presetIds?: string[];
  items?: IndicatorTemplateItem[];
}

/** Acceso directo en la barra de indicadores (favoritos por lista). */
export interface IndicatorFavoriteRef {
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
  shortLabel?: string;
  presetId?: string;
}

export const DEFAULT_INDICATOR_FAVORITES: IndicatorFavoriteRef[] = [
  {
    definitionId: "volume",
    parameters: {},
    presetId: "preset-sys-volume-default",
  },
  {
    definitionId: "sma",
    parameters: { period: 20 },
    presetId: "preset-sys-sma-default",
  },
  {
    definitionId: "rsi",
    parameters: { period: 14 },
    presetId: "preset-sys-rsi-default",
  },
];

/** Accesos directos de plantillas en la barra del gráfico (favoritos). */
/** Vacío = solo icono con plantilla activa; chips opcionales vía estrella. */
export const DEFAULT_INDICATOR_TEMPLATE_FAVORITES: string[] = [];

export const BUILTIN_PERSONAL_TEMPLATE_ID = "builtin-personal";

export const DEFAULT_INDICATOR_TEMPLATES: IndicatorTemplate[] = [
  {
    id: "builtin-swing",
    name: "Swing",
    source: "builtin",
    locked: true,
    builtin: true,
    presetIds: [
      "preset-sys-volume-default",
      "preset-sys-sma-50",
      "preset-sys-rsi-default",
    ],
  },
  {
    id: "builtin-day",
    name: "Intradía",
    source: "builtin",
    locked: true,
    builtin: true,
    presetIds: [
      "preset-sys-volume-default",
      "preset-sys-ema-default",
      "preset-sys-rsi-default",
    ],
  },
  {
    id: BUILTIN_PERSONAL_TEMPLATE_ID,
    name: "Personal",
    source: "custom",
    locked: true,
    builtin: true,
    presetIds: [],
  },
];

export function favoriteRefKey(ref: IndicatorFavoriteRef): string {
  if (ref.presetId) return `preset:${ref.presetId}`;
  return instanceSpecKey(ref.definitionId, ref.parameters);
}

export function favoriteRefLabel(ref: IndicatorFavoriteRef): string {
  if (ref.shortLabel) return ref.shortLabel;
  const definition = findIndicatorDefinition(ref.definitionId);
  if (!definition) return ref.definitionId;
  const period = ref.parameters.period;
  if (period != null) return `${definition.shortLabel}${period}`;
  return definition.shortLabel;
}

export function favoriteRefFromInstance(
  instance: ChartIndicatorInstance,
): IndicatorFavoriteRef {
  return {
    definitionId: instance.definitionId,
    parameters: { ...instance.parameters },
    presetId: instance.presetId,
  };
}

export function instanceMatchesRef(
  instance: ChartIndicatorInstance,
  ref: IndicatorFavoriteRef,
): boolean {
  if (ref.presetId) return instance.presetId === ref.presetId;
  return (
    favoriteRefKey(favoriteRefFromInstance(instance)) === favoriteRefKey(ref)
  );
}

export function findInstanceByRef(
  instances: ChartIndicatorInstance[],
  ref: IndicatorFavoriteRef,
): ChartIndicatorInstance | undefined {
  return instances.find((item) => instanceMatchesRef(item, ref));
}

export function newIndicatorTemplateId(): string {
  return `itpl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function resolveTemplatePresetIds(template: IndicatorTemplate): string[] {
  if (template.presetIds?.length) return [...template.presetIds];
  return [];
}

export function templateIncludesPreset(
  template: IndicatorTemplate,
  presetId: string,
): boolean {
  return resolveTemplatePresetIds(template).includes(presetId);
}

export function normalizeIndicatorTemplates(
  raw: IndicatorTemplate[] | undefined,
): IndicatorTemplate[] {
  const merged: IndicatorTemplate[] = (raw?.length ? raw : []).map((t) => ({
    ...t,
    locked: t.locked ?? t.builtin ?? false,
    source: (t.source ?? (t.builtin ? "builtin" : "custom")) as IndicatorSource,
    presetIds: t.presetIds?.length
      ? [...t.presetIds]
      : resolveTemplatePresetIds(t),
    items: Array.isArray(t.items)
      ? t.items.map((item) => ({ ...item, parameters: { ...item.parameters } }))
      : undefined,
  }));

  if (!merged.length) {
    return DEFAULT_INDICATOR_TEMPLATES.map((t) => ({
      ...t,
      presetIds: [...(t.presetIds ?? [])],
    }));
  }

  for (const builtin of DEFAULT_INDICATOR_TEMPLATES) {
    if (!merged.some((t) => t.id === builtin.id)) {
      merged.unshift({
        ...builtin,
        locked: builtin.locked ?? true,
        source: (builtin.source ?? "builtin") as IndicatorSource,
        presetIds: [...(builtin.presetIds ?? [])],
      });
    }
  }
  return merged;
}

export function normalizeIndicatorFavoritesByListId(
  raw: Record<string, IndicatorFavoriteRef[]> | undefined,
): Record<string, IndicatorFavoriteRef[]> {
  if (!raw) return {};
  const out: Record<string, IndicatorFavoriteRef[]> = {};
  for (const [listId, refs] of Object.entries(raw)) {
    if (!Array.isArray(refs) || !refs.length) continue;
    out[listId] = refs.map((ref) => ({
      definitionId: ref.definitionId,
      parameters: { ...ref.parameters },
      ...(ref.shortLabel ? { shortLabel: ref.shortLabel } : {}),
      ...(ref.presetId ? { presetId: ref.presetId } : {}),
    }));
  }
  return out;
}

export function instancesFromTemplate(
  template: IndicatorTemplate,
  presets: IndicatorPreset[],
): ChartIndicatorInstance[] {
  const presetIds = resolveTemplatePresetIds(template);
  if (presetIds.length > 0) {
    return presetIds
      .map((id) => presets.find((p) => p.id === id))
      .filter((p): p is IndicatorPreset => Boolean(p))
      .map((preset) => instanceFromPreset(preset));
  }
  if (!template.items?.length) return [];
  return template.items.map((item) => ({
    instanceId: newIndicatorInstanceId(item.definitionId, item.parameters),
    definitionId: item.definitionId,
    parameters: { ...item.parameters },
    visible: item.visible,
  }));
}

export function createBlankIndicatorTemplate(
  name = "Nuevo grupo",
): IndicatorTemplate {
  return {
    id: newIndicatorTemplateId(),
    name,
    source: "custom",
    locked: false,
    presetIds: [],
  };
}

export function indicatorTemplateFromInstances(
  instances: ChartIndicatorInstance[],
  name: string,
  presets: IndicatorPreset[],
): IndicatorTemplate {
  return {
    id: newIndicatorTemplateId(),
    name,
    source: "custom",
    locked: false,
    presetIds: collectPresetIdsFromInstances(instances, presets),
  };
}

export function templateItemLabel(item: IndicatorTemplateItem): string {
  return instanceLabel({
    instanceId: "x",
    definitionId: item.definitionId,
    parameters: item.parameters,
    visible: item.visible,
  });
}

export function presetIdsFromTemplate(template: IndicatorTemplate): string[] {
  return resolveTemplatePresetIds(template);
}

export function ensurePresetInTemplate(
  template: IndicatorTemplate,
  presetId: string,
): IndicatorTemplate {
  const current = resolveTemplatePresetIds(template);
  if (current.includes(presetId)) return template;
  return { ...template, presetIds: [...current, presetId], items: undefined };
}

export function togglePresetInTemplate(
  template: IndicatorTemplate,
  presetId: string,
): IndicatorTemplate {
  const current = resolveTemplatePresetIds(template);
  const next = current.includes(presetId)
    ? current.filter((id) => id !== presetId)
    : [...current, presetId];
  return { ...template, presetIds: next, items: undefined };
}

export function templateHasIndicators(template: IndicatorTemplate): boolean {
  if ((template.presetIds?.length ?? 0) > 0) return true;
  return (template.items?.length ?? 0) > 0;
}

export function normalizeIndicatorTemplateFavorites(
  raw?: string[] | null,
  validIds?: readonly string[],
): string[] {
  if (raw == null) return [...DEFAULT_INDICATOR_TEMPLATE_FAVORITES];
  if (raw.length === 0) return [];
  const valid = validIds ? new Set(validIds) : null;
  const seen = new Set<string>();
  const next: string[] = [];
  for (const id of raw) {
    if (!id || seen.has(id)) continue;
    if (valid && !valid.has(id)) continue;
    seen.add(id);
    next.push(id);
  }
  return next;
}

export function toggleIndicatorTemplateFavoriteList(
  favorites: string[],
  templateId: string,
): string[] {
  if (favorites.includes(templateId)) {
    return favorites.filter((id) => id !== templateId);
  }
  return [...favorites, templateId];
}
