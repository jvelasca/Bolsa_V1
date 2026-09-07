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

  it("duplicate FILLED financial apply is idempotent and monotonic", () => {
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

    // Already recorded once → stays (idempotent).
    const once: LiveOrderV1 = { ...base, financialApplyCount: 1 };
    const second = transitionLiveOrder(once, "FILLED", {
      applyFinancial: true,
    });
    expect(second.financialApplyCount).toBe(1);

    // Pre-existing elevated marker never collapses back to 1.
    const elevated: LiveOrderV1 = { ...base, financialApplyCount: 3 };
    const third = transitionLiveOrder(elevated, "FILLED", {
      applyFinancial: true,
    });
    expect(third.financialApplyCount).toBe(3);

    // applyFinancial outside FILLED is vetoed.
    expect(() =>
      transitionLiveOrder(base, "PARTIAL", {
        filledQuantity: 1,
        applyFinancial: true,
      }),
    ).toThrow(/financial apply only/);
  });

  it("FILLED with partial broker qty is fail-closed (reconciliation)", () => {
    let order = buildLiveOrder({
      orderId: "lo-f",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 100,
    });
    order = transitionLiveOrder(order, "SUBMITTING");
    order = transitionLiveOrder(order, "SUBMITTED", { venueOrderId: "xtb-f" });
    const working = transitionLiveOrder(order, "WORKING");

    // Broker dice FILLED pero llenó sólo 80 de 100 → no normalizar silencio.
    expect(() =>
      transitionLiveOrder(working, "FILLED", { filledQuantity: 80 }),
    ).toThrow(/reconciliation required/);
    // La orden origen no se ha mutado (sigue WORKING, sin rastro de FILLED).
    expect(working.status).toBe("WORKING");
    expect(working.filledQuantity).toBe(0);
    expect(working.remainingQuantity).toBe(100);

    // FILLED sin filledQuantity → captura la orden entera.
    const full = transitionLiveOrder(working, "FILLED");
    expect(full.filledQuantity).toBe(100);
    expect(full.remainingQuantity).toBe(0);
  });
});
