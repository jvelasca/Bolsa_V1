/**
 * V1.85/V1.86 — unit table: FSM · time · identity · idempotency · ENTRY accounting.
 * Runs in frontend-ci via vitest (no Playwright browser).
 */
import { describe, expect, it } from "vitest";
import { E2E_LIFECYCLE_POSITION_ID } from "./ids";
import {
  accountLifecycleFills,
  appendValidatedLifecycleEvent,
  buildLifecycleSnapshotFromEvents,
  lastFillPrice,
  reduceLifecycleEvents,
  stopWorsens,
  validateTransition,
  type LifecycleEventInput,
  type LifecycleStoreEvent,
  type LifecycleStoreEventKind,
} from "./lifecycle-events";

function appendAll(kinds: LifecycleStoreEventKind[]): LifecycleStoreEvent[] {
  let log: LifecycleStoreEvent[] = [];
  for (const kind of kinds) {
    const result = appendValidatedLifecycleEvent(log, { kind });
    expect(result.ok, `expected append ${kind}`).toBe(true);
    if (result.ok) log = result.log;
  }
  return log;
}

describe("V1.85 lifecycle FSM", () => {
  it("accepts trail golden sequence", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
      "POSITION_CLOSED",
    ]);
    expect(reduceLifecycleEvents(log).stage).toBe("closed");
    expect(reduceLifecycleEvents(log).lineagePath).toBe("trail");
  });

  it("accepts T2 golden shortcut (no T1_TRIGGERED, no EXIT)", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
      "POSITION_CLOSED",
    ]);
    expect(reduceLifecycleEvents(log).stage).toBe("closed");
    expect(reduceLifecycleEvents(log).lineagePath).toBe("t2");
  });

  it.each([
    {
      name: "T1_EXECUTED before OPEN",
      seed: [] as LifecycleStoreEventKind[],
      next: {
        kind: "T1_EXECUTED" as const,
        eventId: "evt-bad-t1-first",
      },
      code: "illegal_transition" as const,
    },
    {
      name: "T2_TRIGGERED before T1_EXECUTED",
      seed: ["POSITION_OPENED"] as LifecycleStoreEventKind[],
      next: {
        kind: "T2_TRIGGERED" as const,
        eventId: "evt-bad-t2-trig",
        at: "2026-09-02T12:15:00.000Z",
      },
      code: "illegal_transition" as const,
    },
    {
      name: "T2_EXECUTED before T2_TRIGGERED",
      seed: ["POSITION_OPENED", "T1_EXECUTED"] as LifecycleStoreEventKind[],
      next: {
        kind: "T2_EXECUTED" as const,
        eventId: "evt-bad-t2-exec",
        at: "2026-09-02T12:45:00.000Z",
      },
      code: "illegal_transition" as const,
    },
    {
      name: "POSITION_OPENED after CLOSED",
      seed: [
        "POSITION_OPENED",
        "T1_EXECUTED",
        "TRAIL_APPLIED",
        "EXIT_REQUIRED",
        "POSITION_CLOSED",
      ] as LifecycleStoreEventKind[],
      next: {
        kind: "POSITION_OPENED" as const,
        eventId: "evt-reopen-illegal",
        at: "2026-09-02T16:00:00.000Z",
        fillId: "fill-reopen-illegal",
      },
      code: "illegal_transition" as const,
    },
    {
      name: "POSITION_CLOSED twice",
      seed: [
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
        "POSITION_CLOSED",
      ] as LifecycleStoreEventKind[],
      next: {
        kind: "POSITION_CLOSED" as const,
        eventId: "evt-close-twice",
        at: "2026-09-02T16:00:00.000Z",
        fillId: "fill-mock-exit-2",
      },
      code: "illegal_transition" as const,
    },
    {
      name: "TRAIL after T2 path",
      seed: [
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
      ] as LifecycleStoreEventKind[],
      next: {
        kind: "TRAIL_APPLIED" as const,
        eventId: "evt-trail-on-t2",
        at: "2026-09-02T12:30:00.000Z",
      },
      code: "illegal_transition" as const,
    },
  ])("rejects $name", ({ seed, next, code }) => {
    const log = appendAll(seed);
    const result = appendValidatedLifecycleEvent(log, next);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(code);
    }
    expect(log).toHaveLength(seed.length);
  });

  it("validateTransition is table-driven", () => {
    expect(validateTransition("candidate", "POSITION_OPENED").ok).toBe(true);
    expect(validateTransition("open", "T2_EXECUTED").ok).toBe(false);
    expect(validateTransition("closed", "POSITION_OPENED").ok).toBe(false);
    expect(validateTransition("trailing", "TRAIL_APPLIED").ok).toBe(true);
    expect(validateTransition("trailing", "T2_TRIGGERED").ok).toBe(true);
    expect(validateTransition("t2_executed", "TRAIL_APPLIED").ok).toBe(true);
    expect(validateTransition("t2_ready", "POSITION_CLOSED").ok).toBe(true);
  });
});

