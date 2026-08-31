/**
 * V1.42 F2 — mismos hechos → mismo ExecutionState en Mercado / Hoy / Journal / Operaciones.
 */

import { describe, expect, it } from "vitest";
import {
  buildExecutionState,
  executionStateSurfaceSnapshot,
  formatExecutionStateCopy,
  type BuildExecutionStateInputV1,
} from "./execution-state.js";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  transitionPaperOrder,
} from "./paper-order.js";
import { markSendAttempted, recordSubmitIntent } from "./submit-intent.js";

const ASOF = "2026-08-31T11:00:00.000Z";

function fourSurfaces(input: BuildExecutionStateInputV1) {
  const mercado = buildExecutionState(input);
  const hoy = buildExecutionState(input);
  const journal = buildExecutionState(input);
  const operaciones = buildExecutionState(input);
  return { mercado, hoy, journal, operaciones };
}

describe("sameExecutionStateAcrossSurfaces V1.42 F2", () => {
  it("pending_orders → identical snapshot on all surfaces", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      instrumentId: "inst-aapl",
      asOf: ASOF,
      pendingOrder: true,
    });
    const snap = executionStateSurfaceSnapshot(mercado);
    expect(snap).toEqual({
      lifecycle: "in_flight",
      orderState: "pending",
      fillState: "none",
      reconciliationState: "clean",
      trailingState: "inactive",
      source: "pending_order",
      orderId: null,
      intentId: null,
      nextActionKind: "review",
    });
    expect(executionStateSurfaceSnapshot(hoy)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(journal)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(operaciones)).toEqual(snap);
    expect(formatExecutionStateCopy(mercado)).toBe(
      formatExecutionStateCopy(hoy),
    );
  });

  it("UNKNOWN crash facts → same copy and ids on all surfaces", () => {
    const intent = markSendAttempted(
      recordSubmitIntent({
        decisionId: "dec-same",
        intentId: "int-same",
        orderId: "ORD-same",
        accountId: "acc-1",
      }),
    );
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: "inst-aapl",
        side: "buy",
        quantity: 10,
        orderId: "ORD-same",
        intentId: "int-same",
      }),
      "UNKNOWN",
    );
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      instrumentId: "inst-aapl",
      asOf: ASOF,
      submitIntent: intent,
      paperOrder: paper,
    });
    const snap = executionStateSurfaceSnapshot(mercado);
    expect(snap.lifecycle).toBe("unknown");
    expect(snap.orderId).toBe("ORD-same");
    expect(snap.intentId).toBe("int-same");
    expect(snap.nextActionKind).toBe("review");
    expect(executionStateSurfaceSnapshot(hoy)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(journal)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(operaciones)).toEqual(snap);
    for (const s of [mercado, hoy, journal, operaciones]) {
      expect(formatExecutionStateCopy(s)).toMatch(/no duplicar/i);
    }
  });

  it("PARTIAL → same fillState on all surfaces", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: "inst-aapl",
          side: "buy",
          quantity: 10,
          orderId: "ORD-part",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 5 },
    );
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      instrumentId: "inst-aapl",
      paperOrder: paper,
      asOf: ASOF,
    });
    const snap = executionStateSurfaceSnapshot(mercado);
    expect(snap.orderState).toBe("partial");
    expect(snap.fillState).toBe("partial");
    expect(executionStateSurfaceSnapshot(hoy)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(journal)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(operaciones)).toEqual(snap);
  });

  it("FILLED → same terminal snapshot", () => {
    const paper = applyPaperOrderFill(
      buildPaperOrder({
        instrumentId: "inst-aapl",
        side: "buy",
        quantity: 3,
        orderId: "ORD-fill",
      }),
      "tx-1",
    );
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      instrumentId: "inst-aapl",
      paperOrder: paper,
      asOf: ASOF,
    });
    const snap = executionStateSurfaceSnapshot(mercado);
    expect(snap.lifecycle).toBe("filled");
    expect(snap.orderState).toBe("filled");
    expect(snap.fillState).toBe("complete");
    expect(snap.nextActionKind).toBeNull();
    expect(executionStateSurfaceSnapshot(hoy)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(journal)).toEqual(snap);
    expect(executionStateSurfaceSnapshot(operaciones)).toEqual(snap);
  });
});
