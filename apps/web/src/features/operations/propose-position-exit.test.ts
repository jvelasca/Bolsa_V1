import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  buildPositionExitPayload,
  evaluateProtectStopOverride,
  positionShowsProtectHint,
  resolveProtectSuggestedStop,
} from "@/features/operations/propose-position-exit";
import type { PositionDto, ProtectPlanV1 } from "@bolsa/shared";

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: "semi" }),
  demoBookAllowsEnqueueConfirm: () => true,
}));

function position(partial: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-1",
    symbol: "TEST",
    name: "Test SA",
    quantity: 10,
    avgCost: 100,
    lastPrice: 105,
    marketValue: 1050,
    unrealizedPnl: 50,
    unrealizedPnlPct: 0.05,
    operational: {
      status: "OPEN",
      direction: "long",
      currentStop: 95,
      target1: 110,
      target2: 120,
      tradePlanId: "dec-1",
    },
    ...partial,
  };
}

describe("buildPositionExitPayload", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
    });
  });

  it("builds exit_hint with full quantity", () => {
    const payload = buildPositionExitPayload({
      position: position(),
      accountId: "acc-1",
      intent: "exit_hint",
    });
    expect(payload.action).toBe("exit_hint");
    expect(payload.suggestedQuantity).toBe(10);
    expect(payload.decisionId).toBe("dec-1");
    expect(payload.source).toBe("operativa");
    expect(payload.decisionPackage).toMatchObject({
      operativaIntent: "exit_hint",
      exitSource: "manual",
      plannedQty: 10,
    });
  });

  it("V1.32 — event exitSource when ExitPlan TRIGGERED", () => {
    const payload = buildPositionExitPayload({
      position: position({
        operational: {
          status: "OPEN",
          direction: "long",
          currentStop: 95,
          target1: 110,
          target2: 120,
          tradePlanId: "dec-1",
          exitPlan: {
            status: "TRIGGERED",
            suggestedAction: "reduce",
            primaryReason: "TARGET_1",
            suggestedQty: 3,
          },
        },
      }),
      accountId: "acc-1",
      intent: "reduce",
    });
    expect(payload.decisionPackage).toMatchObject({
      operativaIntent: "reduce",
      exitSource: "event",
      plannedQty: 3,
    });
  });

  it("builds reduce with half quantity rounded up when no policy event", () => {
    const payload = buildPositionExitPayload({
      position: position({ quantity: 7 }),
      accountId: "acc-1",
      intent: "reduce",
    });
    expect(payload.action).toBe("reduce");
    expect(payload.suggestedQuantity).toBe(4);
  });

  it("V1.29 — reduce uses ExitPolicy suggestedQty from exitPlan", () => {
    const payload = buildPositionExitPayload({
      position: position({
        quantity: 10,
        operational: {
          status: "OPEN",
          direction: "long",
          currentStop: 95,
          target1: 110,
          target2: 120,
          tradePlanId: "dec-1",
          exitPlan: {
            status: "TRIGGERED",
            suggestedAction: "reduce",
            primaryReason: "TARGET_1",
            suggestedQty: 3,
            policyTemplateId: "moderate",
          },
        },
      }),
      accountId: "acc-1",
      intent: "reduce",
    });
    expect(payload.suggestedQuantity).toBe(3);
  });

  it("V1.29 — reduce from TARGET_1 + conservative without suggestedQty", () => {
    const payload = buildPositionExitPayload({
      position: position({
        quantity: 10,
        operational: {
          status: "OPEN",
          direction: "long",
          currentStop: 95,
          target1: 110,
          target2: 120,
          tradePlanId: "dec-1",
          exitPlan: {
            status: "TRIGGERED",
            suggestedAction: "reduce",
            primaryReason: "TARGET_1",
            policyTemplateId: "conservative",
          },
        },
      }),
      accountId: "acc-1",
      intent: "reduce",
    });
    // conservative t1ReduceFraction 0.5 → 5
    expect(payload.suggestedQuantity).toBe(5);
  });

  it("V1.29 — protect clamps trail that would worsen long stop", () => {
    const payload = buildPositionExitPayload({
      position: position({
        operational: {
          status: "OPEN",
          direction: "long",
          currentStop: 100,
          target1: 110,
          target2: 120,
          tradePlanId: "dec-1",
          exitPlan: {
            status: "ARMED",
            suggestedAction: "protect",
            primaryReason: "TRAIL",
            suggestedStop: 95,
          },
        },
      }),
      accountId: "acc-1",
      intent: "protect",
    });
    expect(payload.suggestedPrice).toBe(100);
    expect(payload.decisionPackage).toMatchObject({
      operativaIntent: "protect",
      suggestedStop: 100,
      stopOverrideRequired: false,
    });
  });

  it("V1.29 — positionShowsProtectHint false when clamp equals current", () => {
    expect(
      positionShowsProtectHint(
        position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: 100,
            target1: 110,
            target2: 120,
            tradePlanId: "dec-1",
            exitPlan: {
              status: "ARMED",
              suggestedAction: "protect",
              primaryReason: "TRAIL",
              suggestedStop: 95,
            },
          },
        }),
      ),
    ).toBe(false);
  });

  it("V1.34 — suggestedStopOverride + allowPendingOverride encola stop del chart", () => {
    const improve = buildPositionExitPayload({
      position: position(),
      accountId: "acc-1",
      intent: "protect",
      suggestedStopOverride: 96,
      allowPendingOverride: true,
    });
    expect(improve.decisionPackage).toMatchObject({
      operativaIntent: "protect",
      suggestedStop: 96,
      stopOverrideRequired: false,
    });

    const worsen = buildPositionExitPayload({
      position: position(),
      accountId: "acc-1",
      intent: "protect",
      suggestedStopOverride: 90,
      allowPendingOverride: true,
    });
    expect(worsen.decisionPackage).toMatchObject({
      suggestedStop: 90,
      stopOverrideRequired: true,
    });
  });

  it("rejects without operational plan", () => {
    expect(() =>
      buildPositionExitPayload({
        position: position({ operational: null }),
        accountId: "acc-1",
        intent: "exit_hint",
      }),
    ).toThrow(/sin plan persistido/i);
  });

  it("builds protect with suggested stop from protectPlan", () => {
    const protectPlan: ProtectPlanV1 = {
      status: "protect_hint",
      target1: 110,
      suggestedProtectStop: 100,
      rMultiple: 1,
      why: ["mfe_ge_1r"],
    };
    const payload = buildPositionExitPayload({
      position: position(),
      accountId: "acc-1",
      intent: "protect",
      protectPlan,
    });
    expect(payload.action).toBe("wait");
    expect(payload.suggestedPrice).toBe(100);
    expect(payload.decisionPackage).toMatchObject({
      operativaIntent: "protect",
      suggestedStop: 100,
    });
  });

  it("positionShowsProtectHint from exitPlan or protectPlan", () => {
    expect(
      positionShowsProtectHint(
        position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: 95,
            target1: 110,
            target2: 120,
            tradePlanId: "dec-1",
            exitPlan: {
              status: "ARMED",
              suggestedAction: "protect",
              primaryReason: "TRAIL",
              suggestedStop: 100,
            },
          },
        }),
      ),
    ).toBe(true);
    expect(
      positionShowsProtectHint(position(), {
        status: "protect_hint",
        target1: 110,
        suggestedProtectStop: 100,
        rMultiple: 1,
        why: ["mfe_ge_1r"],
      }),
    ).toBe(true);
  });

  it("evaluateProtectStopOverride flags worsening long stop", () => {
    const ok = evaluateProtectStopOverride({
      direction: "long",
      currentStop: 95,
      suggestedStop: 100,
    });
    expect(ok.overrideRequired).toBe(false);

    const bad = evaluateProtectStopOverride({
      direction: "long",
      currentStop: 100,
      suggestedStop: 95,
    });
    expect(bad.overrideRequired).toBe(true);
    expect(
      evaluateProtectStopOverride({
        direction: "long",
        currentStop: 100,
        suggestedStop: 95,
        overrideReason: "trail manual",
      }).allowed,
    ).toBe(true);
  });

  it("resolveProtectSuggestedStop prefers exitPlan", () => {
    const stop = resolveProtectSuggestedStop(
      position({
        operational: {
          status: "OPEN",
          direction: "long",
          currentStop: 95,
          target1: 110,
          target2: 120,
          tradePlanId: "dec-1",
          exitPlan: {
            status: "ARMED",
            suggestedAction: "protect",
            primaryReason: null,
            suggestedStop: 102,
          },
        },
      }),
      {
        status: "protect_hint",
        target1: 110,
        suggestedProtectStop: 100,
        rMultiple: 1,
        why: ["mfe_ge_1r"],
      },
    );
    expect(stop).toBe(102);
  });
});
