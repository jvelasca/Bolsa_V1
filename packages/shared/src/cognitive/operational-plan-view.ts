/**
 * OperationalPlanView — proyección visual única del plan operativo (V1.21).
 * No es entidad nueva: lee TradePlan / study geometry o PositionState.
 * Mismo significado en Hoy, Operativa, Confirm y ficha de posición.
 * Trailing = proyección thin (mapTrailPlan); no escribe currentStop.
 *
 * @see ADR-041 · ADR-032 · ADR-033
 */

import { NO_OPERATIONAL_PLAN_COPY } from "./decision-journal-study.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { InvestmentPositionAggregateV1 } from "./investment-position-aggregate.js";
import type { PositionStateV1 } from "./position-state.js";
import type { TradePlanDirectionV1, TradePlanV1 } from "./trade-plan.js";
import { mapTrailPlan } from "./trail-plan.js";

export type OperationalPlanPhaseV1 =
  | "none"
  | "prepared"
  | "triggered"
  | "position"
  | "closed";

export type OperationalPlanViewV1 = {
  phase: OperationalPlanPhaseV1;
  /** Copy corto del estado (Preparada / Posición activa / …). */
  phaseLabel: string;
  entry: number | null;
  /** Stop vigente (post-fill = currentStop; pre-fill = plan stop). */
  stopVigente: number | null;
  /** Stop inicial / planificado (traza). */
  stopInicial: number | null;
  target1: number | null;
  target2: number | null;
  /**
   * @deprecated Compat: touched **o** managed. No usar como «ya reducido».
   * Preferir target1Touched / target1Managed.
   */
  target1Reached: boolean;
  /** @deprecated Igual que target1Reached para T2. */
  target2Reached: boolean;
  /** Precio cruzó T1. ≠ reducción ejecutada. */
  target1Touched: boolean;
  /** Existe `target1AchievedAt` (reduce T1 firmado). */
  target1Managed: boolean;
  target2Touched: boolean;
  /** Siempre false hasta que exista sello T2. */
  target2Managed: boolean;
  expectedRR: number | null;
  riskR: number | null;
  currentPrice: number | null;
  unrealizedR: number | null;
  /** Thin trail tip/ratchet — advisory; ≠ autoridad de stop. */
  trailingActive: boolean;
  trailingPeakMfeR: number | null;
  /** Precio implícito del pico (entry ± peakMfeR × R). */
  trailingPeakPrice: number | null;
  trailingStopHint: number | null;
  trailingDistanceR: number | null;
  /** Quién propone la siguiente acción de salida (informativo). */
  exitAuthorityHint: string | null;
  hasPlan: boolean;
  emptyCopy: string;
};

