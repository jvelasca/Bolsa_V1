import { describe, expect, it } from "vitest";
import {
  buildPositionOperationalView,
  buildStopHistory,
  mapOperatingStateToDeskStatus,
  type PositionOperationalStateV1,
} from "./position-operational-view.js";
import { resolveReconOperatingState } from "./operational-context.js";
import {
  POSITION_REVISION_ORIGINS,
  revisionsFromUnknown,
  type PositionRevisionOriginV1,
} from "./position-revision.js";
import {
  PORTFOLIO_RECON_STATUSES,
  mapPortfolioReconToPovRecon,
  type PortfolioReconStatusV1,
} from "./reconciliation-opening-veto.js";
import type { PositionStateV1 } from "./position-state.js";

function basePosition(
  overrides: Partial<PositionStateV1> = {},
): PositionStateV1 {
  return {
    positionId: "pos-1",
    tradePlanId: "tp-A",
    instrumentId: "A",
    direction: "long",
    status: "OPEN",
    plannedEntry: 100,
    actualEntry: 100,
    initialStop: 95,
    currentStop: 98,
    target1: 110,
    target2: 120,
    quantity: 10,
    remainingQuantity: 10,
    initialRisk: 50,
    realizedR: 0,
    unrealizedR: 0.5,
    mfeMae: { mfeR: null, maeR: null, source: "none" },
    thesisHealth: { status: "none" },
    protectionState: { status: "none" },
    trailing: { status: "none" },
    exitStatus: "none",
    createdAt: "2026-09-01T09:00:00Z",
    updatedAt: "2026-09-01T10:00:00Z",
    target1Leg: { status: "pending" },
    target2Leg: { status: "pending" },
    revisions: [
      {
        revisionId: "r1",
        at: "2026-09-01T10:00:00Z",
        previousStop: 95,
        nextStop: 98,
        previousStatus: "OPEN",
        nextStatus: "PROTECTED",
        origin: "protect",
        reason: "protect",
      },
      {
        revisionId: "r2",
        at: "2026-09-01T12:00:00Z",
        previousStop: 98,
        nextStop: 102,
        previousStatus: "PROTECTED",
        nextStatus: "PROTECTED",
        origin: "trail",
        reason: "trail",
      },
    ],
    ...overrides,
  };
}

describe("buildStopHistory", () => {
  it("GP-V155-01: Initial + Trail entries with deltas", () => {
    const history = buildStopHistory(basePosition());
    expect(history[0]).toMatchObject({ label: "Initial", stop: 95 });
    expect(history.some((h) => h.label === "Trail #1" && h.stop === 102)).toBe(
      true,
    );
    const trail = history.find((h) => h.label === "Trail #1");
    expect(trail?.delta).toBe(4);
  });
});

describe("buildPositionOperationalView", () => {
  it("GP-V155-02: T1 executed → T1_EXECUTED + primaryAction", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        status: "PARTIAL",
        remainingQuantity: 7,
        target1Leg: {
          status: "executed",
          fillId: "tx-t1",
          at: "2026-09-01T11:00:00Z",
        },
      }),
      deskStatus: "reduced",
    });
    expect(view.operatingState).toBe("T1_EXECUTED");
    expect(view.t1?.fillId).toBe("tx-t1");
    expect(view.events.some((e) => e.kind === "T1_EXECUTED")).toBe(true);
  });

  it("GP-V155-03: mark >= T1 with pending leg stays pending", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        target1Leg: { status: "pending" },
      }),
    });
    expect(view.t1?.status).toBe("pending");
    expect(view.operatingState).not.toBe("T1_EXECUTED");
  });

  it("GP-V155-04: stop history monotonic trail stops", () => {
    const view = buildPositionOperationalView({
      position: basePosition(),
    });
    const trailStops = view.stopHistory
      .filter((h) => h.origin === "trail")
      .map((h) => h.stop);
    for (let i = 1; i < trailStops.length; i++) {
      expect(trailStops[i]).toBeGreaterThan(trailStops[i - 1]!);
    }
  });
});

