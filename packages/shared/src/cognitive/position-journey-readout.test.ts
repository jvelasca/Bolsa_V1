import { describe, expect, it } from "vitest";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";
import {
  buildPositionJourneyReadout,
  deriveCurrentProtectedMoney,
} from "./position-journey-readout.js";
import type { PositionOperationalViewV1 } from "./position-operational-view.js";

function g5View(): PositionOperationalViewV1 {
  return {
    positionId: "pos-g5",
    instrumentId: "NVDA",
    tradePlanId: "tp-g5",
    decisionId: "dec-g5",
    lineageCollapsed: false,
    operatingState: "TRAILING",
    primaryAction: "MANTENER",
    levels: {
      entry: 100,
      currentStop: 110,
      target1: 120,
      target2: 125,
      unrealizedR: 1.2,
    },
    t1: { status: "executed", at: "t1" },
    t2: { status: "executed", at: "t2" },
    stopHistory: [
      { label: "Initial", stop: 95, origin: "birth" },
      { label: "Trail #1", stop: 100, origin: "trail", delta: 5 },
      { label: "Trail #2", stop: 105, origin: "trail", delta: 5 },
      { label: "Trail #3", stop: 110, origin: "trail", delta: 5 },
    ],
    events: [],
    quantity: 10,
    remainingQuantity: 2,
    templateId: "moderate",
  };
}

describe("deriveCurrentProtectedMoney", () => {
  it("LONG: entry-stop * remaining", () => {
    expect(
      deriveCurrentProtectedMoney({
        entry: 100,
        currentStop: 110,
        remainingQuantity: 2,
        direction: "long",
      }),
    ).toBe(0);
    expect(
      deriveCurrentProtectedMoney({
        entry: 100,
        currentStop: 95,
        remainingQuantity: 10,
        direction: "long",
      }),
    ).toBe(50);
  });
});

describe("buildPositionJourneyReadout G5-like", () => {
  it("preserves Initial risk, keeps T2 in log after TRAIL, stage derived", () => {
    const posture = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    const journey = buildPositionJourneyReadout({
      view: g5View(),
      initialRisk: 50,
      initialStop: 95,
      realizedR: 3.5,
      direction: "long",
      templateId: "moderate",
      lifecycle: {
        positionId: "pos-g5",
        stage: "trailing",
        lineagePath: "trail",
        events: [
          { kind: "POSITION_OPENED" },
          { kind: "T1_EXECUTED" },
          { kind: "TRAIL_APPLIED" },
          { kind: "TRAIL_APPLIED" },
          { kind: "T2_EXECUTED" },
          { kind: "TRAIL_APPLIED" },
        ],
      },
      autoPosture: posture,
      killOn: false,
    });

    expect(journey.risk.initialRisk).toBe(50);
    expect(journey.risk.initialStop).toBe(95);
    expect(journey.t1.executed).toBe(true);
    expect(journey.t2.executed).toBe(true);
    expect(journey.t1.qtyFractionPct).toBe(30);
    expect(journey.t2.qtyFractionPct).toBe(30);
    expect(journey.trail.active).toBe(true);
    expect(journey.trail.activationEligible).toBe(true);
    expect(journey.trail.lastRatchet?.stop).toBe(110);
    expect(journey.logHasT2Executed).toBe(true);
    expect(journey.logHasTrailApplied).toBe(true);
    expect(journey.stageMachine).toBe("trailing");
    expect(journey.lineagePathLabel).toBe("trail");
    expect(journey.autoPosture?.statusBadge).toMatch(/ejecución off/);
    expect(journey.remainingQuantity).toBe(2);
    expect(journey.primaryAction).toBe("MANTENER");
  });
});
