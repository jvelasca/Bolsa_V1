/**
 * G-OPERATOR-05 / V2.35 — UI Truth matrix + birth Planificado.
 * Same stop / T1 / T2 / remaining / NEXT / protection phase across surfaces.
 * Birth with structural stop → Planificado + MANTENER (not emergency).
 */

import { describe, expect, it } from "vitest";
import {
  buildOperatorDecision,
  buildOperatorJourney2Surfaces,
  operatorJourney2LevelsEqual,
  type OperatorCabinTruthV1,
} from "./operator-cabin-view.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";
import { resolvePositionOperatingState } from "./operational-context.js";
import { buildPositionOperationalView } from "./position-operational-view.js";
import type { PositionStateV1 } from "./position-state.js";

function birthJourney(
  overrides: Partial<PositionJourneyReadoutV1> = {},
): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: 400,
      initialStop: 176.8,
      currentProtected: null,
      realizedR: null,
      unrealizedR: 0.4,
      remainingQuantity: 62,
    },
    t1: {
      trigger: 195,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    t2: {
      trigger: 205,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    trail: {
      active: false,
      activationEligible: false,
      currentStop: 176.8,
      lastRatchet: null,
      trailWidth: null,
    },
    remainingQuantity: 62,
    primaryAction: "MANTENER",
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
    ...overrides,
  };
}

function birthPositionState(): PositionStateV1 {
  return {
    positionId: "pos-birth",
    decisionId: "dec-1",
    tradePlanId: "tp-1",
    instrumentId: "inst-aapl",
    direction: "long",
    status: "OPEN",
    plannedEntry: 184.2,
    actualEntry: 184.2,
    initialStop: 176.8,
    currentStop: 176.8,
    target1: 195,
    target2: 205,
    target1AchievedAt: null,
    target2AchievedAt: null,
    target1Leg: { status: "pending" },
    target2Leg: { status: "pending" },
    quantity: 62,
    remainingQuantity: 62,
    initialRisk: 400,
    realizedR: 0,
    unrealizedR: 0.4,
    mfeMae: { mfeR: null, maeR: null, source: "none" },
    thesisHealth: { status: "none" },
    protectionState: { status: "none" },
    trailing: { status: "none" },
    exitStatus: "none",
    createdAt: "2026-09-04T10:00:00.000Z",
    updatedAt: "2026-09-04T10:00:00.000Z",
    revisions: [],
  };
}

describe("G-OPERATOR-05 V2.35 UI Truth", () => {
  it("birth fill → operatingState PROTECTED (not OPEN_UNPROTECTED / PROTECT_REQUIRED)", () => {
    expect(
      resolvePositionOperatingState({
        positionStatus: "OPEN",
        quantity: 62,
        remainingQuantity: 62,
        currentStop: 176.8,
        initialStop: 176.8,
      }),
    ).toBe("PROTECTED");
    const view = buildPositionOperationalView({
      position: birthPositionState(),
    });
    expect(view.operatingState).toBe("PROTECTED");
    expect(view.operatingState).not.toBe("PROTECT_REQUIRED");
    expect(view.operatingState).not.toBe("OPEN_UNPROTECTED");
  });

  it("OPEN birth → MANTENER · Planificado · same levels on all Journey 2 surfaces", () => {
    const truth: OperatorCabinTruthV1 = {
      kind: "position",
      primaryAction: "MANTENER",
      journey: birthJourney(),
      currentStop: 176.8,
      plannedStop: 176.8,
      birthQuantity: 62,
      templateId: "moderate",
    };
    const decision = buildOperatorDecision(truth);
    expect(decision.currentAction.title).toBe("MANTENER");
    expect(decision.protection.phase).toBe("planned");
    expect(decision.protection.kind).toBe("none");
    expect(decision.currentAction.subtitle).not.toMatch(/emergencia/i);

    const surfaces = buildOperatorJourney2Surfaces(truth, {
      birthQuantity: 62,
      templateId: "moderate",
    });
    expect(operatorJourney2LevelsEqual(surfaces.mercado, surfaces.chart)).toBe(
      true,
    );
    expect(operatorJourney2LevelsEqual(surfaces.mercado, surfaces.auto)).toBe(
      true,
    );
    expect(operatorJourney2LevelsEqual(surfaces.mercado, surfaces.plan)).toBe(
      true,
    );
    expect(
      operatorJourney2LevelsEqual(surfaces.mercado, surfaces.journal),
    ).toBe(true);
    expect(operatorJourney2LevelsEqual(surfaces.mercado, surfaces.risk)).toBe(
      true,
    );
    expect(surfaces.mercado.stop).toBe(176.8);
    expect(surfaces.mercado.t1).toBe(195);
    expect(surfaces.mercado.t2).toBe(205);
    expect(surfaces.mercado.remainingPct).toBe(100);
    expect(surfaces.decision.protection.phase).toBe("planned");
  });

  it("PROTECTED after revision → technical · surfaces equal", () => {
    const j = birthJourney({
      trail: {
        active: false,
        activationEligible: false,
        currentStop: 176.8,
        lastRatchet: null,
        trailWidth: null,
      },
    });
    const surfaces = buildOperatorJourney2Surfaces(
      {
        kind: "position",
        primaryAction: "MANTENER",
        journey: j,
        currentStop: 176.8,
        plannedStop: 176.8,
        hasProtectRevision: true,
        birthQuantity: 62,
        templateId: "moderate",
      },
      { birthQuantity: 62, templateId: "moderate" },
    );
    expect(surfaces.decision.protection.kind).toBe("technical");
    expect(surfaces.decision.protection.phase).toBe("protected");
    expect(
      operatorJourney2LevelsEqual(surfaces.mercado, surfaces.hoy, {
        ignoreNextAction: true,
      }),
    ).toBe(true);
    expect(operatorJourney2LevelsEqual(surfaces.mercado, surfaces.chart)).toBe(
      true,
    );
  });

  it("T1 → TRAIL → remaining drops identically on AUTO / Plan / Journal", () => {
    const j = birthJourney({
      remainingQuantity: 43,
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 180,
        lastRatchet: null,
        trailWidth: "atr_1_5",
      },
      logHasTrailApplied: true,
    });
    const surfaces = buildOperatorJourney2Surfaces(
      {
        kind: "position",
        primaryAction: "MANTENER",
        journey: j,
        currentStop: 180,
        plannedStop: 176.8,
        hasTrailRevision: true,
        birthQuantity: 62,
        templateId: "moderate",
      },
      { birthQuantity: 62, templateId: "moderate" },
    );
    expect(surfaces.mercado.remainingPct).toBeCloseTo(69.4, 0);
    expect(surfaces.auto.remainingPct).toBeCloseTo(69.4, 0);
    expect(surfaces.plan.remainingPct).toBeCloseTo(69.4, 0);
    expect(surfaces.journal.remainingPct).toBeCloseTo(69.4, 0);
    expect(surfaces.chart.stop).toBe(180);
    expect(operatorJourney2LevelsEqual(surfaces.auto, surfaces.journal)).toBe(
      true,
    );
  });
});
