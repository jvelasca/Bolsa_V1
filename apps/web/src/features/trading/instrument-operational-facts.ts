/**
 * V1.70 — Resolver compartido fase + plan operativo (lista ↔ cockpit DECISIÓN).
 * Una sola assembly; React Query comparte cache portfolio/studies.
 */

import type {
  DecisionJournalStudyViewV1,
  OperationalPlanViewV1,
  PositionDto,
} from "@bolsa/shared";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
} from "@bolsa/shared";
import {
  resolveMercadoCockpitPhase,
  type MercadoCockpitPhase,
} from "@/features/trading/operativa-cockpit-phase";
import {
  resolveListOperativaBadge,
  type ListOperativaBadge,
} from "@/features/trading/operativa-phase-toast";

export function hasOpenPositionQuantity(
  position: PositionDto | null | undefined,
): boolean {
  return Boolean(position && Math.abs(Number(position.quantity ?? 0)) > 0);
}

export function resolveInstrumentOperationalPlan(input: {
  position: PositionDto | null;
  study: DecisionJournalStudyViewV1 | null;
  originStudy: DecisionJournalStudyViewV1 | null;
}): OperationalPlanViewV1 {
  if (hasOpenPositionQuantity(input.position)) {
    const aggregate = buildInvestmentPositionAggregate({
      position: input.position!,
      study: input.study,
      originStudy: input.originStudy ?? input.study,
    });
    return buildOperationalPlanFromPosition({
      aggregate,
      markPrice: input.position!.lastPrice ?? null,
    });
  }
  return buildOperationalPlanFromStudy(input.study);
}

export type InstrumentOperationalFactsV1 = {
  phase: MercadoCockpitPhase;
  plan: OperationalPlanViewV1;
  badge: ListOperativaBadge | null;
  target1Touched: boolean;
  target1Managed: boolean;
  decisionId: string | null;
  positionId: string | null;
};

export function resolveInstrumentOperationalFacts(input: {
  instrumentId: string;
  inEstudio: boolean;
  position: PositionDto | null;
  study: DecisionJournalStudyViewV1 | null;
  originStudy: DecisionJournalStudyViewV1 | null;
  inConfirmQueue: boolean;
  orderPendingFill: boolean;
}): InstrumentOperationalFactsV1 {
  const plan = resolveInstrumentOperationalPlan({
    position: input.position,
    study: input.study,
    originStudy: input.originStudy,
  });

  const phase = resolveMercadoCockpitPhase({
    instrumentId: input.instrumentId,
    inEstudio: input.inEstudio,
    hasOpenPosition: hasOpenPositionQuantity(input.position),
    inConfirmQueue: input.inConfirmQueue,
    orderPendingFill: input.orderPendingFill,
    tradePlanStatus: input.study?.tradePlanStatus ?? null,
    hasOperationalPlan:
      input.study?.hasOperationalPlan === true || plan.hasPlan,
  });

  return {
    phase,
    plan,
    badge: resolveListOperativaBadge({
      phase,
      target1Touched: plan.target1Touched,
      target1Managed: plan.target1Managed,
    }),
    target1Touched: plan.target1Touched,
    target1Managed: plan.target1Managed,
    decisionId: input.study?.decisionId ?? null,
    positionId: input.position?.id ?? null,
  };
}
