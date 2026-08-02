/**
 * Tipo ejecutable de un slot Finalistas = preset de la definición, no el seed
 * proxy de Lab (p. ej. SuperTrend → grid SMA no debe dejar type=supertrend_follow).
 */

import type { InstrumentStrategyTopSlotV1 } from '@bolsa/shared';
import { isBacktestStrategyType } from '@bolsa/shared';

/**
 * Prioridad: preset de la def guardada → nested definition.presetKey →
 * tipo del slot solo si es preset válido.
 */
export function resolveExecutableStrategyType(opts: {
  slotStrategyType?: string | null;
  definitionPresetKey?: string | null;
  nestedPresetKey?: string | null;
}): string | null {
  for (const raw of [
    opts.definitionPresetKey,
    opts.nestedPresetKey,
    opts.slotStrategyType,
  ]) {
    const t = typeof raw === 'string' ? raw.trim() : '';
    if (t && isBacktestStrategyType(t)) return t;
  }
  const fallback = opts.slotStrategyType?.trim();
  return fallback || null;
}

export function sanitizeTopSlotStrategyType(
  slot: InstrumentStrategyTopSlotV1,
  definitionPresetKey?: string | null,
  nestedPresetKey?: string | null,
): InstrumentStrategyTopSlotV1 {
  const next = resolveExecutableStrategyType({
    slotStrategyType: slot.strategyType,
    definitionPresetKey,
    nestedPresetKey,
  });
  if (!next || next === slot.strategyType) return slot;
  return { ...slot, strategyType: next };
}

/** Aplica presetKey conocido por strategyDefinitionId. */
export function sanitizeTopSlotsStrategyTypes(
  slots: InstrumentStrategyTopSlotV1[],
  presetByDefinitionId: ReadonlyMap<string, string | null | undefined>,
): InstrumentStrategyTopSlotV1[] {
  return slots.map((slot) => {
    const id = slot.strategyDefinitionId?.trim();
    if (!id) return slot;
    return sanitizeTopSlotStrategyType(slot, presetByDefinitionId.get(id) ?? null);
  });
}
