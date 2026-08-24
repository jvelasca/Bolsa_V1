import { describe, expect, it } from "vitest";
import type { DecisionBoardV1 } from "./decision-board.js";
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

describe("mapDecisionBoardToHoyQueue", () => {
  it("maps F3 queue to BUY and veto sessions to BLOCKED", () => {
    const items = mapDecisionBoardToHoyQueue(board());
    const kinds = items.map((i) => i.kind);
    expect(kinds).toContain("BUY");
    expect(kinds).toContain("BLOCKED");
    const blocked = items.find((i) => i.kind === "BLOCKED");
    expect(blocked?.whyNot).toContain("fit");
  });
});
