/**
 * V1.42 F2 — ExecutionState precedence matrix + trailing hint ≠ applied.
 */

import { describe, expect, it } from "vitest";
import { buildExecutionRecord } from "./execution-record.js";
import {
  buildExecutionState,
  formatExecutionStateCopy,
  isOrderInFlight,
} from "./execution-state.js";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  transitionPaperOrder,
} from "./paper-order.js";
import {
  markSendAttempted,
  recordSubmitIntent,
  reconstructUnknown,
} from "./submit-intent.js";

const INST = "inst-aapl";
const ASOF = "2026-08-31T09:00:00.000Z";

function baseIntent() {
  return recordSubmitIntent({
    decisionId: "dec-1",
    intentId: "int-1",
    orderId: "ORD-dec-1",
    accountId: "acc-1",
  });
}

describe("buildExecutionState precedence", () => {
  it("none when no facts", () => {
    const s = buildExecutionState({ instrumentId: INST, asOf: ASOF });
    expect(s.lifecycle).toBe("none");
    expect(s.orderState).toBe("none");
    expect(s.fillState).toBe("none");
    expect(s.source).toBe("none");
    expect(isOrderInFlight(s)).toBe(false);
    expect(formatExecutionStateCopy(s)).toBeNull();
  });

  it("pending_orders only → in_flight/pending (GP-03 germen)", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      pendingOrder: true,
    });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("pending");
    expect(s.source).toBe("pending_order");
    expect(isOrderInFlight(s)).toBe(true);
    expect(formatExecutionStateCopy(s)).toMatch(/en vuelo/i);
  });

  it("intent recorded (pre-send) → submit/pending", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      submitIntent: baseIntent(),
    });
    expect(s.lifecycle).toBe("submit");
    expect(s.orderState).toBe("pending");
    expect(s.source).toBe("submit_intent");
    expect(s.orderId).toBe("ORD-dec-1");
    expect(s.intentId).toBe("int-1");
    expect(s.decisionId).toBe("dec-1");
    expect(isOrderInFlight(s)).toBe(true);
  });

  it("UNKNOWN paper beats pending_orders", () => {
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 10,
        orderId: "ORD-u",
        intentId: "int-u",
      }),
      "UNKNOWN",
    );
    const s = buildExecutionState({
      instrumentId: INST,
      pendingOrder: true,
      paperOrder: paper,
    });
    expect(s.lifecycle).toBe("unknown");
    expect(s.orderState).toBe("unknown");
    expect(s.source).toBe("paper_order");
    expect(s.nextAction?.kind).toBe("review");
    expect(formatExecutionStateCopy(s)).toMatch(/no duplicar/i);
  });

  it("executionRecord unknown → unknown", () => {
    const intent = markSendAttempted(baseIntent());
    const s = buildExecutionState({
      instrumentId: INST,
      submitIntent: intent,
      executionRecord: reconstructUnknown(intent),
    });
    expect(s.lifecycle).toBe("unknown");
    expect(s.orderState).toBe("unknown");
    expect(isOrderInFlight(s)).toBe(true);
  });

  it("send_attempted without fill → unknown (OR-2 mid-flight)", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      submitIntent: markSendAttempted(baseIntent()),
    });
    expect(s.lifecycle).toBe("unknown");
    expect(s.orderState).toBe("unknown");
  });

  it("FILLED paper beats stale unknown intent", () => {
    const paper = applyPaperOrderFill(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 10,
          orderId: "ORD-dec-1",
          intentId: "int-1",
        }),
        "SUBMITTED",
      ),
      "tx-99",
    );
    const s = buildExecutionState({
      instrumentId: INST,
      paperOrder: paper,
      submitIntent: markSendAttempted(baseIntent()),
      executionRecord: buildExecutionRecord({
        sendAttempted: true,
        exception: "stale",
      }),
    });
    // Fill confirmed wins — but wait: we also have unknown record.
    // Plan: fill confirmed beats stale intent. Paper FILLED is confirmed fill.
    expect(s.lifecycle).toBe("filled");
    expect(s.orderState).toBe("filled");
    expect(s.fillState).toBe("complete");
    expect(s.transactionId).toBe("tx-99");
    expect(isOrderInFlight(s)).toBe(false);
  });

  it("paper_auto ledger fill → filled without PaperOrder", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      paperAutoLedger: { transactionId: "tx-auto-1" },
    });
    expect(s.lifecycle).toBe("filled");
    expect(s.orderState).toBe("filled");
    expect(s.source).toBe("paper_auto_ledger");
    expect(s.transactionId).toBe("tx-auto-1");
  });

  it("PARTIAL → in_flight/partial", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 10,
          orderId: "ORD-p",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 4 },
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("partial");
    expect(s.fillState).toBe("partial");
    expect(isOrderInFlight(s)).toBe(true);
    expect(formatExecutionStateCopy(s)).toMatch(/parcial/i);
  });

  it("REJECTED → failed/rejected", () => {
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 10,
        orderId: "ORD-r",
      }),
      "REJECTED",
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("failed");
    expect(s.orderState).toBe("rejected");
    expect(isOrderInFlight(s)).toBe(false);
    expect(formatExecutionStateCopy(s)).toMatch(/rechazada/i);
  });

  it("ACK → in_flight/accepted", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 10,
          orderId: "ORD-a",
        }),
        "SUBMITTED",
      ),
      "ACK",
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("accepted");
  });

  it("orderReconciled + filled → reconciled", () => {
    const paper = applyPaperOrderFill(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 5,
        orderId: "ORD-f",
      }),
      "tx-1",
    );
    const s = buildExecutionState({
      instrumentId: INST,
      paperOrder: paper,
      orderReconciled: true,
    });
    expect(s.lifecycle).toBe("reconciled");
    expect(s.orderState).toBe("filled");
    expect(isOrderInFlight(s)).toBe(false);
  });

  it("reconciliationState is independent of orderState", () => {
    const clean = buildExecutionState({
      instrumentId: INST,
      portfolioReconStatus: "ok",
    });
    expect(clean.reconciliationState).toBe("clean");
    expect(clean.lifecycle).toBe("none");

    const drift = buildExecutionState({
      instrumentId: INST,
      portfolioReconStatus: "drift",
    });
    expect(drift.reconciliationState).toBe("incident");
    expect(drift.lifecycle).toBe("none");

    const incident = buildExecutionState({
      instrumentId: INST,
      hasOpenIncident: true,
    });
    expect(incident.reconciliationState).toBe("incident");

    const lookup = buildExecutionState({
      instrumentId: INST,
      reconLookupFailed: true,
    });
    expect(lookup.reconciliationState).toBe("unknown");
  });
});

describe("trailing hint ≠ applied (GP-A7)", () => {
  it("trailingHint alone → hint, never applied", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      trailingHint: true,
    });
    expect(s.trailingState).toBe("hint");
  });

  it("trailingApplied fact required for applied", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      trailingHint: true,
      trailingApplied: true,
    });
    expect(s.trailingState).toBe("applied");
  });

  it("proposed before applied", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      trailingHint: true,
      trailingProposed: true,
    });
    expect(s.trailingState).toBe("proposed");
  });
});
