/**
 * PaperBrokerReceipt — venue PAPER ≠ broker live (post-OI-6).
 */

import { describe, expect, it } from "vitest";
import { buildPaperOrder } from "./cognitive/paper-order.js";
import {
  PAPER_BROKER_ADAPTER,
  buildPaperBrokerReceipt,
  paperBrokerVenueCopy,
} from "./cognitive/paper-broker.js";

describe("PaperBrokerReceipt", () => {
  it("fill executed stamps venue PAPER + adapter paper_broker", () => {
    const order = buildPaperOrder({
      instrumentId: "inst-1",
      side: "buy",
      quantity: 10,
    });
    const filled = {
      ...order,
      status: "FILLED" as const,
      transactionId: "tx-1",
    };
    const receipt = buildPaperBrokerReceipt({
      paperOrder: filled,
      fillStatus: "executed",
    });
    expect(receipt.venue).toBe("PAPER");
    expect(receipt.adapter).toBe(PAPER_BROKER_ADAPTER);
    expect(receipt.fillStatus).toBe("executed");
    expect(receipt.paperOrder.status).toBe("FILLED");
    expect(receipt.venue).not.toBe("BROKER");
  });

  it("unknown keeps CREATED order — never claims live broker", () => {
    const order = buildPaperOrder({
      instrumentId: "inst-1",
      side: "sell",
      quantity: 5,
    });
    const receipt = buildPaperBrokerReceipt({
      paperOrder: order,
      fillStatus: "unknown",
    });
    expect(receipt.fillStatus).toBe("unknown");
    expect(receipt.paperOrder.status).toBe("CREATED");
    expect(receipt.adapter).toBe("paper_broker");
    expect(paperBrokerVenueCopy()).toMatch(/≠ broker live/i);
  });
});
