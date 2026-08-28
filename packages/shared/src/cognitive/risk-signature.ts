/**
 * P2 / V1.26 — firma de riesgo al confirmar (ADR-033 §6).
 * TradePlan TRIGGERED sizea; % caja no es autoridad.
 * Geometría: direction + entry + stop (fail-closed; no abs).
 * No es check_opening. No es OrderIntent.
 */

import { isAuditedOverride } from "./position-state.js";
import {
  adverseExposure,
  validateOperationalLevels,
  type OperationalLevelsReasonV1,
} from "./operational-levels.js";
import type { TradePlanV1 } from "./trade-plan.js";

const QTY_EPS = 1e-9;
const MONEY_EPS = 0.01;

export type RiskSignatureModeV1 = "plan" | "no_plan";

export type RiskSignatureExcessV1 = "qty_above_plan" | "loss_above_plan" | null;

export type RiskSignatureBlockReasonV1 =
  | "override_missing"
  | "no_tradeplan"
  | "stop_wrong_side"
  | "stop_invalid"
  | "targets_invalid"
  | "risk_non_positive"
  | null;

export type RiskSignatureV1 = {
  mode: RiskSignatureModeV1;
  suggestedQty: number | null;
  maxQty: number | null;
  stop: number | null;
  plannedRiskAmount: number | null;
  initialRiskR: number | null;
  signedLossAtStop: number | null;
  signedR: number | null;
  overrideRequired: boolean;
  allowed: boolean;
  excess: RiskSignatureExcessV1;
  blockReason: RiskSignatureBlockReasonV1;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

function asPlan(raw: TradePlanV1 | null | undefined): TradePlanV1 | null {
  if (!raw || typeof raw !== "object") return null;
  return raw;
}

function geometryBlock(
  reason: OperationalLevelsReasonV1,
): Exclude<RiskSignatureBlockReasonV1, null> {
  return reason;
}

function emptyPlan(requireTriggeredPlan: boolean): RiskSignatureV1 {
  return {
    mode: "no_plan",
    suggestedQty: null,
    maxQty: null,
    stop: null,
    plannedRiskAmount: null,
    initialRiskR: null,
    signedLossAtStop: null,
    signedR: null,
    overrideRequired: false,
    allowed: !requireTriggeredPlan,
    excess: null,
    blockReason: requireTriggeredPlan ? "no_tradeplan" : null,
  };
}

function deniedPlan(input: {
  planQty: number;
  stop: number | null;
  plannedRisk: number | null;
  initialRiskR: number | null;
  blockReason: Exclude<RiskSignatureBlockReasonV1, null>;
  signedLoss?: number | null;
  signedR?: number | null;
}): RiskSignatureV1 {
  return {
    mode: "plan",
    suggestedQty: input.planQty,
    maxQty: input.planQty,
    stop: input.stop,
    plannedRiskAmount: input.plannedRisk,
    initialRiskR: input.initialRiskR,
    signedLossAtStop: input.signedLoss ?? null,
    signedR: input.signedR ?? null,
    overrideRequired: false,
    allowed: false,
    excess: null,
    blockReason: input.blockReason,
  };
}

/**
 * Evalúa qty/precio/stop firmados contra el TradePlan.
 * Sin TRIGGERED + quantity>0 → `no_plan`.
 * Con `requireTriggeredPlan` (SEMI apertura): `no_plan` → DENY `no_tradeplan`.
 * `signedStop` omitido (`undefined`/`null`) → stop del plan.
 * `signedStop` presente e inválido (≤0 / no finito) → DENY `stop_invalid` (no sustituye).
 */
export function evaluateRiskSignature(input: {
  tradePlan: TradePlanV1 | null | undefined;
  signedQty: number;
  signedPrice: number;
  /** Stop firmado (editable en ticket). Omitido = plan.structuralStop. */
  signedStop?: number | null;
  overrideReason?: string | null;
  requireTriggeredPlan?: boolean;
}): RiskSignatureV1 {
  const plan = asPlan(input.tradePlan);
  const qty = finite(input.signedQty) ? input.signedQty : NaN;
  const price = finite(input.signedPrice) ? input.signedPrice : NaN;
  const override = isAuditedOverride(
    input.overrideReason != null && String(input.overrideReason).trim()
      ? { reason: String(input.overrideReason) }
      : null,
  );
  const requireTriggeredPlan = input.requireTriggeredPlan === true;

  const planQty =
    plan != null &&
    plan.status === "TRIGGERED" &&
    finite(plan.quantity) &&
    plan.quantity > 0
      ? plan.quantity
      : null;
  if (plan == null || planQty == null) {
    return emptyPlan(requireTriggeredPlan);
  }

  const plannedRisk = finite(plan.riskAmount) ? plan.riskAmount : null;
  const initialRiskR = finite(plan.initialRiskR) ? plan.initialRiskR : null;
  const planStop = finite(plan.structuralStop) ? plan.structuralStop : null;

  let stop: number | null;
  if (input.signedStop !== undefined && input.signedStop !== null) {
    if (!finite(input.signedStop) || input.signedStop <= 0) {
      return deniedPlan({
        planQty,
        stop: null,
        plannedRisk,
        initialRiskR,
        blockReason: "stop_invalid",
      });
    }
    stop = input.signedStop;
  } else {
    stop = planStop;
  }

  if (stop == null || stop <= 0) {
    return deniedPlan({
      planQty,
      stop: null,
      plannedRisk,
      initialRiskR,
      blockReason: "stop_invalid",
    });
  }

  if (Number.isFinite(price) && price > 0) {
    const levels = validateOperationalLevels({
      direction: plan.direction,
      entry: price,
      stop,
      target1: plan.target1,
      target2: plan.target2,
    });
    if (!levels.ok && levels.reason) {
      return deniedPlan({
        planQty,
        stop,
        plannedRisk,
        initialRiskR,
        blockReason: geometryBlock(levels.reason),
      });
    }
  }

  let signedLoss: number | null = null;
  const direction =
    plan.direction === "long" || plan.direction === "short"
      ? plan.direction
      : null;
  if (
    Number.isFinite(qty) &&
    qty > 0 &&
    Number.isFinite(price) &&
    price > 0 &&
    direction != null
  ) {
    signedLoss = round4(qty * adverseExposure(direction, price, stop));
  }

  let signedR: number | null = null;
  if (signedLoss != null && plannedRisk != null && plannedRisk > MONEY_EPS) {
    signedR = round4(signedLoss / plannedRisk);
  }

  let excess: RiskSignatureExcessV1 = null;
  if (Number.isFinite(qty) && qty > planQty + QTY_EPS) {
    excess = "qty_above_plan";
  } else if (
    signedLoss != null &&
    plannedRisk != null &&
    plannedRisk > 0 &&
    signedLoss > plannedRisk + MONEY_EPS
  ) {
    excess = "loss_above_plan";
  }

  const overrideRequired = excess != null;
  const allowed = !overrideRequired || override;

  return {
    mode: "plan",
    suggestedQty: planQty,
    maxQty: planQty,
    stop,
    plannedRiskAmount: plannedRisk,
    initialRiskR,
    signedLossAtStop: signedLoss,
    signedR,
    overrideRequired,
    allowed,
    excess,
    blockReason: !allowed ? "override_missing" : null,
  };
}

/** Congela qty/entrada/stop firmados sobre el snapshot del plan (nacimiento Position). */
export function applySignedLevelsToTradePlan(
  plan: TradePlanV1 | null | undefined,
  input: {
    signedQty?: number | null;
    signedPrice?: number | null;
    signedStop?: number | null;
  },
): TradePlanV1 | null {
  if (!plan) return plan ?? null;
  const next = { ...plan };
  if (finite(input.signedQty) && input.signedQty > 0) {
    next.quantity = input.signedQty;
  }
  if (finite(input.signedPrice) && input.signedPrice > 0) {
    next.entry = input.signedPrice;
  }
  if (finite(input.signedStop) && input.signedStop > 0) {
    next.structuralStop = input.signedStop;
  }
  return next;
}
