/**
 * XL-3 LiveOrder — UNKNOWN / PARTIAL / no re-POST mirror tests.
 */

import { describe, expect, it } from "vitest";
import {
  buildLiveOrder,
  canTransitionLiveOrder,
  forbidExecuteTradeForPartial,
  forbidRepostFromUnknown,
  LiveOrderTransitionError,
  transitionLiveOrder,
  type LiveOrderV1,
} from "./cognitive/live-order.js";

describe("LiveOrder XL-3", () => {
  it("forbids UNKNOWN → SUBMITTING (no re-POST)", () => {
    expect(canTransitionLiveOrder("UNKNOWN", "SUBMITTING")).toBe(false);
    const order = buildLiveOrder({
      orderId: "lo-1",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 100,
      status: "UNKNOWN",
    });
    expect(() => transitionLiveOrder(order, "SUBMITTING")).toThrow(
      LiveOrderTransitionError,
    );
    expect(() => forbidRepostFromUnknown(order)).toThrow(/re-POST/);
  });

  it("timeout path SUBMITTING → UNKNOWN", () => {
    const order = buildLiveOrder({
      orderId: "lo-2",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 10,
    });
    const unknown = transitionLiveOrder(
      transitionLiveOrder(order, "SUBMITTING"),
      "UNKNOWN",
    );
    expect(unknown.status).toBe("UNKNOWN");
  });

  it("PARTIAL keeps remaining qty and vetoes full execute_trade", () => {
    let order = buildLiveOrder({
      orderId: "lo-3",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 100,
    });
    order = transitionLiveOrder(order, "SUBMITTING");
    order = transitionLiveOrder(order, "SUBMITTED", { venueOrderId: "xtb-1" });
    order = transitionLiveOrder(order, "WORKING");
    const partial = transitionLiveOrder(order, "PARTIAL", {
      filledQuantity: 40,
    });
    expect(partial.filledQuantity).toBe(40);
    expect(partial.remainingQuantity).toBe(60);
    expect(() => forbidExecuteTradeForPartial(partial)).toThrow(/PARTIAL/);
  });

  it("duplicate FILLED financial apply stays at 1", () => {
    const base: LiveOrderV1 = {
      orderId: "lo-4",
      status: "WORKING",
      venue: "LIVE",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 5,
      filledQuantity: 0,
      remainingQuantity: 5,
      venueOrderId: "xtb-1",
      intentId: null,
      financialApplyCount: 0,
    };
    const first = transitionLiveOrder(base, "FILLED", { applyFinancial: true });
    expect(first.financialApplyCount).toBe(1);
    const again: LiveOrderV1 = { ...base, financialApplyCount: 1 };
    const second = transitionLiveOrder(again, "FILLED", {
      applyFinancial: true,
    });
    expect(second.financialApplyCount).toBe(1);
  });
});