describe("V1.57 GP-V157-01 T2 operating state", () => {
  it("T2 triggered → T2_READY (even after T1 executed)", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        status: "PARTIAL",
        remainingQuantity: 7,
        target1Leg: {
          status: "executed",
          fillId: "tx-t1",
          at: "2026-09-01T11:00:00Z",
        },
        target2Leg: {
          status: "triggered",
          at: "2026-09-01T13:00:00Z",
        },
      }),
    });
    expect(view.operatingState).toBe("T2_READY");
    expect(view.events.some((e) => e.kind === "T2_TRIGGERED")).toBe(true);
  });

  it("T2 executed + remaining > 0 → T2_EXECUTED + T2_FILL", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        status: "PARTIAL",
        remainingQuantity: 3,
        target1Leg: {
          status: "executed",
          fillId: "tx-t1",
          at: "2026-09-01T11:00:00Z",
        },
        target2Leg: {
          status: "executed",
          fillId: "tx-t2",
          at: "2026-09-01T14:00:00Z",
        },
      }),
    });
    expect(view.operatingState).toBe("T2_EXECUTED");
    expect(view.events.some((e) => e.kind === "T2_EXECUTED")).toBe(true);
    expect(
      view.events.some((e) => e.kind === "T2_FILL" && e.fillId === "tx-t2"),
    ).toBe(true);
    expect(mapOperatingStateToDeskStatus("T2_EXECUTED")).toBe("reduced");
    expect(mapOperatingStateToDeskStatus("T2_READY")).toBe("reduced");
  });

  it("T2 executed + CLOSED → CLOSED", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        status: "CLOSED",
        quantity: 0,
        remainingQuantity: 0,
        currentStop: 95,
        target2Leg: {
          status: "executed",
          fillId: "tx-t2",
          at: "2026-09-01T14:00:00Z",
        },
      }),
    });
    expect(view.operatingState).toBe("CLOSED");
  });
});

describe("V1.57 GP-V157-02 stop history origins", () => {
  it("protect → override → trail: all visible; trail delta vs override", () => {
    const history = buildStopHistory(
      basePosition({
        currentStop: 103,
        revisions: [
          {
            revisionId: "r1",
            at: "2026-09-01T10:00:00Z",
            previousStop: 95,
            nextStop: 98,
            previousStatus: "OPEN",
            nextStatus: "PROTECTED",
            origin: "protect",
            reason: "protect",
          },
          {
            revisionId: "r-ov",
            at: "2026-09-01T11:00:00Z",
            previousStop: 98,
            nextStop: 100,
            previousStatus: "PROTECTED",
            nextStatus: "PROTECTED",
            origin: "override",
            reason: "manual",
          },
          {
            revisionId: "r-tr",
            at: "2026-09-01T12:00:00Z",
            previousStop: 100,
            nextStop: 103,
            previousStatus: "PROTECTED",
            nextStatus: "PROTECTED",
            origin: "trail",
            reason: "trail",
          },
        ],
      }),
    );
    expect(history.map((h) => h.origin)).toEqual([
      "birth",
      "protect",
      "override",
      "trail",
    ]);
    expect(history.find((h) => h.origin === "override")?.label).toBe(
      "Ajuste manual",
    );
    const trail = history.find((h) => h.origin === "trail");
    expect(trail?.stop).toBe(103);
    expect(trail?.delta).toBe(3);
  });

  it("reduce and stop origins appear with labels", () => {
    const history = buildStopHistory(
      basePosition({
        currentStop: 99,
        revisions: [
          {
            revisionId: "r-red",
            at: "2026-09-01T10:30:00Z",
            previousStop: 95,
            nextStop: 97,
            previousStatus: "OPEN",
            nextStatus: "PARTIAL",
            origin: "reduce",
            reason: "t1",
          },
          {
            revisionId: "r-st",
            at: "2026-09-01T11:00:00Z",
            previousStop: 97,
            nextStop: 99,
            previousStatus: "PARTIAL",
            nextStatus: "PROTECTED",
            origin: "stop",
            reason: "stop",
          },
        ],
      }),
    );
    expect(
      history.some((h) => h.origin === "reduce" && h.label === "Reduce"),
    ).toBe(true);
    expect(history.some((h) => h.origin === "stop" && h.label === "Stop")).toBe(
      true,
    );
  });
});

