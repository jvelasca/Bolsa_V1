import { describe, expect, it } from "vitest";
import {
  buildPositionOperationalView,
  buildStopHistory,
} from "./position-operational-view.js";
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
