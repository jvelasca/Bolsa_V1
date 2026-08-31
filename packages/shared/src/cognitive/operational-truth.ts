/**
 * OperationalTruth — proyección canónica de posición abierta (V1.37).
 * No es entidad, endpoint ni segundo motor: compone PositionDecision +
 * OperationalPlanView. Mercado / Hoy / Journal / Operaciones leen esto.
 * protect_hint thin ≠ autoridad de acción.
 */

import type { PositionDto } from "../types.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import { buildInvestmentPositionAggregate } from "./investment-position-aggregate.js";
import { type MesaNextActionV1 } from "./mesa-next-action.js";
import {
  buildOperationalPlanFromPosition,
  isTrailingStopApplied,
  type OperationalPlanViewV1,
} from "./operational-plan-view.js";
import {
  positionOperatingCtaFromDecision,
  primaryPositionExitCta,
  type PositionExitCtaKindV1,
  type PositionOperatingCtaV1,
} from "./position-decision-copy.js";
import type {
  PositionAttentionV1,
  PositionDecisionActionV1,
  PositionDecisionV1,
  PositionNextEventV1,
  PositionProtectionV1,
  PositionReconHealthV1,
} from "./position-decision.js";
import { buildPositionDecisionFromDto } from "./position-state-from-dto.js";

export type OperationalTruthExecutionHintV1 =
  | "none"
  | "recommended_not_executed";

export type OperationalTruthLevelsV1 = {
  entry: number | null;
  stopOperativo: number | null;
  stopInicial: number | null;
  target1: number | null;
  target2: number | null;
};

export type OperationalTruthPnlV1 = {
  unrealizedPnlPct: number | null;
  unrealizedR: number | null;
};

export type OperationalTruthTrailingV1 = {
  active: boolean;
  applied: boolean;
  hint: number | null;
};

export type OperationalTruthV1 = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  asOf: string | null;
  currentPrice: number | null;
  pnl: OperationalTruthPnlV1;
  levels: OperationalTruthLevelsV1;
  trailing: OperationalTruthTrailingV1;
  plan: OperationalPlanViewV1;
  decision: PositionDecisionV1;
  primaryCta: PositionOperatingCtaV1;
  attention: PositionAttentionV1;
  protection: PositionProtectionV1;
  nextEvent: PositionNextEventV1;
  reconHealth: PositionReconHealthV1;
  executionHint: OperationalTruthExecutionHintV1;
};

export type BuildOperationalTruthInputV1 = {
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  portfolioReconStatus?: string | null;
  /** Stamp explícito; si falta, `decision.marketAsOf` (no se inventa otro). */
  asOf?: string | null;
  /** Orden de salida/protección ya en vuelo. */
  orderPending?: boolean;
};

export type OperationalTruthSurfaceSnapshotV1 = {
  action: PositionDecisionActionV1;
  ctaLabel: string;
  ctaKind: PositionExitCtaKindV1;
  protection: PositionProtectionV1;
  nextEvent: PositionNextEventV1;
  reconHealth: PositionReconHealthV1;
  asOf: string | null;
  stopOperativo: number | null;
  target1: number | null;
  target2: number | null;
  executionHint: OperationalTruthExecutionHintV1;
};

const ACTIONABLE_CTA = new Set<PositionExitCtaKindV1>([
  "protect",
  "reduce",
  "exit",
  "review",
]);

const RECOMMENDED_ACTIONS = new Set<PositionDecisionActionV1>([
  "PROTECT",
  "REDUCE",
  "TAKE_PROFIT",
  "EXIT",
]);

