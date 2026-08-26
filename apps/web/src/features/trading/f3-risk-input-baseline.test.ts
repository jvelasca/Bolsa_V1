/**
 * V1.17 — invalidación qty/precio vs TradePlan TRIGGERED.
 */

import { describe, expect, it } from "vitest";
import type { TradePlanV1 } from "@bolsa/shared";
import {
  f3TicketInputsStale,
  resolveF3PlanBaseline,
  resolveF3SignedPrice,
} from "@/features/trading/f3-risk-input-baseline";

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

describe("resolveF3PlanBaseline", () => {
  it("reads qty and entry from TRIGGERED plan", () => {
    expect(
      resolveF3PlanBaseline({
        tradePlan: triggeredPlan(),
        suggestedPrice: 101,
        lastClose: 99,
      }),
    ).toEqual({ qty: 10, price: 101 });
  });

  it("returns null qty without TRIGGERED quantity", () => {
    expect(
      resolveF3PlanBaseline({
        tradePlan: triggeredPlan({ status: "WATCH", quantity: 10 }),
      }),
    ).toEqual({ qty: null, price: 100 });
  });
});

describe("f3TicketInputsStale", () => {
  const baseline = { qty: 10, price: 100 };

  it("false when inputs match baseline", () => {
    expect(
      f3TicketInputsStale({
        quantity: "10",
        priceField: "100",
        baseline,
      }),
    ).toBe(false);
  });

  it("true when quantity differs", () => {
    expect(
      f3TicketInputsStale({
        quantity: "12",
        priceField: "100",
        baseline,
      }),
    ).toBe(true);
  });

  it("true when price differs", () => {
    expect(
      f3TicketInputsStale({
        quantity: "10",
        priceField: "110",
        baseline,
      }),
    ).toBe(true);
  });

  it("uses fallback price when field is empty", () => {
    expect(
      resolveF3SignedPrice({
        priceField: "",
        baselinePrice: 100,
        suggestedPrice: 101,
        lastClose: 99,
      }),
    ).toBe(100);
  });
});