describe("V1.98 trail + T2 coexist", () => {
  it("allows two TRAIL_APPLIED ratchets in trailing", () => {
    const log = appendAll(["POSITION_OPENED", "T1_EXECUTED", "TRAIL_APPLIED"]);
    const second = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "evt-trail-2",
      at: "2026-09-02T12:10:00.000Z",
      previousStop: 98,
      newStop: 100,
    });
    expect(second.ok).toBe(true);
    if (second.ok) {
      expect(second.stage).toBe("trailing");
      expect(second.log.filter((e) => e.kind === "TRAIL_APPLIED")).toHaveLength(
        2,
      );
    }
  });

  it("allows TRAIL then T2", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
    ]);
    const reduced = reduceLifecycleEvents(log);
    expect(reduced.stage).toBe("t2_executed");
    expect(reduced.lineagePath).toBe("t2");
  });

  it("allows T2 then TRAIL", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
    ]);
    const trail = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "evt-trail-after-t2",
      at: "2026-09-02T13:00:00.000Z",
      previousStop: 98,
      newStop: 101,
    });
    expect(trail.ok).toBe(true);
    if (trail.ok) {
      expect(trail.stage).toBe("trailing");
      expect(trail.lineagePath).toBe("trail");
    }
  });

  it("rejects SHORT trail relaxation", () => {
    let log: LifecycleStoreEvent[] = [];
    const open = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_OPENED",
      eventId: "open-short",
      side: "SHORT",
    });
    expect(open.ok).toBe(true);
    if (!open.ok) return;
    log = open.log;
    const t1 = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "t1-short",
      side: "SHORT",
    });
    expect(t1.ok).toBe(true);
    if (!t1.ok) return;
    log = t1.log;
    const relax = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "evt-relax-short",
      side: "SHORT",
      previousStop: 110,
      newStop: 115,
    });
    expect(relax.ok).toBe(false);
    if (!relax.ok) expect(relax.error.code).toBe("trail_relaxation");
  });

  it("trail geometry uses last fill not mock 106", () => {
    let log: LifecycleStoreEvent[] = [];
    const open = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_OPENED",
      eventId: "open-hi",
      quantity: 10,
      price: 200,
      fillId: "fill-open-hi",
    });
    expect(open.ok).toBe(true);
    if (!open.ok) return;
    log = open.log;
    const t1 = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "t1-hi",
      quantity: 5,
      price: 230,
      fillId: "fill-t1-hi",
    });
    expect(t1.ok).toBe(true);
    if (!t1.ok) return;
    log = t1.log;
    const trail = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "evt-trail-hi",
      at: "2026-09-02T12:00:00.000Z",
      previousStop: 190,
      newStop: 220,
    });
    expect(trail.ok).toBe(true);
    if (trail.ok) expect(trail.stage).toBe("trailing");
  });
});