export function buildOperationalTruth(
  input: BuildOperationalTruthInputV1,
): OperationalTruthV1 | null {
  const { position } = input;
  const decision = buildPositionDecisionFromDto(position, {
    portfolioReconStatus:
      typeof input.portfolioReconStatus === "string" &&
      input.portfolioReconStatus.trim()
        ? input.portfolioReconStatus
        : "ok",
    at: input.asOf,
  });
  if (!decision) return null;

  const aggregate = buildInvestmentPositionAggregate({
    position,
    study: input.study,
    originStudy: input.originStudy,
  });
  const markPrice =
    typeof position.lastPrice === "number" &&
    Number.isFinite(position.lastPrice)
      ? position.lastPrice
      : null;
  const plan = buildOperationalPlanFromPosition({
    aggregate,
    markPrice,
  });

  const applied = isTrailingStopApplied({
    direction: plan.direction,
    stopVigente: plan.stopVigente,
    trailingStopHint: plan.trailingStopHint,
  });

  const asOf =
    typeof input.asOf === "string" && input.asOf.trim()
      ? input.asOf.trim()
      : decision.marketAsOf;

  const executionHint: OperationalTruthExecutionHintV1 =
    !input.orderPending && RECOMMENDED_ACTIONS.has(decision.action)
      ? "recommended_not_executed"
      : "none";

  const primaryCta = positionOperatingCtaFromDecision(decision);

  return {
    instrumentId: position.instrumentId,
    symbol: position.symbol,
    positionId: position.id,
    asOf,
    currentPrice: markPrice,
    pnl: {
      unrealizedPnlPct:
        typeof position.unrealizedPnlPct === "number" &&
        Number.isFinite(position.unrealizedPnlPct)
          ? position.unrealizedPnlPct
          : null,
      unrealizedR: plan.unrealizedR,
    },
    levels: {
      entry: plan.entry,
      stopOperativo: plan.stopVigente,
      stopInicial: plan.stopInicial,
      target1: plan.target1,
      target2: plan.target2,
    },
    trailing: {
      active: plan.trailingActive,
      applied,
      hint: plan.trailingStopHint,
    },
    plan,
    decision,
    primaryCta,
    attention: decision.attention,
    protection: decision.protection,
    nextEvent: decision.nextEvent,
    reconHealth: decision.reconHealth,
    executionHint,
  };
}

export function operationalTruthSurfaceSnapshot(
  truth: OperationalTruthV1,
): OperationalTruthSurfaceSnapshotV1 {
  return {
    action: truth.decision.action,
    ctaLabel: truth.primaryCta.label,
    ctaKind: truth.primaryCta.kind,
    protection: truth.protection,
    nextEvent: truth.nextEvent,
    reconHealth: truth.reconHealth,
    asOf: truth.asOf,
    stopOperativo: truth.levels.stopOperativo,
    target1: truth.levels.target1,
    target2: truth.levels.target2,
    executionHint: truth.executionHint,
  };
}

/** CTA de fila / inbox para posición abierta — ignora protect_hint thin. */
export function mesaNextActionFromDecision(
  decision: PositionDecisionV1,
): MesaNextActionV1 {
  const cta = positionOperatingCtaFromDecision(decision);
  return {
    kind: cta.kind,
    label: cta.label,
    allowsEntry: false,
  };
}

export function mesaNextActionFromOperationalTruth(
  truth: OperationalTruthV1,
): MesaNextActionV1 {
  return {
    kind: truth.primaryCta.kind,
    label: truth.primaryCta.label,
    allowsEntry: false,
  };
}

export function openPositionNeedsAction(decision: PositionDecisionV1): boolean {
  return ACTIONABLE_CTA.has(primaryPositionExitCta(decision));
}

export function formatOperationalAsOf(asOf: string | null): string | null {
  if (!asOf?.trim()) return null;
  const ms = Date.parse(asOf);
  if (!Number.isFinite(ms)) return asOf.trim();
  const iso = new Date(ms).toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

export function formatExecutionHintCopy(
  truth: OperationalTruthV1,
): string | null {
  if (truth.executionHint !== "recommended_not_executed") return null;
  switch (truth.decision.action) {
    case "EXIT":
      return "Salida recomendada · aún no ejecutada.";
    case "PROTECT":
      return "Protección recomendada · aún no ejecutada.";
    case "REDUCE":
    case "TAKE_PROFIT":
      return "Reducción recomendada · aún no ejecutada.";
    default:
      return "Acción recomendada · aún no ejecutada.";
  }
}
