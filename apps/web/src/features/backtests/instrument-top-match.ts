/**
 * Empareja un backtest detalle con un slot del InstrumentStrategyTop (Finalistas).
 */

import type {
  BacktestRunDetailDto,
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
} from '@bolsa/shared';

export type FinalistHudBadge = {
  rank: 1 | 2 | 3;
  stars: number;
  score: number;
  starsCapped: boolean;
  label: string;
  source: InstrumentStrategyTopSlotV1['source'];
  evidenceLevel: InstrumentStrategyTopV1['evidenceLevel'];
};

/**
 * Match preferente: runId → strategyDefinitionId → strategyType (preset).
 */
export function matchInstrumentTopSlot(
  detail: Pick<BacktestRunDetailDto, 'id' | 'strategyType' | 'strategyDefinitionId'>,
  top: InstrumentStrategyTopV1 | null | undefined,
): InstrumentStrategyTopSlotV1 | null {
  if (!top?.slots?.length) return null;
  const byRun = top.slots.find((s) => s.runId && s.runId === detail.id);
  if (byRun) return byRun;
  if (detail.strategyDefinitionId) {
    const byDef = top.slots.find(
      (s) => s.strategyDefinitionId && s.strategyDefinitionId === detail.strategyDefinitionId,
    );
    if (byDef) return byDef;
  }
  if (detail.strategyType) {
    const byType = top.slots.find((s) => s.strategyType === detail.strategyType);
    if (byType) return byType;
  }
  return null;
}

export function finalistHudBadgeFromTop(
  detail: Pick<BacktestRunDetailDto, 'id' | 'strategyType' | 'strategyDefinitionId'>,
  top: InstrumentStrategyTopV1 | null | undefined,
): FinalistHudBadge | null {
  const slot = matchInstrumentTopSlot(detail, top);
  if (!slot || !(slot.stars > 0)) return null;
  return {
    rank: slot.rank,
    stars: slot.stars,
    score: slot.score,
    starsCapped: Boolean(slot.starsCapped),
    label: slot.label,
    source: slot.source,
    evidenceLevel: top!.evidenceLevel,
  };
}