describe("V1.57 GP-V157-03 recon drift", () => {
  it("PROTECTED + drift → RECONCILIATION_DRIFT not PROTECTED", () => {
    const view = buildPositionOperationalView({
      position: basePosition({ status: "PROTECTED" }),
      reconStatus: "drift",
    });
    expect(view.operatingState).toBe("RECONCILIATION_DRIFT");
    expect(view.operatingState).not.toBe("PROTECTED");
    expect(mapOperatingStateToDeskStatus("RECONCILIATION_DRIFT")).toBe(
      "denied",
    );
  });

  it("unavailable → RECONCILIATION_ERROR (distinct from drift)", () => {
    const view = buildPositionOperationalView({
      position: basePosition({ status: "PROTECTED" }),
      reconStatus: "unavailable",
    });
    expect(view.operatingState).toBe("RECONCILIATION_ERROR");
  });
});

describe("V1.57 exhaustiveness", () => {
  it("every PositionRevisionOriginV1 has a stop-history label", () => {
    const origins: Record<PositionRevisionOriginV1, true> = {
      protect: true,
      trail: true,
      reduce: true,
      override: true,
      stop: true,
    };
    expect(POSITION_REVISION_ORIGINS.slice().sort()).toEqual(
      (Object.keys(origins) as PositionRevisionOriginV1[]).sort(),
    );
    for (const origin of POSITION_REVISION_ORIGINS) {
      const history = buildStopHistory(
        basePosition({
          currentStop: 100,
          revisions: [
            {
              revisionId: `r-${origin}`,
              at: "2026-09-01T10:00:00Z",
              previousStop: 95,
              nextStop: 100,
              previousStatus: "OPEN",
              nextStatus: "PROTECTED",
              origin,
              reason: origin,
            },
          ],
        }),
      );
      expect(history.some((h) => h.origin === origin)).toBe(true);
    }
  });

  it("every PositionOperationalStateV1 maps to a desk status", () => {
    const states: Record<PositionOperationalStateV1, true> = {
      OPEN_UNPROTECTED: true,
      PROTECTED: true,
      TRAILING: true,
      PARTIALLY_REDUCED: true,
      EXIT_PENDING: true,
      CLOSED: true,
      RECONCILIATION_ERROR: true,
      RECONCILIATION_DRIFT: true,
      PROTECT_REQUIRED: true,
      T1_READY: true,
      T1_EXECUTED: true,
      T2_READY: true,
      T2_EXECUTED: true,
      EXIT_REQUIRED: true,
    };
    for (const state of Object.keys(states) as PositionOperationalStateV1[]) {
      expect(typeof mapOperatingStateToDeskStatus(state)).toBe("string");
    }
  });

  it("GP-V161-01: unknown recon wire → unavailable not clean", () => {
    expect(mapPortfolioReconToPovRecon("error")).toBe("unavailable");
    expect(mapPortfolioReconToPovRecon("unknown")).toBe("unavailable");
    expect(mapPortfolioReconToPovRecon("garbage")).toBe("unavailable");
    expect(mapPortfolioReconToPovRecon(null)).toBeNull();
    expect(mapPortfolioReconToPovRecon("ok")).toBe("clean");
  });

  it("every PortfolioReconStatusV1 is handled", () => {
    const expected: Record<PortfolioReconStatusV1, true> = {
      clean: true,
      drift: true,
      unavailable: true,
    };
    expect(PORTFOLIO_RECON_STATUSES.slice().sort()).toEqual(
      (Object.keys(expected) as PortfolioReconStatusV1[]).sort(),
    );
    expect(resolveReconOperatingState("clean")).toBeNull();
    expect(resolveReconOperatingState("drift")).toBe("RECONCILIATION_DRIFT");
    expect(resolveReconOperatingState("unavailable")).toBe(
      "RECONCILIATION_ERROR",
    );
  });
});

