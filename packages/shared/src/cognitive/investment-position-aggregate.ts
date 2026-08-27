/**
 * Position = memoria operativa (V1.17).
 * Agregado reconstruible desde dominio existente — sin mega-clase persistida.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { ExitSuggestedActionV1 } from "./exit-plan.js";
import type { ProtectPlanV1 } from "./protect-plan.js";
import type { PositionStatusV1 } from "./position-state.js";
import type { TradePlanDirectionV1 } from "./trade-plan.js";
import {
  mapPositionNextAction,
  type MesaNextActionV1,
} from "./mesa-next-action.js";
import { buildMesaProtectionState } from "./mesa-protection-state.js";
import { computePositionOpenRiskR } from "./portfolio-risk-metrics.js";

export type PositionManagementStateV1 = {
  status: PositionStatusV1 | string;
  exitSuggestedAction: ExitSuggestedActionV1 | null;
  protectionDiscrepancy: boolean;
  unrealizedR: number | null;
  openRiskR: number | null;
};

export type PositionPlanLevelsV1 = {
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
};

export type InvestmentPositionAggregateV1 = {
  symbol: string;
  instrumentId: string;
  originDecisionId: string | null;
  thesisSnapshot:
    | (Pick<
        DecisionJournalStudyViewV1,
        | "status"
        | "opinion"
        | "tradePlanStatus"
        | "hasOperationalPlan"
        | "strength"
        | "entry"
        | "stop"
        | "target1"
        | "target2"
        | "expectedRR"
        | "riskAmount"
      > & { direction: "long" | "short" })
    | null;
  originalPlan: PositionPlanLevelsV1 | null;
  originalPlanAvailable: boolean;
  currentPlan: PositionPlanLevelsV1;
  /** @deprecated Usar originalPlan / currentPlan. */
  tradePlanSnapshot: {
    entry: number | null;
    stop: number | null;
    target1: number | null;
    target2: number | null;
    plannedEntry: number | null;
    executedEntry: number | null;
    executedStop: number | null;
  };
  entry: number | null;
  currentPrice: number | null;
  quantity: number;
  risk: { openRiskR: number | null; unrealizedR: number | null };
  protection: {
    currentStop: number | null;
    protectHint: boolean;
    discrepancy: boolean;
  };
  targets: { target1: number | null; target2: number | null };
  currentState: PositionManagementStateV1;
  nextAction: MesaNextActionV1;
};

export type BuildInvestmentPositionAggregateInput = {
  position: {
    symbol: string;
    instrumentId: string;
    quantity: number;
    avgCost: number;
    lastPrice?: number | null;
    operational?: {
      status?: string | null;
      direction?: string | null;
      currentStop?: number | null;
      target1?: number | null;
      target2?: number | null;
      unrealizedR?: number | null;
      plannedEntry?: number | null;
      actualEntry?: number | null;
      initialStop?: number | null;
      exitPlan?: {
        suggestedAction?: ExitSuggestedActionV1 | string | null;
      } | null;
    } | null;
  };
  study?: DecisionJournalStudyViewV1 | null;
  protectPlan?: Pick<ProtectPlanV1, "status" | "suggestedProtectStop"> | null;
  originDecisionId?: string | null;
};

