/**
 * Embudo C: helpers para promover slots lab_validated (usados desde Coach²,
 * no desde el Lab). Lab nunca escribe Finalistas.
 */

import type {
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
  UpsertInstrumentStrategyTopRequestV1,
} from '@bolsa/shared';
import { resolveLabEvidenceForFinalistsSave } from '@/features/backtests/finalists-stability-summary';

export type LabPromotionSlotInput = {
  label: string;
  strategyDefinitionId: string;
  strategyType?: string | null;
  score: number;
  stars?: number;
  totalReturnPct?: number | null;
  excessReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  lateReturnPct?: number | null;
  runId?: string | null;
};

/** Estrellas 1–5 en pasos de 0.5 (medias estrellas). */
function clampStars(score: number, explicit?: number): number {
  const roundHalf = (n: number) => Math.round(n * 2) / 2;
  if (explicit != null && Number.isFinite(explicit)) {
    return Math.min(5, Math.max(1, roundHalf(explicit)));
  }
  return Math.min(5, Math.max(1, roundHalf(score / 20)));
}

function slotIdentityKey(
  slot: Pick<InstrumentStrategyTopSlotV1, 'strategyDefinitionId' | 'strategyType' | 'label'>,
): string {
  if (slot.strategyDefinitionId) return `id:${slot.strategyDefinitionId}`;
  if (slot.strategyType) return `type:${slot.strategyType}`;
  return `label:${slot.label.trim().toLowerCase()}`;
}

/** lab_validated / active: todos los slots necesitan runId (Checklist). */
export function assertLabValidatedSlotsHaveRunId(
  slots: InstrumentStrategyTopSlotV1[],
): void {
  const missing = slots.filter((s) => !s.runId?.trim()).map((s) => s.label || `#${s.rank}`);
  if (missing.length > 0) {
    throw new Error(
      `lab_validated TOP requires runId on every slot (missing: ${missing.join(', ')})`,
    );
  }
}

/**
 * Como máximo una entrada por estrategia (definitionId y strategyType).
 * Reasigna ranks 1..N.
 */
export function dedupeInstrumentTopSlots(
  slots: InstrumentStrategyTopSlotV1[],
  limit = 3,
): InstrumentStrategyTopSlotV1[] {
  const seenIds = new Set<string>();
  const seenTypes = new Set<string>();
  const seenKeys = new Set<string>();
  const out: InstrumentStrategyTopSlotV1[] = [];
  for (const slot of slots) {
    if (slot.strategyDefinitionId && seenIds.has(slot.strategyDefinitionId)) continue;
    if (slot.strategyType && seenTypes.has(slot.strategyType)) continue;
    const key = slotIdentityKey(slot);
    if (seenKeys.has(key)) continue;
    if (slot.strategyDefinitionId) seenIds.add(slot.strategyDefinitionId);
    if (slot.strategyType) seenTypes.add(slot.strategyType);
    seenKeys.add(key);
    out.push(slot);
    if (out.length >= limit) break;
  }
  return out.map((s, i) => ({ ...s, rank: (i + 1) as 1 | 2 | 3 }));
}

/**
 * Inserta el candidato lab como #1; conserva hasta 2 slots previos distintos
 * (por definitionId y por strategyType, para no duplicar p.ej. dos SMA).
 */
export function buildLabPromotionUpsert(opts: {
  existing: InstrumentStrategyTopV1 | null;
  instrumentId: string;
  symbol?: string | null;
  timeframe: string;
  periodLabel?: string | null;
  promoted: LabPromotionSlotInput;
  labFacts?: Record<string, unknown> | null;
  coachHeadline?: string | null;
}): UpsertInstrumentStrategyTopRequestV1 {
  return buildLabPromotionUpsertMany({
    ...opts,
    promoted: [opts.promoted],
  });
}

/**
 * Promueve varios Mejores del Lab (orden = prioridad; el primero es #1).
 * Sustituye slots previos del mismo type/id; rellena con previos distintos.
 */
export function buildLabPromotionUpsertMany(opts: {
  existing: InstrumentStrategyTopV1 | null;
  instrumentId: string;
  symbol?: string | null;
  timeframe: string;
  periodLabel?: string | null;
  promoted: LabPromotionSlotInput[];
  labFacts?: Record<string, unknown> | null;
  coachHeadline?: string | null;
}): UpsertInstrumentStrategyTopRequestV1 {
  const labSlots: InstrumentStrategyTopSlotV1[] = opts.promoted.map((p, i) => ({
    rank: (i + 1) as 1 | 2 | 3,
    label: p.label,
    strategyType: p.strategyType ?? null,
    strategyDefinitionId: p.strategyDefinitionId,
    stars: clampStars(p.score, p.stars),
    score: p.score,
    starsCapped: false,
    runId: p.runId ?? null,
    source: 'optimized' as const,
    totalReturnPct: p.totalReturnPct ?? null,
    excessReturnPct: p.excessReturnPct ?? null,
    maxDrawdownPct: p.maxDrawdownPct ?? null,
    lateReturnPct: p.lateReturnPct ?? null,
  }));

  const promotedIds = new Set(
    labSlots.map((s) => s.strategyDefinitionId).filter(Boolean) as string[],
  );
  const promotedTypes = new Set(
    labSlots.map((s) => s.strategyType).filter(Boolean) as string[],
  );

  const prior = (opts.existing?.slots ?? []).filter((s) => {
    if (s.strategyDefinitionId && promotedIds.has(s.strategyDefinitionId)) return false;
    if (s.strategyType && promotedTypes.has(s.strategyType)) return false;
    // lab_validated no puede arrastrar slots sin runId (Checklist).
    if (!s.runId?.trim()) return false;
    return true;
  });

  const slots = dedupeInstrumentTopSlots([...labSlots, ...prior], 3);
  assertLabValidatedSlotsHaveRunId(slots);
  const topLabel = slots[0]?.label ?? 'lab';
  const slot1 = slots[0];
  const labEvidence =
    (opts.labFacts?.labEvidence as object | undefined) ??
    resolveLabEvidenceForFinalistsSave({
      strategyDefinitionId: slot1?.strategyDefinitionId,
      runId: slot1?.runId,
    });

  return {
    instrumentId: opts.instrumentId,
    symbol: opts.symbol ?? opts.existing?.symbol ?? null,
    timeframe: opts.timeframe,
    periodLabel: opts.periodLabel ?? opts.existing?.periodLabel ?? null,
    status: 'active',
    evidenceLevel: 'lab_validated',
    slots,
    coachHeadline:
      opts.coachHeadline ??
      opts.existing?.coachHeadline ??
      `TOP activo tras lab · #1 ${topLabel}`,
    coachFacts: {
      ...(opts.existing?.coachFacts ?? {}),
      ...(opts.labFacts ?? {}),
      ...(labEvidence ? { labEvidence } : {}),
      promotedAt: new Date().toISOString(),
      promotionSource: opts.promoted.length > 1 ? 'lab_adopt_many' : 'lab_adopt',
      promotedCount: opts.promoted.length,
    },
  };
}

/** True si hay evidencia OOS/WF/CPCV suficiente para promover. */
export function canPromoteTopFromLabEvidence(kind: string | null | undefined): boolean {
  return kind === 'holdout' || kind === 'walkforward' || kind === 'cpcv';
}
