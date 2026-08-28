/**
 * P2 — firma de riesgo (qty ≤ plan · override · sin plan honest).
 */

import { describe, expect, it } from "vitest";
import { evaluateRiskSignature } from "./cognitive/risk-signature.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";

function triggeredPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "MSFT",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    riskAmount: 50,
    initialRiskR: 5,
    ...overrides,
  };
}

describe("evaluateRiskSignature", () => {
  it("no_plan when TradePlan is missing", () => {
    const s = evaluateRiskSignature({
      tradePlan: null,
      signedQty: 10,
      signedPrice: 100,
    });
    expect(s.mode).toBe("no_plan");
    expect(s.allowed).toBe(true);
    expect(s.overrideRequired).toBe(false);
    expect(s.stop).toBeNull();
  });

  it("no_plan fail-closed when requireTriggeredPlan (SEMI opening)", () => {
    const s = evaluateRiskSignature({
      tradePlan: null,
      signedQty: 10,
      signedPrice: 100,
      requireTriggeredPlan: true,
    });
    expect(s.mode).toBe("no_plan");
    expect(s.allowed).toBe(false);
    expect(s.blockReason).toBe("no_tradeplan");
  });

  it("no_plan when status is WATCH (display-only, no requireTriggeredPlan)", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan({ status: "WATCH", quantity: 10 }),
      signedQty: 10,
      signedPrice: 100,
    });
    expect(s.mode).toBe("no_plan");
    expect(s.allowed).toBe(true);
  });

  it("allows qty at or below plan", () => {
    const at = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 10,
      signedPrice: 100,
    });
    expect(at.mode).toBe("plan");
    expect(at.allowed).toBe(true);
    expect(at.maxQty).toBe(10);
    expect(at.signedLossAtStop).toBe(50);
    expect(at.signedR).toBe(1);

    const below = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 5,
      signedPrice: 100,
    });
    expect(below.allowed).toBe(true);
    expect(below.overrideRequired).toBe(false);
    expect(below.signedLossAtStop).toBe(25);
    expect(below.signedR).toBe(0.5);
  });

  it("blocks qty above plan without override", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 20,
      signedPrice: 100,
    });
    expect(s.allowed).toBe(false);
    expect(s.overrideRequired).toBe(true);
    expect(s.excess).toBe("qty_above_plan");
    expect(s.blockReason).toBe("override_missing");
  });

  it("allows qty above plan with override reason", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 20,
      signedPrice: 100,
      overrideReason: "acepto más riesgo",
    });
    expect(s.allowed).toBe(true);
    expect(s.overrideRequired).toBe(true);
    expect(s.blockReason).toBeNull();
  });

  it("rejects blank override", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 20,
      signedPrice: 100,
      overrideReason: "   ",
    });
    expect(s.allowed).toBe(false);
  });

  it("blocks loss above riskAmount at same qty when price moves away from stop", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 10,
      signedPrice: 110,
    });
    expect(s.excess).toBe("loss_above_plan");
    expect(s.allowed).toBe(false);
    expect(s.signedLossAtStop).toBe(150);
  });

  it("T-SIZE-05: signedStop recalculates loss and R", () => {
    const baseline = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 10,
      signedPrice: 100,
    });
    const tighter = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 10,
      signedPrice: 100,
      signedStop: 97,
    });
    expect(baseline.signedLossAtStop).toBe(50);
    expect(tighter.signedLossAtStop).toBe(30);
    expect(tighter.signedR).toBeLessThan(baseline.signedR!);
  });

  it("T-SIZE-04: qty above plan requires override", () => {
    const s = evaluateRiskSignature({
      tradePlan: triggeredPlan(),
      signedQty: 20,
      signedPrice: 100,
    });
    expect(s.overrideRequired).toBe(true);
    expect(s.allowed).toBe(false);
  });
});
