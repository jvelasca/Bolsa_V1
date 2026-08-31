/**
 * V1.42 F4 — Golden Paths for TradeStory (spec §C slices GP-01/03/04/05/08/10).
 */

import { describe, expect, it } from "vitest";
import { buildExecutionState } from "./execution-state.js";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  transitionPaperOrder,
} from "./paper-order.js";
import { buildPositionRevision } from "./position-revision.js";
import type { PositionStateV1 } from "./position-state.js";
import { markSendAttempted, recordSubmitIntent } from "./submit-intent.js";
import { buildTradeStory, tradeStorySurfaceSnapshot } from "./trade-story.js";

const INST = "inst-msft";
const DECISION = "dec-gp01";

function basePosition(
  overrides: Partial<PositionStateV1> = {},
): PositionStateV1 {
  return {
    positionId: "pos-gp",
    tradePlanId: "tp-gp",
    instrumentId: INST,
    direction: "long",
    status: "OPEN",
    plannedEntry: 100,
    actualEntry: 100,
    initialStop: 95,
    currentStop: 95,
    target1: 110,
    target2: 120,
    quantity: 10,
    remainingQuantity: 10,
    initialRisk: 5,
    realizedR: 0,
    unrealizedR: 0.4,
    mfeMae: { mfeR: null, maeR: null, source: "none" },
    thesisHealth: { status: "none" },
    protectionState: { status: "none" },
    trailing: { status: "none" },
    exitStatus: "none",
    createdAt: "2026-09-05T18:00:00.000Z",
    updatedAt: "2026-09-05T18:00:00.000Z",
    revisions: [],
    ...overrides,
  };
}

