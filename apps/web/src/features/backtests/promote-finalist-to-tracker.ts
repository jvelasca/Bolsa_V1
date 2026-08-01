/**
 * Puente Finalistas → Rastreador (Camino B / Radar).
 * Construye CreateTrackerDefinitionDto desde un slot TOP — no ejecuta paper.
 *
 * @see docs/engineering/research-radar-unification-2026-07-31.md
 */

import {
  isKernelTimeframe,
  type CreateTrackerDefinitionDto,
  type ExecutionMode,
  type InstrumentStrategyTopSlotV1,
  type KernelTimeframe,
  type TrackerScheduleKind,
} from '@bolsa/shared';
import { pickAlarmPolicyId } from '@/features/screeners/tracker-alarms';

export type PromoteFinalistToTrackerInput = {
  instrumentId: string;
  symbol?: string | null;
  /** Timeframe del TOP (p. ej. 1d). */
  timeframe: string;
  slot: InstrumentStrategyTopSlotV1;
  /** Versión del TOP (trazabilidad en sourcePrompt). */
  topVersion?: number;
  scheduleKind?: TrackerScheduleKind;
  defaultExecutionPolicyId?: string | null;
  /** Políticas disponibles: si no hay defaultExecutionPolicyId, elige inform/alert. */
  alarmPolicies?: Array<{ id: string; mode: ExecutionMode; enabled: boolean }>;
  /** Si se pasa, el universo es la lista; si no, solo el instrumento. */
  listId?: string | null;
};

export type PromoteFinalistToTrackerResult =
  | { ok: true; dto: CreateTrackerDefinitionDto }
  | { ok: false; error: string };

export function kernelTimeframeFromTop(timeframe: string): KernelTimeframe {
  return isKernelTimeframe(timeframe) ? timeframe : '1d';
}

export function buildTrackerNameFromFinalist(input: {
  symbol?: string | null;
  slot: InstrumentStrategyTopSlotV1;
}): string {
  const sym = (input.symbol ?? 'VALOR').trim() || 'VALOR';
  const label = input.slot.label.trim() || 'estrategia';
  const raw = `Radar · ${sym} · #${input.slot.rank} ${label}`;
  return raw.length > 80 ? `${raw.slice(0, 77)}…` : raw;
}

/**
 * Valida el slot y construye el DTO de creación de rastreador.
 */
export function buildTrackerFromFinalistSlot(
  input: PromoteFinalistToTrackerInput,
): PromoteFinalistToTrackerResult {
  const strategyDefinitionId = input.slot.strategyDefinitionId?.trim();
  if (!strategyDefinitionId) {
    return {
      ok: false,
      error: 'El slot no tiene estrategia guardada (strategyDefinitionId).',
    };
  }
  if (!input.instrumentId.trim()) {
    return { ok: false, error: 'Falta instrumentId.' };
  }

  const timeframe = kernelTimeframeFromTop(input.timeframe);
  const scheduleKind: TrackerScheduleKind =
    input.scheduleKind === 'on_bar_close'
      ? 'on_bar_close'
      : input.scheduleKind === 'cron'
        ? 'cron'
        : 'manual';

  const universe = input.listId?.trim()
    ? { listId: input.listId.trim() }
    : { instrumentIds: [input.instrumentId] };

  const policyId =
    input.defaultExecutionPolicyId ??
    (input.alarmPolicies ? pickAlarmPolicyId(input.alarmPolicies) : null);

  const dto: CreateTrackerDefinitionDto = {
    name: buildTrackerNameFromFinalist({
      symbol: input.symbol,
      slot: input.slot,
    }),
    strategyDefinitionId,
    universe,
    timeframe,
    maxResults: 20,
    schedule: { kind: scheduleKind },
    defaultExecutionPolicyId: policyId,
    origin: 'assisted',
    sourcePrompt: `finalist:${input.instrumentId}:${timeframe}:r${input.slot.rank}:v${input.topVersion ?? 0}`,
    enabled: true,
  };

  return { ok: true, dto };
}

/** Deep-link al hub Screeners tras crear el rastreador. */
export function screenersHrefAfterTrackerCreate(trackerId?: string): string {
  if (!trackerId) return '/screeners';
  const params = new URLSearchParams({ trackerId });
  return `/screeners?${params.toString()}`;
}
