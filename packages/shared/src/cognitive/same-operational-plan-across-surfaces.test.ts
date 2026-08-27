/**
 * V1.24 — sameOperationalPlanAcrossSurfaces
 * Mismo instrumento → mismos niveles (stop/T1/T2/trail) desde study o position.
 * No E2E browser: contrato de builders compartidos.
 */

import { describe, expect, it } from "vitest";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
  buildPositionRouteLevels,
  isTrailingStopApplied,
  targetProgressHint,
  type DecisionJournalStudyViewV1,
} from "./index.js";
import type { PositionStateV1 } from "./position-state.js";

describe("sameOperationalPlanAcrossSurfaces", () => {
  const study = {
    hasOperationalPlan: true,
    tradePlanStatus: "ARMED",
    entry: 100,
    stop: 94,
    target1: 112,
    target2: 124,
    expectedRR: 2,
    initialRiskR: 1,
    direction: "long",
    symbol: "AAPL",
    instrumentId: "aapl",
  } as DecisionJournalStudyViewV1;

  it("study projection exposes the same levels Mercado/Hoy/Journal would show", () => {
    const plan = buildOperationalPlanFromStudy(study);
    expect(plan.hasPlan).toBe(true);
    expect(plan.entry).toBe(100);
    expect(plan.stopVigente).toBe(94);
    expect(plan.stopInicial).toBe(94);
    expect(plan.target1).toBe(112);
    expect(plan.target2).toBe(124);
    expect(plan.direction).toBe("long");
    expect(plan.trailingStopHint).toBeNull();
  });

  it("position projection keeps stop vigente / T1 / T2 coherent with route", () => {
    const ps = {
      status: "OPEN",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: 94,
      currentStop: 100,
      target1: 112,
      target2: 124,
      unrealizedR: 1.5,
      initialRisk: 6,
      mfeMae: { mfeR: 1.5, maeR: 0, source: "close_proxy" },
    } as PositionStateV1;

    const fromPs = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 112,
    });

    const aggregate = buildInvestmentPositionAggregate({
      position: {
        id: "p1",
        instrumentId: "aapl",
        symbol: "AAPL",
        quantity: 10,
        avgCost: 100,
        lastPrice: 112,
        marketValue: 1120,
        unrealizedPnl: 120,
        operational: {
          status: "OPEN",
          currentStop: 100,
          target1: 112,
          target2: 124,
          unrealizedR: 1.5,
        },
      } as never,
      study,
    });

    const fromAgg = buildOperationalPlanFromPosition({
      aggregate,
      markPrice: 112,
    });

    expect(fromPs.stopVigente).toBe(100);
    expect(fromPs.stopInicial).toBe(94);
    expect(fromPs.target1).toBe(112);
    expect(fromPs.target2).toBe(124);
    expect(fromAgg.stopVigente).toBe(fromPs.stopVigente);
    expect(fromAgg.target1).toBe(fromPs.target1);
    expect(fromAgg.target2).toBe(fromPs.target2);

    const levels = buildPositionRouteLevels(aggregate);
    const tp1 = levels.find((l) => l.label === "TP1");
    expect(tp1?.touched).toBe(true);
    expect(tp1?.managed).toBe(false);
    expect(targetProgressHint(tp1!.touched!, tp1!.managed!)).toBe(
      "● alcanzado · ○ pendiente de gestión",
    );
    // Must NOT look like a plain «gestionado» checkmark from price alone.
    expect(targetProgressHint(tp1!.touched!, tp1!.managed!)).not.toBe(
      "✓ gestionado",
    );
  });

  it("T1 managed only when target1AchievedAt is set", () => {
    const aggregate = buildInvestmentPositionAggregate({
      position: {
        id: "p1",
        instrumentId: "aapl",
        symbol: "AAPL",
        quantity: 5,
        avgCost: 100,
        lastPrice: 104,
        marketValue: 520,
        unrealizedPnl: 20,
        operational: {
          status: "PARTIAL",
          currentStop: 100,
          target1: 112,
          target2: 124,
          target1AchievedAt: "2026-08-27T10:00:00Z",
          unrealizedR: 0.5,
        },
      } as never,
      study,
    });
    const plan = buildOperationalPlanFromPosition({
      aggregate,
      markPrice: 104,
    });
    expect(plan.target1Touched).toBe(false);
    expect(plan.target1Managed).toBe(true);
    const tp1 = buildPositionRouteLevels(aggregate).find(
      (l) => l.label === "TP1",
    );
    expect(tp1?.managed).toBe(true);
    expect(targetProgressHint(tp1!.touched!, tp1!.managed!)).toBe(
      "✓ gestionado",
    );
  });

  it("trailing applied uses direction consistently", () => {
    expect(
      isTrailingStopApplied({
        direction: "long",
        stopVigente: 103,
        trailingStopHint: 101,
      }),
    ).toBe(true);
    expect(
      isTrailingStopApplied({
        direction: "short",
        stopVigente: 104,
        trailingStopHint: 106,
      }),
    ).toBe(true);
  });
});