const EMPTY_TRAIL = {
  trailingActive: false,
  trailingPeakMfeR: null as number | null,
  trailingPeakPrice: null as number | null,
  trailingStopHint: null as number | null,
  trailingDistanceR: null as number | null,
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function targetTouchedByPrice(
  isShort: boolean,
  price: number | null,
  target: number | null,
): boolean {
  if (price == null || target == null) return false;
  return isShort ? price <= target : price >= target;
}

/** Copy honesto: pendiente / alcanzado (tocado) / pendiente de gestión / gestionado. */
export function targetProgressHint(touched: boolean, managed: boolean): string {
  if (managed) return "✓ gestionado";
  if (touched) return "● alcanzado · ○ pendiente de gestión";
  return "○ pendiente";
}

function phaseFromTradePlanStatus(
  status: string | null | undefined,
): OperationalPlanPhaseV1 {
  switch (status) {
    case "ARMED":
      return "prepared";
    case "TRIGGERED":
      return "triggered";
    case "WATCH":
      return "prepared";
    default:
      return "none";
  }
}

function phaseLabel(phase: OperationalPlanPhaseV1): string {
  switch (phase) {
    case "prepared":
      return "Preparada";
    case "triggered":
      return "Disparador / Propuesta";
    case "position":
      return "Posición activa";
    case "closed":
      return "Cerrada";
    default:
      return "Sin plan";
  }
}

function projectTrailing(input: {
  direction: TradePlanDirectionV1 | null | undefined;
  entry: number | null;
  structuralStop: number | null;
  peakMfeR: number | null;
  currentR: number | null;
}): Pick<
  OperationalPlanViewV1,
  | "trailingActive"
  | "trailingPeakMfeR"
  | "trailingPeakPrice"
  | "trailingStopHint"
  | "trailingDistanceR"
> {
  const trail = mapTrailPlan({
    direction: input.direction,
    entry: input.entry,
    structuralStop: input.structuralStop,
    peakMfeR: input.peakMfeR,
    currentR: input.currentR,
  });
  if (trail.status !== "tip" && trail.status !== "ratchet") {
    return EMPTY_TRAIL;
  }
  const entry = input.entry;
  const stop = input.structuralStop;
  let peakPrice: number | null = null;
  if (
    finite(entry) &&
    finite(stop) &&
    finite(trail.peakMfeR) &&
    Math.abs(entry - stop) > 0
  ) {
    const R = Math.abs(entry - stop);
    const sign = input.direction === "short" ? -1 : 1;
    peakPrice =
      Math.round((entry + sign * trail.peakMfeR! * R) * 10000) / 10000;
  }
  return {
    trailingActive: true,
    trailingPeakMfeR: trail.peakMfeR,
    trailingPeakPrice: peakPrice,
    trailingStopHint: trail.suggestedTrailStop,
    trailingDistanceR: trail.trailDistanceR,
  };
}

/** Pre-entrada: study journal o TradePlan. */
export function buildOperationalPlanFromStudy(
  study: DecisionJournalStudyViewV1 | null | undefined,
  tradePlan?: TradePlanV1 | null,
): OperationalPlanViewV1 {
  const hasPlan =
    study?.hasOperationalPlan === true ||
    (tradePlan != null &&
      (tradePlan.status === "ARMED" || tradePlan.status === "TRIGGERED"));
  const entry =
    (finite(tradePlan?.entry) ? tradePlan!.entry! : null) ??
    (finite(study?.entry) ? study!.entry! : null);
  const stop =
    (finite(tradePlan?.structuralStop) ? tradePlan!.structuralStop! : null) ??
    (finite(study?.stop) ? study!.stop! : null);
  const t1 =
    (finite(tradePlan?.target1) ? tradePlan!.target1! : null) ??
    (finite(study?.target1) ? study!.target1! : null);
  const t2 =
    (finite(tradePlan?.target2) ? tradePlan!.target2! : null) ??
    (finite(study?.target2) ? study!.target2! : null);
  const phase = hasPlan
    ? phaseFromTradePlanStatus(
        tradePlan?.status ?? study?.tradePlanStatus ?? null,
      )
    : "none";

  return {
    phase,
    phaseLabel: phaseLabel(phase),
    entry,
    stopVigente: stop,
    stopInicial: stop,
    target1: t1,
    target2: t2,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR:
      (finite(tradePlan?.expectedRR) ? tradePlan!.expectedRR! : null) ??
      (finite(study?.expectedRR) ? study!.expectedRR! : null),
    riskR:
      (finite(tradePlan?.initialRiskR) ? tradePlan!.initialRiskR! : null) ??
      (finite(study?.initialRiskR) ? study!.initialRiskR! : null),
    currentPrice: null,
    unrealizedR: null,
    ...EMPTY_TRAIL,
    exitAuthorityHint: hasPlan
      ? "SEMI · Confirm es la firma — Ranking ≠ BUY"
      : null,
    hasPlan: Boolean(hasPlan && (entry != null || stop != null)),
    emptyCopy: NO_OPERATIONAL_PLAN_COPY,
  };
}

/** Post-entrada: aggregate / PositionState. */
export function buildOperationalPlanFromPosition(input: {
  aggregate?: InvestmentPositionAggregateV1 | null;
  positionState?: PositionStateV1 | null;
  markPrice?: number | null;
}): OperationalPlanViewV1 {
  const agg = input.aggregate;
  const ps = input.positionState;
  const entry =
    (finite(ps?.actualEntry) ? ps!.actualEntry! : null) ??
    (finite(ps?.plannedEntry) ? ps!.plannedEntry! : null) ??
    (finite(agg?.entry) ? agg!.entry! : null);
  const stopVigente =
    (finite(ps?.currentStop) ? ps!.currentStop! : null) ??
    (finite(agg?.protection.currentStop) ? agg!.protection.currentStop! : null);
  const stopInicial =
    (finite(ps?.initialStop) ? ps!.initialStop! : null) ??
    (finite(agg?.originalPlan?.stop) ? agg!.originalPlan!.stop! : null) ??
    stopVigente;
  const t1 =
    (finite(ps?.target1) ? ps!.target1! : null) ??
    (finite(agg?.targets.target1) ? agg!.targets.target1! : null);
  const t2 =
    (finite(ps?.target2) ? ps!.target2! : null) ??
    (finite(agg?.targets.target2) ? agg!.targets.target2! : null);
  const price =
    (finite(input.markPrice) ? input.markPrice! : null) ??
    (finite(agg?.currentPrice) ? agg!.currentPrice! : null);
  const direction: TradePlanDirectionV1 =
    ps?.direction === "short" || agg?.thesisSnapshot?.direction === "short"
      ? "short"
      : "long";
  const isShort = direction === "short";
  const t1Touched = targetTouchedByPrice(isShort, price, t1);
  const t1Managed = Boolean(
    ps?.target1AchievedAt ??
    (typeof agg?.targets.target1AchievedAt === "string" &&
      agg.targets.target1AchievedAt),
  );
  const t2Touched = targetTouchedByPrice(isShort, price, t2);
  const t2Managed = false;
  const t1Reached = t1Touched || t1Managed;
  const t2Reached = t2Touched || t2Managed;
  const closed = ps?.status === "CLOSED";
  const hasPlan = entry != null || stopVigente != null;
  const phase: OperationalPlanPhaseV1 = closed
    ? "closed"
    : hasPlan
      ? "position"
      : "none";

  const unrealizedR =
    (finite(ps?.unrealizedR) ? ps!.unrealizedR! : null) ??
    (finite(agg?.risk.unrealizedR) ? agg!.risk.unrealizedR! : null);
  const peakMfeR = finite(ps?.mfeMae?.mfeR) ? ps!.mfeMae!.mfeR! : unrealizedR;

  const trail = closed
    ? EMPTY_TRAIL
    : projectTrailing({
        direction,
        entry,
        structuralStop: stopInicial ?? stopVigente,
        peakMfeR,
        currentR: unrealizedR,
      });

  return {
    phase,
    phaseLabel: phaseLabel(phase),
    entry,
    stopVigente,
    stopInicial,
    target1: t1,
    target2: t2,
    target1Reached: t1Reached,
    target2Reached: t2Reached,
    target1Touched: t1Touched,
    target1Managed: t1Managed,
    target2Touched: t2Touched,
    target2Managed: t2Managed,
    expectedRR: null,
    riskR: finite(ps?.initialRisk) ? ps!.initialRisk! : null,
    currentPrice: price,
    unrealizedR,
    ...trail,
    exitAuthorityHint: hasPlan
      ? trail.trailingActive
        ? "Trail propone stop · ExitPermission valida · SEMI firma (no auto)"
        : "ExitPlan propone · ExitPermission valida · SEMI firma"
      : null,
    hasPlan,
    emptyCopy: NO_OPERATIONAL_PLAN_COPY,
  };
}
