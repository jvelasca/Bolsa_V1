/**
 * V1.42 F2 — Golden Paths that ExecutionState must close (spec §C GP-03/04/10).
 * GP-01/02/05–09 need F3 PositionOperatingTruth — not faked here.
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
  markSubmitFilled,
  recordSubmitIntent,
  reconstructUnknown,
} from "./submit-intent.js";

const INST = "inst-msft";
const DECISION = "dec-gp10";
const ORDER = "ORD-dec-gp10";
const INTENT = "int-gp10";

function intent() {
  return recordSubmitIntent({
    decisionId: DECISION,
    intentId: INTENT,
    orderId: ORDER,
    accountId: "acc-1",
  });
}

describe("ExecutionState Golden Paths V1.42 F2", () => {
  it("GP-03 Orden pendiente: pending_orders → in_flight/pending · Ver operaciones", () => {
    const s = buildExecutionState({
      instrumentId: INST,
      pendingOrder: true,
      asOf: "2026-08-31T10:00:00.000Z",
    });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("pending");
    expect(s.fillState).toBe("none");
    expect(s.nextAction?.kind).toBe("review");
    expect(s.nextAction?.label).toMatch(/operaciones/i);
    expect(s.nextAction?.allowsEntry).toBe(false);
    expect(isOrderInFlight(s)).toBe(true);
  });

  it("GP-03 Confirmada ACK: paper ACK → accepted", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 8,
          orderId: ORDER,
          intentId: INTENT,
        }),
        "SUBMITTED",
      ),
      "ACK",
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("accepted");
    expect(formatExecutionStateCopy(s)).toMatch(/aceptada/i);
  });

  it("GP-04 Fill parcial: PARTIAL → partial + fillState partial", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 10,
          orderId: ORDER,
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 3 },
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("in_flight");
    expect(s.orderState).toBe("partial");
    expect(s.fillState).toBe("partial");
    expect(isOrderInFlight(s)).toBe(true);
  });

  it("GP-10 Crash after submit → UNKNOWN · same ids · no second order", () => {
    const durable = markSendAttempted(intent());
    const record = reconstructUnknown(durable);
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 10,
        orderId: ORDER,
        intentId: INTENT,
      }),
      "UNKNOWN",
    );

    const afterCrash = buildExecutionState({
      instrumentId: INST,
      submitIntent: durable,
      executionRecord: record,
      paperOrder: paper,
    });
    expect(afterCrash.lifecycle).toBe("unknown");
    expect(afterCrash.orderState).toBe("unknown");
    expect(afterCrash.orderId).toBe(ORDER);
    expect(afterCrash.intentId).toBe(INTENT);
    expect(afterCrash.decisionId).toBe(DECISION);
    expect(afterCrash.nextAction?.kind).toBe("review");
    expect(formatExecutionStateCopy(afterCrash)).toMatch(/no duplicar/i);

    // Retry / recover with same durable ids — still one order identity.
    const retry = buildExecutionState({
      instrumentId: INST,
      submitIntent: durable,
      executionRecord: record,
      paperOrder: paper,
    });
    expect(retry.orderId).toBe(afterCrash.orderId);
    expect(retry.intentId).toBe(afterCrash.intentId);
    expect(retry.decisionId).toBe(afterCrash.decisionId);

    // Reconcile → filled with same orderId (no duplicate).
    const filledPaper = applyPaperOrderFill(paper, "tx-recovered");
    const filledIntent = markSubmitFilled(durable);
    const reconciled = buildExecutionState({
      instrumentId: INST,
      paperOrder: filledPaper,
      submitIntent: filledIntent,
      executionRecord: buildExecutionRecord({
        filled: true,
        transactionId: "tx-recovered",
      }),
      orderReconciled: true,
    });
    expect(reconciled.lifecycle).toBe("reconciled");
    expect(reconciled.orderState).toBe("filled");
    expect(reconciled.orderId).toBe(ORDER);
    expect(reconciled.intentId).toBe(INTENT);
    expect(isOrderInFlight(reconciled)).toBe(false);
  });

  it("filled happy path: FILLED paper", () => {
    const paper = applyPaperOrderFill(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 2,
        orderId: ORDER,
      }),
      "tx-ok",
    );
    const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
    expect(s.lifecycle).toBe("filled");
    expect(s.fillState).toBe("complete");
  });

  it("failed: CANCELLED / EXPIRED", () => {
    for (const status of ["CANCELLED", "EXPIRED"] as const) {
      const paper = transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "sell",
          quantity: 1,
          orderId: `ORD-${status}`,
        }),
        status,
      );
      const s = buildExecutionState({ instrumentId: INST, paperOrder: paper });
      expect(s.lifecycle).toBe("failed");
      expect(s.orderState).toBe(status.toLowerCase());
    }
  });

  it("AUTO facts absent → none (projection ≠ execute; PAPER_D_EXECUTE irrelevant)", () => {
    const s = buildExecutionState({ instrumentId: INST });
    expect(s.lifecycle).toBe("none");
    expect(s.source).toBe("none");
    expect(formatExecutionStateCopy(s)).toBeNull();
  });
});
