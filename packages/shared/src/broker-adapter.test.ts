/**
 * BrokerAdapterReceipt — puerto Paper | Live; mock ≠ XTB; submitted ≠ fill.
 */

import { describe, expect, it } from "vitest";
import {
  BROKER_ADAPTER_MOCK,
  BROKER_ADAPTER_PAPER,
  BROKER_ADAPTER_XTB,
  brokerAdapterVenueCopy,
  buildBrokerAdapterReceipt,
} from "./cognitive/broker-adapter.js";

describe("BrokerAdapterReceipt", () => {
  it("paper stamps venue PAPER + adapter paper_broker", () => {
    const receipt = buildBrokerAdapterReceipt({
      venue: "PAPER",
      adapter: BROKER_ADAPTER_PAPER,
      fillStatus: "executed",
    });
    expect(receipt.venue).toBe("PAPER");
    expect(receipt.adapter).toBe("paper_broker");
    expect(receipt.fillStatus).toBe("executed");
    expect(receipt.venue).not.toBe("LIVE");
    expect(brokerAdapterVenueCopy("PAPER")).toMatch(/≠ broker live/i);
  });

  it("mock live is not_wired — never claims a real send", () => {
    const receipt = buildBrokerAdapterReceipt({
      venue: "LIVE",
      adapter: BROKER_ADAPTER_MOCK,
      fillStatus: "not_wired",
    });
    expect(receipt.venue).toBe("LIVE");
    expect(receipt.adapter).toBe("mock");
    expect(receipt.fillStatus).toBe("not_wired");
    expect(receipt.fillStatus).not.toBe("executed");
    expect(brokerAdapterVenueCopy("LIVE")).toMatch(/no envío/i);
    expect(brokerAdapterVenueCopy("LIVE")).toMatch(/≠ broker live/i);
  });

  it("xtb live rejected/submitted never claims executed fill", () => {
    const rejected = buildBrokerAdapterReceipt({
      venue: "LIVE",
      adapter: BROKER_ADAPTER_XTB,
      fillStatus: "rejected",
    });
    expect(rejected.adapter).toBe("xtb");
    expect(rejected.fillStatus).toBe("rejected");
    expect(rejected.fillStatus).not.toBe("executed");
    const submitted = buildBrokerAdapterReceipt({
      venue: "LIVE",
      adapter: BROKER_ADAPTER_XTB,
      fillStatus: "submitted",
    });
    expect(submitted.fillStatus).toBe("submitted");
    expect(submitted.fillStatus).not.toBe("executed");
    expect(brokerAdapterVenueCopy("LIVE", "xtb")).toMatch(/XTB/i);
    expect(brokerAdapterVenueCopy("LIVE", "xtb")).toMatch(/ledger|≠/i);
  });
});
