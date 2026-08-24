import { describe, expect, it } from "vitest";
import type { DecisionBoardV1 } from "./decision-board.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";
import { mapDecisionBoardToHoyQueue } from "./cognitive/hoy-queue.js";

function board(partial: Partial<DecisionBoardV1> = {}): DecisionBoardV1 {
  return {
    accountId: "acc1",
    generatedAt: "2026-08-24T09:30:00Z",
    buckets: {
      pendingConfirm: 1,
      vetoed: 1,
      deferred: 0,
      autoWaiting: 0,
      total: 2,
    },
    semiF3Queue: [
      { instrumentId: "i1", symbol: "SAN", status: "pending_confirm" },
    ],
    decisionSessions: [
      {
        sessionId: "s-veto",
        kind: "propose",
        status: "open",
        instrumentId: "i2",
        symbol: "BBVA",
        createdAt: "2026-08-24T08:00:00Z",
        gate: "VETO",
      },
    ],
    ...partial,
  };
}

function watchPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "d1",
    instrumentId: "i1",
    direction: "long",
    status: "WATCH",
    quantity: 0,
    riskPct: 0,
    whyNot: ["no_stop"],
    executionAllowed: false,
    ...overrides,
  };
}

describe("mapDecisionBoardToHoyQueue", () => {
  it("maps F3 queue to BUY and veto sessions to BLOCKED", () => {
    const items = mapDecisionBoardToHoyQueue(board());
    const kinds = items.map((i) => i.kind);
    expect(kinds).toContain("BUY");
    expect(kinds).toContain("BLOCKED");
    const blocked = items.find((i) => i.kind === "BLOCKED");
    expect(blocked?.whyNot).toContain("fit");
  });

  it("prefers live TradePlan WATCH over heuristic BUY for pending F3", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        decisionSessions: [],
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: { payload: { tradePlan: watchPlan() } },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("WATCH");
    expect(items[0]?.kind).not.toBe("BUY");
    expect(items[0]?.status).toBe("WATCH");
    expect(items[0]?.whyNot).toContain("no_stop");
  });

  it("keeps heuristic BUY for pending F3 when tradePlan is absent", () => {
    const items = mapDecisionBoardToHoyQueue(board({ decisionSessions: [] }));
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.status).toBe("TRIGGERED");
  });
});