describe("V1.65 GP-V165 identity", () => {
  it("GP-V165-03: decisionId and tradePlanId diverge in POV", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        decisionId: "DEC-1",
        tradePlanId: "TP-1",
      }),
    });
    expect(view.decisionId).toBe("DEC-1");
    expect(view.tradePlanId).toBe("TP-1");
    expect(view.lineageCollapsed).toBe(false);
  });

  it("GP-V165-02: legacy without decisionId → null + lineageCollapsed", () => {
    const view = buildPositionOperationalView({
      position: basePosition({ tradePlanId: "TP-1" }),
    });
    expect(view.decisionId).toBeNull();
    expect(view.lineageCollapsed).toBe(true);
  });
});

describe("V1.71 GP-V171 TS/Python POV golden", () => {
  it("T2_EXECUTED + primaryAction MONITOR", () => {
    const view = buildPositionOperationalView({
      position: basePosition({
        status: "PARTIAL",
        remainingQuantity: 3,
        target1Leg: {
          status: "executed",
          fillId: "tx-t1",
          at: "2026-09-01T11:00:00Z",
        },
        target2Leg: {
          status: "executed",
          fillId: "tx-t2",
          at: "2026-09-01T14:00:00Z",
        },
      }),
    });
    expect(view.operatingState).toBe("T2_EXECUTED");
    expect(view.primaryAction).toBe("MONITOR");
    expect(view.levels.currentStop).toBe(98);
    expect(view.levels.target2).toBe(120);
  });

  it("recon drift → RECONCILIATION_DRIFT + BLOQUEADO", () => {
    const view = buildPositionOperationalView({
      position: basePosition(),
      reconStatus: "drift",
    });
    expect(view.operatingState).toBe("RECONCILIATION_DRIFT");
    expect(view.primaryAction).toBe("BLOQUEADO");
  });

  it("invalid revision origin is dropped (not coerced to stop)", () => {
    const kept = revisionsFromUnknown([
      {
        revisionId: "r-bad",
        at: "2026-09-01T10:00:00Z",
        origin: "not-a-real-origin",
        nextStop: 96,
      },
      {
        revisionId: "r-ok",
        at: "2026-09-01T10:00:00Z",
        origin: "protect",
        nextStop: 98,
      },
    ]);
    expect(kept).toHaveLength(1);
    expect(kept[0]?.origin).toBe("protect");
  });

  it("stopHistory labels for all five revision origins", () => {
    const origins: PositionRevisionOriginV1[] = [
      "protect",
      "trail",
      "reduce",
      "override",
      "stop",
    ];
    const history = buildStopHistory(
      basePosition({
        revisions: origins.map((origin, i) => ({
          revisionId: `r-${origin}`,
          at: `2026-09-01T10:0${i}:00Z`,
          previousStop: 95 + i,
          nextStop: 96 + i,
          previousStatus: "OPEN",
          nextStatus: "OPEN",
          origin,
          reason: origin,
        })),
      }),
    );
    const revEntries = history.filter(
      (h) => h.origin !== "birth" && h.origin !== "current",
    );
    expect(revEntries.map((h) => h.origin)).toEqual(origins);
    expect(revEntries.map((h) => h.label)).toEqual([
      "Protect",
      "Trail #1",
      "Reduce",
      "Ajuste manual",
      "Stop",
    ]);
  });
});