describe("V1.99 position management", () => {
  it("G1 OPEN → EXIT (birth stop, no TRAIL)", () => {
    const log = appendAll(["POSITION_OPENED", "POSITION_CLOSED"]);
    const reduced = reduceLifecycleEvents(log);
    expect(reduced.stage).toBe("closed");
    expect(log.some((e) => e.kind === "TRAIL_APPLIED")).toBe(false);
    expect(accountLifecycleFills(log).remaining).toBe(0);
  });

  it("G4 OPEN → T1 → TRAIL → TRAIL → EXIT", () => {
    let log = appendAll(["POSITION_OPENED", "T1_EXECUTED"]);
    const t1 = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g4-trail-1",
      at: "2026-09-02T12:00:00.000Z",
      previousStop: 95,
      newStop: 98,
    });
    expect(t1.ok).toBe(true);
    if (!t1.ok) return;
    log = t1.log;
    const t2 = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g4-trail-2",
      at: "2026-09-02T12:10:00.000Z",
      previousStop: 98,
      newStop: 100,
    });
    expect(t2.ok).toBe(true);
    if (!t2.ok) return;
    log = t2.log;
    expect(log.filter((e) => e.kind === "TRAIL_APPLIED")).toHaveLength(2);
    const closed = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_CLOSED",
      eventId: "g4-exit",
      at: "2026-09-02T15:00:00.000Z",
      fillId: "fill-g4-exit",
    });
    expect(closed.ok).toBe(true);
    if (closed.ok) expect(closed.stage).toBe("closed");
  });

  it("G5 aggressive T1→TRAIL×2→T2→TRAIL→EXIT + lineage ≠ history", () => {
    let log: LifecycleStoreEvent[] = [];
    const open = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_OPENED",
      eventId: "g5-open",
      quantity: 10,
      price: 100,
      fillId: "fill-g5-open",
    });
    expect(open.ok).toBe(true);
    if (!open.ok) return;
    log = open.log;

    const t1 = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "g5-t1",
      at: "2026-09-02T11:30:00.000Z",
      quantity: 5,
      price: 120,
      fillId: "fill-g5-t1",
    });
    expect(t1.ok).toBe(true);
    if (!t1.ok) return;
    log = t1.log;
    expect(lastFillPrice(log, "t1_executed", "trail")).toBe(120);

    for (const [id, prev, next, at] of [
      ["g5-trail-1", 95, 100, "2026-09-02T12:00:00.000Z"],
      ["g5-trail-2", 100, 105, "2026-09-02T12:10:00.000Z"],
    ] as const) {
      expect(stopWorsens("LONG", prev, next)).toBe(false);
      const trail = appendValidatedLifecycleEvent(log, {
        kind: "TRAIL_APPLIED",
        eventId: id,
        at,
        previousStop: prev,
        newStop: next,
      });
      expect(trail.ok).toBe(true);
      if (!trail.ok) return;
      log = trail.log;
    }

    const trig = appendValidatedLifecycleEvent(log, {
      kind: "T2_TRIGGERED",
      eventId: "g5-t2-trig",
      at: "2026-09-02T12:15:00.000Z",
    });
    expect(trig.ok).toBe(true);
    if (!trig.ok) return;
    log = trig.log;

    const exec = appendValidatedLifecycleEvent(log, {
      kind: "T2_EXECUTED",
      eventId: "g5-t2-exec",
      at: "2026-09-02T12:45:00.000Z",
      quantity: 3,
      price: 125,
      fillId: "fill-g5-t2",
    });
    expect(exec.ok).toBe(true);
    if (!exec.ok) return;
    log = exec.log;
    expect(accountLifecycleFills(log).remaining).toBe(2);
    expect(lastFillPrice(log, "t2_executed", "t2")).toBe(125);

    const trail3 = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g5-trail-3",
      at: "2026-09-02T13:00:00.000Z",
      previousStop: 105,
      newStop: 110,
    });
    expect(trail3.ok).toBe(true);
    if (!trail3.ok) return;
    log = trail3.log;
    const afterTrail = reduceLifecycleEvents(log);
    expect(afterTrail.stage).toBe("trailing");
    expect(afterTrail.lineagePath).toBe("trail");
    expect(log.some((e) => e.kind === "T2_EXECUTED")).toBe(true);
    expect(lastFillPrice(log, afterTrail.stage, afterTrail.lineagePath)).toBe(
      125,
    );

    const exit = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_CLOSED",
      eventId: "g5-exit",
      at: "2026-09-02T15:00:00.000Z",
      fillId: "fill-g5-exit",
      quantity: 2,
      price: 125,
    });
    expect(exit.ok).toBe(true);
    if (exit.ok) {
      expect(exit.stage).toBe("closed");
      expect(accountLifecycleFills(exit.log).remaining).toBe(0);
    }
  });

  it("G6 OPEN → T1 → T2 → TRAIL → TRAIL → EXIT", () => {
    let log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
    ]);
    const trail1 = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g6-trail-1",
      at: "2026-09-02T13:00:00.000Z",
      previousStop: 98,
      newStop: 101,
    });
    expect(trail1.ok).toBe(true);
    if (!trail1.ok) return;
    log = trail1.log;
    const trail2 = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g6-trail-2",
      at: "2026-09-02T13:10:00.000Z",
      previousStop: 101,
      newStop: 104,
    });
    expect(trail2.ok).toBe(true);
    if (!trail2.ok) return;
    log = trail2.log;
    expect(reduceLifecycleEvents(log).lineagePath).toBe("trail");
    expect(log.some((e) => e.kind === "T2_EXECUTED")).toBe(true);
    const exit = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_CLOSED",
      eventId: "g6-exit",
      at: "2026-09-02T15:00:00.000Z",
      fillId: "fill-g6-exit",
    });
    expect(exit.ok).toBe(true);
    if (exit.ok) expect(exit.stage).toBe("closed");
  });

  it("G8 stop worsen LONG/SHORT ratchets", () => {
    expect(stopWorsens("LONG", 100, 105)).toBe(false);
    expect(stopWorsens("LONG", 105, 110)).toBe(false);
    expect(stopWorsens("LONG", 110, 105)).toBe(true);
    expect(stopWorsens("SHORT", 100, 95)).toBe(false);
    expect(stopWorsens("SHORT", 95, 90)).toBe(false);
    expect(stopWorsens("SHORT", 90, 95)).toBe(true);

    let log: LifecycleStoreEvent[] = [];
    const open = appendValidatedLifecycleEvent(log, {
      kind: "POSITION_OPENED",
      eventId: "g8-open",
      quantity: 10,
      price: 100,
      fillId: "fill-g8-open",
    });
    expect(open.ok).toBe(true);
    if (!open.ok) return;
    log = open.log;
    const t1 = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "g8-t1",
      at: "2026-09-02T11:30:00.000Z",
      quantity: 5,
      price: 120,
      fillId: "fill-g8-t1",
    });
    expect(t1.ok).toBe(true);
    if (!t1.ok) return;
    log = t1.log;
    for (const [id, prev, next, at] of [
      ["g8-l1", 100, 105, "2026-09-02T12:00:00.000Z"],
      ["g8-l2", 105, 110, "2026-09-02T12:10:00.000Z"],
    ] as const) {
      const ok = appendValidatedLifecycleEvent(log, {
        kind: "TRAIL_APPLIED",
        eventId: id,
        at,
        previousStop: prev,
        newStop: next,
      });
      expect(ok.ok).toBe(true);
      if (!ok.ok) return;
      log = ok.log;
    }
    const deny = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      eventId: "g8-deny",
      at: "2026-09-02T12:20:00.000Z",
      previousStop: 110,
      newStop: 105,
    });
    expect(deny.ok).toBe(false);
    if (!deny.ok) expect(deny.error.code).toBe("trail_relaxation");
  });
});

