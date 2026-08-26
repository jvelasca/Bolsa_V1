/**
 * V1.17 — baseline qty/precio del TradePlan vs inputs editados en F3.
 * Detecta desviación para invalidar override y avisar antes de firmar.
 */

import type { TradePlanV1 } from "@bolsa/shared";

const QTY_EPS = 1e-9;
const PRICE_EPS = 0.001;

export type F3PlanBaselineV1 = {
  qty: number | null;
  price: number | null;
};

export function resolveF3PlanBaseline(input: {
  tradePlan?: TradePlanV1 | null;
  suggestedPrice?: number | null;
  lastClose?: number | null;
}): F3PlanBaselineV1 {
  const plan = input.tradePlan;
  const planQty =
    plan?.status === "TRIGGERED" &&
    typeof plan.quantity === "number" &&
    Number.isFinite(plan.quantity) &&
    plan.quantity > 0
      ? plan.quantity
      : null;

  const priceCandidate =
    input.suggestedPrice ??
    (typeof plan?.entry === "number" && Number.isFinite(plan.entry)
      ? plan.entry
      : null) ??
    input.lastClose ??
    null;

  return {
    qty: planQty,
    price:
      typeof priceCandidate === "number" && Number.isFinite(priceCandidate)
        ? priceCandidate
        : null,
  };
}

/** Resuelve precio firmado (campo vacío → baseline / last close). */
export function resolveF3SignedPrice(input: {
  priceField: string;
  baselinePrice: number | null;
  suggestedPrice?: number | null;
  lastClose?: number | null;
}): number | null {
  const trimmed = input.priceField.trim();
  if (trimmed) {
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  const fallback =
    input.baselinePrice ?? input.suggestedPrice ?? input.lastClose ?? null;
  return typeof fallback === "number" && Number.isFinite(fallback)
    ? fallback
    : null;
}

/** True cuando qty/precio editados difieren del baseline TRIGGERED. */
export function f3TicketInputsStale(input: {
  quantity: string;
  priceField: string;
  baseline: F3PlanBaselineV1;
  suggestedPrice?: number | null;
  lastClose?: number | null;
}): boolean {
  if (input.baseline.qty == null && input.baseline.price == null) {
    return false;
  }

  const qty = Number(input.quantity);
  if (
    input.baseline.qty != null &&
    Number.isFinite(qty) &&
    Math.abs(qty - input.baseline.qty) > QTY_EPS
  ) {
    return true;
  }

  const signedPrice = resolveF3SignedPrice({
    priceField: input.priceField,
    baselinePrice: input.baseline.price,
    suggestedPrice: input.suggestedPrice,
    lastClose: input.lastClose,
  });
  if (
    input.baseline.price != null &&
    signedPrice != null &&
    Math.abs(signedPrice - input.baseline.price) > PRICE_EPS
  ) {
    return true;
  }

  return false;
}
