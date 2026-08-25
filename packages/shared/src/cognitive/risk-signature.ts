/**
 * P2 — firma de riesgo al confirmar (ADR-033 §6).
 * TradePlan TRIGGERED sizea; % caja no es autoridad.
 * No es check_opening. No es OrderIntent.
 */

import { isAuditedOverride } from "./position-state.js";
import type { TradePlanV1 } from "./trade-plan.js";

const QTY_EPS = 1e-9;
const MONEY_EPS = 0.01;

export type RiskSignatureModeV1 = "plan" | "no_plan";

export type RiskSignatureExcessV1 = "qty_above_plan" | "loss_above_plan" | null;

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
  blockReason: "override_missing" | null;
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

/**
 * Evalúa qty/precio firmados contra el TradePlan.
 * Sin TRIGGERED + quantity>0 → `no_plan` (no inventa stop/R; allowed).
 */
export function evaluateRiskSignature(input: {
  tradePlan: TradePlanV1 | null | undefined;
  signedQty: number;
  signedPrice: number;
  overrideReason?: string | null;
}): RiskSignatureV1 {
  const plan = asPlan(input.tradePlan);
  const qty = finite(input.signedQty) ? input.signedQty : NaN;
  const price = finite(input.signedPrice) ? input.signedPrice : NaN;
  const override = isAuditedOverride(
    input.overrideReason != null && String(input.overrideReason).trim()
      ? { reason: String(input.overrideReason) }
      : null,
  );

  const planQty =
    plan != null &&
    plan.status === "TRIGGERED" &&
    finite(plan.quantity) &&
    plan.quantity > 0
      ? plan.quantity
      : null;
  if (plan == null || planQty == null) {
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
      allowed: true,
      excess: null,
      blockReason: null,
    };
  }

  const stop = finite(plan.structuralStop) ? plan.structuralStop : null;
  const plannedRisk = finite(plan.riskAmount) ? plan.riskAmount : null;
  const initialRiskR = finite(plan.initialRiskR) ? plan.initialRiskR : null;

  let signedLoss: number | null = null;
  if (
    Number.isFinite(qty) &&
    qty > 0 &&
    Number.isFinite(price) &&
    price > 0 &&
    stop != null
  ) {
    signedLoss = round4(qty * Math.abs(price - stop));
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
