/**
 * DurableSubmitIntent OR-2 / DEX-1 — crash/restart UNKNOWN reconstruible (ADR-035).
 */

import { describe, expect, it } from "vitest";
import {
  bindVenueOrder,
  markSendAttempted,
  markSubmitFilled,
  recordSubmitIntent,
  reconstructUnknown,
  sendAttemptedDurable,
} from "./cognitive/submit-intent.js";

function recorded() {
  return recordSubmitIntent({
    decisionId: "DEC-1",
    intentId: "INT-DEC-1",
    orderId: "ORD-DEC-1",
    accountId: "acc-1",
  });
}

describe("OR-2 / DEX-1 DurableSubmitIntent", () => {
  it("record → recorded without venue; sendAttemptedDurable false", () => {
    const intent = recorded();
    expect(intent.phase).toBe("recorded");
    expect(intent.venueOrderId).toBeNull();
    expect(intent.reason).toBe("crash_before_venue_ack");
    expect(intent.venue).toBe("paper");
    expect(intent.sendAttemptedAt).toBeNull();
    expect(sendAttemptedDurable(intent)).toBe(false);
    expect(sendAttemptedDurable(null)).toBe(false);
  });

  it("markSendAttempted sets phase + timestamp", () => {
    const stamped = markSendAttempted(recorded(), "2026-08-26T12:00:00.000Z");
    expect(stamped.phase).toBe("send_attempted");
    expect(stamped.sendAttemptedAt).toBe("2026-08-26T12:00:00.000Z");
    expect(sendAttemptedDurable(stamped)).toBe(true);
  });

  it("bind venue keeps ids and is not fill; first venue id wins", () => {
    const bound = bindVenueOrder(recorded(), "xtb-1");
    expect(bound.phase).toBe("venue_bound");
    expect(bound.venueOrderId).toBe("xtb-1");
    expect(bound.intentId).toBe("INT-DEC-1");
    expect(sendAttemptedDurable(bound)).toBe(true);
    expect(bindVenueOrder(bound, "xtb-other").venueOrderId).toBe("xtb-1");
  });

  it("reconstruct recorded → unknown, never error", () => {
    const rec = reconstructUnknown(recorded());
    expect(rec.outcome).toBe("unknown");
    expect(rec.sendAttempted).toBe(true);
    expect(rec.reason).toBe("crash_before_venue_ack");
    expect(rec.outcome).not.toBe("error");
    expect(rec.outcome).not.toBe("not_executed");
  });

  it("filled still sendAttempted; reconstruct unknown if no ledger", () => {
    const filled = markSubmitFilled(recorded());
    expect(filled.phase).toBe("filled");
    expect(sendAttemptedDurable(filled)).toBe(true);
    expect(reconstructUnknown(filled).reason).toBe(
      "crash_after_fill_unconfirmed",
    );
  });
});
