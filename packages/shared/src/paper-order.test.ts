/**
 * PaperOrder OI-4 + OR-3 state machine (ADR-034/035).
 */

import { describe, expect, it } from "vitest";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  canTransitionPaperOrder,
  paperOrderStatusCopy,
  stableOrderIdFromDecision,
  transitionPaperOrder,
  type PaperOrderV1,
} from "./cognitive/paper-order.js";

describe("OI-4 buildPaperOrder", () => {
  it("build → CREATED, venue PAPER, no fill", () => {
    const order = buildPaperOrder({
      orderId: "ORD-1",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 10,
      intentId: "INT-1",
    });
    expect(order.status).toBe("CREATED");
    expect(order.venue).toBe("PAPER");
    expect(order.transactionId).toBeNull();
    expect(order.filledQuantity).toBeNull();
    expect(order.orderId).toBe("ORD-1");
  });

  it("applyFill CREATED → FILLED", () => {
    const created = buildPaperOrder({
      orderId: "ORD-1",
      instrumentId: "inst-1",
      side: "sell",
      quantity: 4,
    });
    const filled = applyPaperOrderFill(created, "tx-1");
    expect(filled.status).toBe("FILLED");
    expect(filled.transactionId).toBe("tx-1");
    expect(filled.filledQuantity).toBe(4);
    expect(filled.orderId).toBe(created.orderId);
    expect(created.status).toBe("CREATED");
  });

  it("FILLED does not revert; first fill wins", () => {
    const created = buildPaperOrder({
      orderId: "ORD-1",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 1,
    });
    const filled = applyPaperOrderFill(created, "tx-1");
    const again = applyPaperOrderFill(filled, "tx-other");
    expect(again.status).toBe("FILLED");
    expect(again.transactionId).toBe("tx-1");
  });

  it("blank orderId is generated", () => {
    const order = buildPaperOrder({
      orderId: "  ",
      instrumentId: "inst-1",
      side: "buy",
      quantity: 1,
    });
    expect(order.orderId.startsWith("ORD-")).toBe(true);
    expect(order.status).toBe("CREATED");
  });

  it("OR-1 stableOrderIdFromDecision is deterministic", () => {
    expect(stableOrderIdFromDecision("DEC-1")).toBe("ORD-DEC-1");
    expect(stableOrderIdFromDecision("DEC-1")).toBe(
      stableOrderIdFromDecision("DEC-1"),
    );
  });
});

describe("OI-4 paperOrderStatusCopy", () => {
  it("CREATED copy is not covered", () => {
    expect(paperOrderStatusCopy("CREATED")).toMatch(/no confirmado/i);
    expect(paperOrderStatusCopy("FILLED")).toMatch(/cubierta/i);
    expect(paperOrderStatusCopy("UNKNOWN")).toMatch(/desconocido/i);
    const created: PaperOrderV1 = buildPaperOrder({
      instrumentId: "i",
      side: "buy",
      quantity: 1,
    });
    expect(paperOrderStatusCopy(created.status)).not.toBe(
      paperOrderStatusCopy("FILLED"),
    );
  });
});

describe("OR-3 transitions", () => {
  it("CREATED → SUBMITTED → ACK → FILLED", () => {
    const order = buildPaperOrder({
      orderId: "ORD-1",
      instrumentId: "i",
      side: "buy",
      quantity: 10,
    });
    const submitted = transitionPaperOrder(order, "SUBMITTED");
    const ack = transitionPaperOrder(submitted, "ACK");
    const filled = applyPaperOrderFill(ack, "tx-1");
    expect(submitted.status).toBe("SUBMITTED");
    expect(ack.status).toBe("ACK");
    expect(filled.status).toBe("FILLED");
  });

  it("PARTIAL then FILLED", () => {
    const ack = transitionPaperOrder(
      buildPaperOrder({
        orderId: "ORD-1",
        instrumentId: "i",
        side: "buy",
        quantity: 10,
      }),
      "ACK",
    );
    const partial = transitionPaperOrder(ack, "PARTIAL", {
      filledQuantity: 4,
    });
    expect(partial.status).toBe("PARTIAL");
    expect(partial.filledQuantity).toBe(4);
    const filled = applyPaperOrderFill(partial, "tx-1");
    expect(filled.status).toBe("FILLED");
    expect(filled.filledQuantity).toBe(10);
  });

  it("UNKNOWN resolves to FILLED", () => {
    const unknown = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          orderId: "ORD-1",
          instrumentId: "i",
          side: "buy",
          quantity: 1,
        }),
        "SUBMITTED",
      ),
      "UNKNOWN",
    );
    expect(unknown.status).toBe("UNKNOWN");
    expect(applyPaperOrderFill(unknown, "tx-r").status).toBe("FILLED");
  });

  it("REJECTED/CANCELLED/EXPIRED are terminal", () => {
    const base = buildPaperOrder({
      orderId: "ORD-1",
      instrumentId: "i",
      side: "buy",
      quantity: 1,
    });
    const rejected = transitionPaperOrder(base, "REJECTED");
    expect(rejected.status).toBe("REJECTED");
    expect(canTransitionPaperOrder("REJECTED", "FILLED")).toBe(false);
    expect(() => transitionPaperOrder(rejected, "FILLED")).toThrow(
      /illegal_transition/,
    );
    expect(transitionPaperOrder(base, "CANCELLED").status).toBe("CANCELLED");
    expect(transitionPaperOrder(base, "EXPIRED").status).toBe("EXPIRED");
    expect(() => applyPaperOrderFill(rejected)).toThrow(/fill_from_terminal/);
  });
});
