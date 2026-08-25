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

  it("Ciclo 4.8: surfaces entrySetup + phase/effort from F3 payload anchor", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        decisionSessions: [],
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: watchPlan({
                  entrySetup: "wyckoff",
                  status: "ARMED",
                  whyNot: ["entry"],
                }),
                wyckoffSpringAnchor: {
                  direction: "long",
                  ice: 85,
                  springLow: 85,
                  springHigh: 88,
                  phase: "lps",
                  effort: "result_ok",
                },
              },
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.setup).toEqual({
      entrySetup: "wyckoff",
      phase: "lps",
      effort: "result_ok",
    });
  });

  it("Ciclo 4.9: prefers session tradePlan over gate heuristic + Setup from anchor", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-blocked",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "BLOCKED",
              whyNot: ["regime"],
              entrySetup: "wyckoff",
              executionAllowed: false,
            }),
            wyckoffSpringAnchor: {
              phase: "sos",
              effort: "spring_high_effort",
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BLOCKED");
    expect(items[0]?.kind).not.toBe("BUY");
    expect(items[0]?.whyNot).toEqual(["regime"]);
    expect(items[0]?.setup).toEqual({
      entrySetup: "wyckoff",
      phase: "sos",
      effort: "spring_high_effort",
    });
  });

  it("Ciclo 5.0: surfaces thesisHealth review without changing EXPIRED→REVIEW kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-health",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "WATCH",
              whyNot: ["entry"],
              structuralStop: 90,
              entry: 100,
            }),
            thesisHealth: {
              hint: "reduce",
              status: "review",
              why: ["confidence_degraded", "stop_intact"],
              confidence: 0.3,
            },
          },
          {
            sessionId: "s-expired",
            kind: "propose",
            status: "open",
            instrumentId: "i3",
            symbol: "TEF",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "EXPIRED",
              whyNot: ["expired"],
            }),
          },
        ],
      }),
    );
    const health = items.find((i) => i.symbol === "BBVA");
    const expired = items.find((i) => i.symbol === "TEF");
    expect(health?.kind).toBe("WATCH");
    expect(health?.kind).not.toBe("REVIEW");
    expect(health?.thesisHealth?.status).toBe("review");
    expect(expired?.kind).toBe("REVIEW");
    expect(expired?.thesisHealth ?? null).toBeNull();
  });

  it("Ciclo 5.1: surfaces protectPlan protect_hint without changing kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-protect",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
            }),
            protectPlan: {
              status: "protect_hint",
              target1: 110,
              suggestedProtectStop: 100,
              rMultiple: 1,
              why: ["mfe_ge_1r"],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.protectPlan?.status).toBe("protect_hint");
    expect(items[0]?.protectPlan?.target1).toBe(110);
  });

  it("Ciclo 5.2: surfaces exitRadar trail_hint", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-exit",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
            }),
            exitRadar: {
              status: "trail_hint",
              suggestedTrailStop: 105,
              target1: 110,
              rMultiple: 1.5,
              why: ["mfe_ge_1_5r"],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.exitRadar?.status).toBe("trail_hint");
    expect(items[0]?.exitRadar?.suggestedTrailStop).toBe(105);
  });

  it("Ciclo 5.3: surfaces mfeMae metrics without changing kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-mfe",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
            }),
            mfeMae: {
              status: "favorable",
              mfeR: 1.8,
              maeR: 0.2,
              currentR: 0.8,
              why: ["peak_from_bars", "mfe_ge_1_5r"],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.mfeMae?.status).toBe("favorable");
    expect(items[0]?.mfeMae?.mfeR).toBe(1.8);
    expect(items[0]?.mfeMae?.maeR).toBe(0.2);
  });

  it("Ciclo 8.0: surfaces expectancy thin without changing kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-exp",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
              entrySetup: "breakout",
            }),
            expectancy: {
              status: "thin",
              entrySetup: "breakout",
              n: 1,
              expectancyR: 0.8,
              winRate: 1,
              avgWinR: 0.8,
              avgLossR: null,
              currentR: 0.8,
              why: ["not_permission", "live_proxy", "thin_sample"],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.expectancy?.status).toBe("thin");
    expect(items[0]?.expectancy?.expectancyR).toBe(0.8);
    expect(items[0]?.expectancy?.n).toBe(1);
  });

  it("Ciclo 8.1: surfaces trailPlan ratchet without changing kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-trail",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBVA",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
            }),
            trailPlan: {
              status: "ratchet",
              suggestedTrailStop: 115,
              lockedR: 1.5,
              peakMfeR: 2.5,
              currentR: 2.0,
              trailDistanceR: 1,
              why: ["not_permission", "hint_only", "ratchet_lock"],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.trailPlan?.status).toBe("ratchet");
    expect(items[0]?.trailPlan?.suggestedTrailStop).toBe(115);
    expect(items[0]?.trailPlan?.lockedR).toBe(1.5);
  });

  it("Ciclo 8.2: surfaces bracketPlan picture without changing kind", () => {
    const items = mapDecisionBoardToHoyQueue(
      board({
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s-bracket",
            kind: "propose",
            status: "open",
            instrumentId: "i3",
            symbol: "SAN",
            createdAt: "2026-08-24T08:00:00Z",
            gate: "PASS",
            tradePlan: watchPlan({
              status: "TRIGGERED",
              whyNot: [],
              entry: 100,
              structuralStop: 90,
              executionAllowed: true,
            }),
            bracketPlan: {
              status: "picture",
              entry: 100,
              stop: 90,
              target1: 110,
              target2: 120,
              target1R: 1,
              target2R: 2,
              legT1QtyFrac: 0.5,
              legT2QtyFrac: 0.5,
              why: [
                "aligned_protect_t1",
                "display_only",
                "not_permission",
                "hint_only",
                "no_broker_oco",
              ],
            },
          },
        ],
      }),
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("BUY");
    expect(items[0]?.bracketPlan?.status).toBe("picture");
    expect(items[0]?.bracketPlan?.target1).toBe(110);
    expect(items[0]?.bracketPlan?.target2).toBe(120);
    expect(items[0]?.bracketPlan?.legT1QtyFrac).toBe(0.5);
  });
});
