/**
 * PaperOrder OI-4 — CREATED→FILLED (ADR-034).
 */

import { describe, expect, it } from "vitest";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  paperOrderStatusCopy,
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
});

describe("OI-4 paperOrderStatusCopy", () => {
  it("CREATED copy is not covered", () => {
    expect(paperOrderStatusCopy("CREATED")).toMatch(/no confirmado/i);
    expect(paperOrderStatusCopy("FILLED")).toMatch(/cubierta/i);
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
