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
  reduceLifecycleEvents,
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