describe("TradeStory Golden Paths V1.42 F4", () => {
  it("GP-01 full chain: estudio→preparada→trigger→propuesta→confirmacion→fill", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: DECISION,
      study: {
        studiedAt: "2026-09-02T08:00:00.000Z",
        sessionId: "sess-gp",
        decisionId: DECISION,
        tradePlanStatus: "TRIGGERED",
        instrumentId: INST,
      },
      // Status alone has no stamp — caller supplies phase clocks (honesty).
      facts: [
        { kind: "preparada", asOf: "2026-09-03T09:00:00.000Z" },
        { kind: "trigger", asOf: "2026-09-05T10:00:00.000Z" },
      ],
      orderProposal: {
        schemaVersion: "1.0.0",
        proposalId: "prop-1",
        decisionId: DECISION,
        recommendationId: "rec-1",
        sessionId: "sess-gp",
        instrumentId: INST,
        status: "confirmed",
        createdAt: "2026-09-05T11:00:00.000Z",
        closedAt: "2026-09-05T12:00:00.000Z",
      },
      fills: [
        {
          price: 100,
          quantity: 10,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-gp",
        },
      ],
    });
    expect(story.events.map((e) => e.kind)).toEqual([
      "estudio",
      "preparada",
      "trigger",
      "propuesta",
      "confirmacion",
      "fill",
    ]);
    expect(story.events.every((e) => e.asOf)).toBe(true);
  });

  it("GP-03 pending: confirmacion fact + no invented fill clock from paper alone", () => {
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 8,
        orderId: "ORD-p",
      }),
      "ACK",
    );
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: DECISION,
      paperOrder: paper,
      facts: [{ kind: "confirmacion", asOf: "2026-09-05T12:00:00.000Z" }],
    });
    expect(story.events.map((e) => e.kind)).toEqual(["confirmacion"]);
    expect(story.events.some((e) => e.kind === "fill")).toBe(false);
  });

  it("GP-04 fill_partial from ExecutionState when asOf present", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 10,
          orderId: "ORD-part",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 3 },
    );
    const es = buildExecutionState({
      instrumentId: INST,
      paperOrder: paper,
      asOf: "2026-09-05T15:00:00.000Z",
    });
    const story = buildTradeStory({
      instrumentId: INST,
      executionState: es,
    });
    expect(story.events.some((e) => e.kind === "fill_partial")).toBe(true);
  });

  it("GP-05 stop→cierre from position revisions", () => {
    const closeAt = "2026-09-07T16:00:00.000Z";
    const stopRev = buildPositionRevision({
      at: "2026-09-07T15:00:00.000Z",
      previousStop: 95,
      nextStop: 94,
      origin: "stop",
      reason: "structural_stop",
    });
    const closeRev = buildPositionRevision({
      at: closeAt,
      previousStatus: "OPEN",
      nextStatus: "CLOSED",
      previousStop: 94,
      nextStop: 94,
      origin: "stop",
      reason: "exit_fill",
    });
    const story = buildTradeStory({
      instrumentId: INST,
      positionState: basePosition({
        status: "CLOSED",
        updatedAt: closeAt,
        revisions: [stopRev, closeRev],
      }),
    });
    const kinds = story.events.map((e) => e.kind);
    expect(kinds).toContain("stop_updated");
    expect(kinds).toContain("cierre");
    expect(kinds.indexOf("stop_updated")).toBeLessThan(kinds.indexOf("cierre"));
  });

  it("GP-08 trailing hint ≠ trailing_applied; applied only via revision origin trail", () => {
    const hintOnly = buildTradeStory({
      instrumentId: INST,
      facts: [],
      executionState: buildExecutionState({
        instrumentId: INST,
        asOf: "2026-09-10T10:00:00.000Z",
        trailingHint: true,
      }),
    });
    expect(hintOnly.events.some((e) => e.kind === "trailing_applied")).toBe(
      false,
    );

    const trailRev = buildPositionRevision({
      at: "2026-09-12T11:00:00.000Z",
      previousStop: 100,
      nextStop: 105,
      origin: "trail",
      reason: "trail_confirm",
    });
    const applied = buildTradeStory({
      instrumentId: INST,
      positionState: basePosition({
        currentStop: 105,
        revisions: [trailRev],
      }),
    });
    expect(applied.events.some((e) => e.kind === "trailing_applied")).toBe(
      true,
    );

    // Legacy: protect + reason containing trail still maps to trailing_applied.
    const legacy = buildTradeStory({
      instrumentId: INST,
      positionState: basePosition({
        currentStop: 105,
        revisions: [
          buildPositionRevision({
            at: "2026-09-12T11:00:00.000Z",
            previousStop: 100,
            nextStop: 105,
            origin: "protect",
            reason: "trailing_stop_confirm",
          }),
        ],
      }),
    });
    expect(legacy.events.some((e) => e.kind === "trailing_applied")).toBe(true);
  });

  it("GP-10 unknown_order → reconciled with same order identity", () => {
    const intent = markSendAttempted(
      recordSubmitIntent({
        decisionId: DECISION,
        intentId: "int-gp10",
        orderId: "ORD-gp10",
        accountId: "acc-1",
      }),
      "2026-09-05T13:00:00.000Z",
    );
    const paperUnknown = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 10,
        orderId: "ORD-gp10",
        intentId: "int-gp10",
      }),
      "UNKNOWN",
    );
    const afterCrash = buildTradeStory({
      instrumentId: INST,
      decisionId: DECISION,
      submitIntent: intent,
      paperOrder: paperUnknown,
      executionState: buildExecutionState({
        instrumentId: INST,
        submitIntent: intent,
        paperOrder: paperUnknown,
        asOf: "2026-09-05T13:05:00.000Z",
      }),
    });
    expect(afterCrash.events.some((e) => e.kind === "unknown_order")).toBe(
      true,
    );
    const unknown = afterCrash.events.find((e) => e.kind === "unknown_order")!;
    expect(unknown.refs.orderId).toBe("ORD-gp10");
    expect(unknown.refs.intentId).toBe("int-gp10");

    const filled = applyPaperOrderFill(paperUnknown, "tx-recovered");
    const reconciled = buildTradeStory({
      instrumentId: INST,
      decisionId: DECISION,
      executionState: buildExecutionState({
        instrumentId: INST,
        paperOrder: filled,
        orderReconciled: true,
        asOf: "2026-09-05T14:00:00.000Z",
      }),
    });
    expect(reconciled.events.some((e) => e.kind === "reconciled")).toBe(true);
    expect(reconciled.events.some((e) => e.kind === "fill")).toBe(true);
    const snap = tradeStorySurfaceSnapshot(reconciled);
    expect(snap.eventKinds).toContain("reconciled");
  });
});