function finiteNumber(n: unknown): number | null {
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function resolveDirection(
  operationalDirection?: string | null,
  studyDirection?: TradePlanDirectionV1 | null,
): "long" | "short" {
  const raw = (operationalDirection ?? studyDirection ?? "long").toLowerCase();
  return raw === "short" ? "short" : "long";
}

export function buildInvestmentPositionAggregate(
  input: BuildInvestmentPositionAggregateInput,
): InvestmentPositionAggregateV1 {
  const { position, study, protectPlan } = input;
  const op = position.operational;
  const protection = buildMesaProtectionState({
    study,
    exitSuggestedStop:
      (op?.exitPlan as { suggestedStop?: number | null } | undefined)
        ?.suggestedStop ?? null,
    currentStop: op?.currentStop ?? null,
    protectPlan,
  });

  const executedEntry = finiteNumber(op?.actualEntry) ?? position.avgCost;
  const executedStop = finiteNumber(op?.currentStop);
  const originalEntry = finiteNumber(op?.plannedEntry);
  const originalStop = finiteNumber(op?.initialStop);
  const originalPlanAvailable = originalEntry != null || originalStop != null;
  const originalPlan: PositionPlanLevelsV1 | null = originalPlanAvailable
    ? {
        entry: originalEntry,
        stop: originalStop,
        target1: null,
        target2: null,
      }
    : null;

  const currentPlan: PositionPlanLevelsV1 = {
    entry: executedEntry,
    stop: executedStop,
    target1: finiteNumber(op?.target1) ?? study?.target1 ?? null,
    target2: finiteNumber(op?.target2) ?? study?.target2 ?? null,
  };

  const direction = resolveDirection(op?.direction, study?.direction ?? null);

  const openRiskR = computePositionOpenRiskR({
    avgCost: position.avgCost,
    quantity: position.quantity,
    lastPrice: position.lastPrice,
    operational: op,
    study,
  });

  const exitRaw = op?.exitPlan?.suggestedAction;
  const exitSuggestedAction =
    exitRaw === "hold" ||
    exitRaw === "protect" ||
    exitRaw === "reduce" ||
    exitRaw === "full_exit"
      ? exitRaw
      : null;

  const currentState: PositionManagementStateV1 = {
    status: op?.status ?? "OPEN",
    exitSuggestedAction,
    protectionDiscrepancy: protection.discrepancy,
    unrealizedR: op?.unrealizedR ?? null,
    openRiskR,
  };

  const nextAction = mapPositionNextAction({
    position,
    protectPlan,
    study,
    protectionDiscrepancy: protection.discrepancy,
  });

  return {
    symbol: position.symbol,
    instrumentId: position.instrumentId,
    originDecisionId: input.originDecisionId ?? null,
    thesisSnapshot: study
      ? {
          status: study.status,
          opinion: study.opinion,
          tradePlanStatus: study.tradePlanStatus,
          hasOperationalPlan: study.hasOperationalPlan,
          strength: study.strength,
          entry: study.entry,
          stop: study.stop,
          target1: study.target1,
          target2: study.target2,
          expectedRR: study.expectedRR,
          riskAmount: study.riskAmount,
          direction,
        }
      : null,
    originalPlan,
    originalPlanAvailable,
    currentPlan,
    tradePlanSnapshot: {
      entry: currentPlan.entry,
      stop: currentPlan.stop,
      target1: currentPlan.target1,
      target2: currentPlan.target2,
      plannedEntry: originalPlan?.entry ?? null,
      executedEntry,
      executedStop,
    },
    entry: executedEntry,
    currentPrice: position.lastPrice ?? null,
    quantity: position.quantity,
    risk: { openRiskR, unrealizedR: op?.unrealizedR ?? null },
    protection: {
      currentStop: executedStop,
      protectHint: protectPlan?.status === "protect_hint",
      discrepancy: protection.discrepancy,
    },
    targets: {
      target1: currentPlan.target1,
      target2: currentPlan.target2,
    },
    currentState,
    nextAction,
  };
}

export type PositionRouteLevelV1 = {
  label: string;
  value: number;
  kind: "target" | "entry" | "stop" | "price";
  distancePct: number | null;
  distanceR: number | null;
  reached: boolean;
};

export function buildPositionRouteLevels(
  aggregate: InvestmentPositionAggregateV1,
): PositionRouteLevelV1[] {
  const price = aggregate.currentPrice;
  const entry = aggregate.entry;
  const stop = aggregate.protection.currentStop;
  const t1 = aggregate.targets.target1;
  const t2 = aggregate.targets.target2;
  const riskAmount = aggregate.thesisSnapshot?.riskAmount;
  const isShort = aggregate.thesisSnapshot?.direction === "short";

  function distancePct(from: number, to: number): number | null {
    if (!Number.isFinite(from) || from === 0) return null;
    return Math.round(((to - from) / from) * 1000) / 10;
  }

  function distanceR(level: number): number | null {
    if (
      entry == null ||
      stop == null ||
      riskAmount == null ||
      riskAmount <= 0
    ) {
      return null;
    }
    const riskPerUnit = isShort ? stop - entry : entry - stop;
    if (riskPerUnit <= 0) return null;
    const move = isShort ? entry - level : level - entry;
    return Math.round((move / riskPerUnit) * 100) / 100;
  }

  const levels: PositionRouteLevelV1[] = [];

  if (t2 != null) {
    levels.push({
      label: "TP2",
      value: t2,
      kind: "target",
      distancePct: price != null ? distancePct(price, t2) : null,
      distanceR: distanceR(t2),
      reached: price != null && (isShort ? price <= t2 : price >= t2),
    });
  }
  if (t1 != null) {
    levels.push({
      label: "TP1",
      value: t1,
      kind: "target",
      distancePct: price != null ? distancePct(price, t1) : null,
      distanceR: distanceR(t1),
      reached: price != null && (isShort ? price <= t1 : price >= t1),
    });
  }
  if (price != null) {
    levels.push({
      label: "PRECIO",
      value: price,
      kind: "price",
      distancePct: null,
      distanceR: entry != null ? distanceR(price) : null,
      reached: false,
    });
  }
  if (entry != null) {
    levels.push({
      label: "ENTRADA",
      value: entry,
      kind: "entry",
      distancePct: price != null ? distancePct(entry, price) : null,
      distanceR: 0,
      reached: true,
    });
  }
  if (stop != null) {
    levels.push({
      label: "STOP",
      value: stop,
      kind: "stop",
      distancePct: price != null ? distancePct(price, stop) : null,
      distanceR: distanceR(stop),
      reached: false,
    });
  }

  return levels;
}