describe("V1.85 lifecycle time + identity", () => {
  it("rejects time regression", () => {
    const log = appendAll(["POSITION_OPENED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      at: "2026-09-02T09:00:00.000Z",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("time_regression");
  });

  it("rejects duplicate fillId with different eventId", () => {
    const log = appendAll(["POSITION_OPENED", "T1_EXECUTED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "T2_TRIGGERED",
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const withT2 = result.log;
    const dup = appendValidatedLifecycleEvent(withT2, {
      kind: "T2_EXECUTED",
      fillId: "fill-mock-t1",
      eventId: "evt-other-t2",
    });
    expect(dup.ok).toBe(false);
    if (!dup.ok) expect(dup.error.code).toBe("duplicate_fill_id");
  });

  it("rejects positionId mismatch", () => {
    const log = appendAll(["POSITION_OPENED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      positionId: "pos-other",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("position_mismatch");
  });

  it("idempotent same eventId does not grow log", () => {
    let log = appendAll(["POSITION_OPENED"]);
    const input: LifecycleEventInput = {
      kind: "T1_EXECUTED",
      eventId: "evt-fixed-t1",
    };
    const first = appendValidatedLifecycleEvent(log, input);
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    log = first.log;
    expect(log).toHaveLength(2);
    const second = appendValidatedLifecycleEvent(log, input);
    expect(second.ok).toBe(true);
    if (!second.ok) return;
    expect(second.idempotent).toBe(true);
    expect(second.log).toHaveLength(2);
    expect(second.log[0]?.positionId).toBe(E2E_LIFECYCLE_POSITION_ID);
  });

  it("idempotent CLOSE replay after remaining=0 still matches", () => {
    let log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
    ]);
    const closeBody: LifecycleEventInput = {
      kind: "POSITION_CLOSED",
      eventId: "evt-close-once",
    };
    const first = appendValidatedLifecycleEvent(log, closeBody);
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    log = first.log;
    expect(accountLifecycleFills(log).remaining).toBe(0);
    const second = appendValidatedLifecycleEvent(log, closeBody);
    expect(second.ok).toBe(true);
    if (!second.ok) return;
    expect(second.idempotent).toBe(true);
    expect(second.log).toHaveLength(5);
  });

  it("reduce throws on illegal log (fail-closed)", () => {
    const forged: LifecycleStoreEvent[] = [
      {
        eventId: "a",
        positionId: E2E_LIFECYCLE_POSITION_ID,
        kind: "T1_EXECUTED",
        at: "2026-09-02T11:30:00.000Z",
      },
    ];
    expect(() => reduceLifecycleEvents(forged)).toThrow(/illegal transition/);
  });
});

describe("V1.86 lifecycle accounting + guards", () => {
  it("OPEN debits cash; equity = initial + pnl", () => {
    const log = appendAll(["POSITION_OPENED"]);
    const acct = accountLifecycleFills(log);
    expect(acct.cash).toBe(100_000 - 10 * 100);
    expect(acct.remaining).toBe(10);
    expect(acct.totalEquity).toBe(acct.cash + acct.marketValue);
    expect(acct.totalEquity).toBe(
      acct.initialEquity + acct.realizedPnl + acct.unrealizedPnl,
    );
  });

  it("trail CLOSED realized PnL lives in cash equity", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
      "POSITION_CLOSED",
    ]);
    const acct = accountLifecycleFills(log);
    // ENTRY -1000; T1 +525; EXIT +530 ⇒ cash 100055; realized 55
    expect(acct.remaining).toBe(0);
    expect(acct.realizedPnl).toBe(55);
    expect(acct.unrealizedPnl).toBe(0);
    expect(acct.totalPnl).toBe(55);
    expect(acct.cash).toBe(100_055);
    expect(acct.totalEquity).toBe(acct.cash);

    const snap = buildLifecycleSnapshotFromEvents(log);
    expect(snap.totalEquity).toBe(acct.totalEquity);
    expect(snap.cash).toBe(acct.cash);
    expect(snap.position?.operational?.realizedPnl).toBe(55);
    expect(snap.position?.operational?.totalPnl).toBe(55);
  });

  it("T2 CLOSED accounting", () => {
    const log = appendAll([
      "POSITION_OPENED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
      "POSITION_CLOSED",
    ]);
    const acct = accountLifecycleFills(log);
    // ENTRY -1000; T1 +525; T2 +330; EXIT +220 ⇒ cash 100075; realized 75
    expect(acct.realizedPnl).toBe(75);
    expect(acct.cash).toBe(100_075);
    expect(acct.totalEquity).toBe(100_075);
  });

  it("same eventId different payload → event_id_conflict", () => {
    let log = appendAll(["POSITION_OPENED"]);
    const first = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "evt-123",
      quantity: 5,
      price: 105,
    });
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    log = first.log;
    const conflict = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      eventId: "evt-123",
      quantity: 8,
      price: 130,
    });
    expect(conflict.ok).toBe(false);
    if (!conflict.ok) expect(conflict.error.code).toBe("event_id_conflict");
    expect(log).toHaveLength(2);
  });

  it("rejects identity mismatch instrumentId", () => {
    const log = appendAll(["POSITION_OPENED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      instrumentId: "inst-nvda",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("identity_mismatch");
  });

  it("rejects trail relaxation LONG", () => {
    const log = appendAll(["POSITION_OPENED", "T1_EXECUTED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "TRAIL_APPLIED",
      previousStop: 98,
      newStop: 92,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("trail_relaxation");
  });

  it("rejects invalid quantity", () => {
    const log = appendAll(["POSITION_OPENED"]);
    const result = appendValidatedLifecycleEvent(log, {
      kind: "T1_EXECUTED",
      quantity: -5,
      eventId: "evt-neg-qty",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("invalid_payload");
  });

  it("rejects malformed timestamp", () => {
    const result = appendValidatedLifecycleEvent([], {
      kind: "POSITION_OPENED",
      at: "not-a-date",
      eventId: "evt-bad-ts",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe("invalid_timestamp");
  });
});
