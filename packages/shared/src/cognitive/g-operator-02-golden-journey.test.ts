/**
 * G-OPERATOR-02 — full operator journey (V2.23) + Journey 2 surfaces (V2.32).
 * ESTUDIO → PREPARADA → TRIGGER → ENTRY → PROTECTED → T1 → TRAIL → TRAIL → T2 → TRAIL → EXIT
 * Same OperatorDecision on Mercado / Hoy CTA / AUTO / remaining.
 * V2.32 — same stop / T1 / T2 / remaining / next action on
 * Mercado · Gráfico · NEXT · Risk · Plan · AUTO · Hoy · Journal.
 * Projection-only — not a second FSM.
 */

import { describe, expect, it } from "vitest";
import {
  buildOperatorAutoPlanPreview,
  buildOperatorDecision,
  buildOperatorJourney2Surfaces,
  buildOperatorMissionSteps,
  mesaNextActionFromOperatorDecision,
  operatorJourney2LevelsEqual,
  resolveOperatorNextAction,
  type OperatorJourney2LevelsV1,
  type OperatorJourney2SurfacesV1,
} from "./operator-cabin-view.js";
import type { EntryOperatingTruthV1 } from "./entry-operating-truth.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";

function entryTruth(
  phase: EntryOperatingTruthV1["phase"],
  overrides: Partial<EntryOperatingTruthV1> = {},
): EntryOperatingTruthV1 {
  return {
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    asOf: "2026-09-04T10:00:00.000Z",
    phase,
    phaseLabel: phase,
    triggerLabel: phase === "preparada" ? "Pendiente" : "Disparado",
    phrase: "test",
    primaryCta: {
      kind:
        phase === "preparada"
          ? "prepare"
          : phase === "confirmada"
            ? "view_operations"
            : "review_confirm",
      label:
        phase === "preparada"
          ? "Preparar operación"
          : phase === "confirmada"
            ? "Ver operaciones"
            : "Revisar y confirmar",
    },
    plan: {
      phase: phase === "preparada" ? "prepared" : "triggered",
      phaseLabel: phase === "preparada" ? "Preparada" : "Disparada",
      direction: "long",
      entry: 184.2,
      stopVigente: 176.8,
      stopInicial: 176.8,
      target1: 195,
      target2: 205,
      target1Reached: false,
      target2Reached: false,
      target1Touched: false,
      target1Managed: false,
      target2Touched: false,
      target2Managed: false,
      expectedRR: 1.46,
      riskR: 0.8,
      currentPrice: 183.5,
      unrealizedR: null,
      trailingActive: false,
      trailingPeakMfeR: null,
      trailingPeakPrice: null,
      trailingStopHint: null,
      trailingDistanceR: null,
      exitAuthorityHint: null,
      hasPlan: true,
      emptyCopy: "",
    },
    sizing: {
      quantity: 62,
      riskAmount: 400,
      expectedRR: 1.46,
      riskR: 0.8,
      positionValue: 11420,
    },
    entriesBlocked: false,
    gateStatus: null,
    expiryLabel: "06 SEP 18:00",
    ...overrides,
  };
}

function journey(
  partial: Partial<PositionJourneyReadoutV1> & {
    primaryAction: PositionJourneyReadoutV1["primaryAction"];
  },
): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: 400,
      initialStop: 176.8,
      currentProtected: 50,
      realizedR: 0,
      unrealizedR: 0.2,
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
      trailWidth: "medium",
    },
    remainingQuantity: 62,
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
    ...partial,
  };
}

function sameAction(
  title: string,
  truth: Parameters<typeof buildOperatorDecision>[0],
) {
  const decision = buildOperatorDecision(truth);
  const mercado = resolveOperatorNextAction(truth);
  const hoy = mesaNextActionFromOperatorDecision(decision);
  expect(mercado.title).toBe(title);
  expect(decision.currentAction.title).toBe(title);
  expect(hoy.label.toUpperCase()).toBe(
    title === "ESPERAR TRIGGER"
      ? "VER TESIS"
      : title === "ENTRADA LISTA"
        ? "REVISAR PROPUESTA"
        : title,
  );
  return { decision, mercado, hoy };
}

function expectContractualSurfaces(
  surfaces: OperatorJourney2SurfacesV1,
  expected: Partial<OperatorJourney2LevelsV1> & { nextAction: string },
) {
  const { mercado, next, risk, plan, auto, hoy, journal, chart } = surfaces;
  expect(mercado.nextAction).toBe(expected.nextAction);
  expect(mercado.stop).toBe(expected.stop ?? null);
  expect(mercado.t1).toBe(expected.t1 ?? null);
  expect(mercado.t2).toBe(expected.t2 ?? null);
  if (expected.remainingPct != null) {
    expect(mercado.remainingPct).toBeCloseTo(expected.remainingPct, 0);
  }
  if (expected.t1Pct != null) expect(mercado.t1Pct).toBe(expected.t1Pct);
  if (expected.t2Pct != null) expect(mercado.t2Pct).toBe(expected.t2Pct);

  expect(operatorJourney2LevelsEqual(mercado, next)).toBe(true);
  expect(operatorJourney2LevelsEqual(mercado, journal)).toBe(true);
  expect(operatorJourney2LevelsEqual(mercado, chart)).toBe(true);
  expect(
    operatorJourney2LevelsEqual(mercado, risk, { ignoreNextAction: true }),
  ).toBe(true);
  expect(
    operatorJourney2LevelsEqual(mercado, plan, { ignoreNextAction: true }),
  ).toBe(true);
  expect(
    operatorJourney2LevelsEqual(mercado, auto, { ignoreNextAction: true }),
  ).toBe(true);
  expect(
    operatorJourney2LevelsEqual(mercado, hoy, { ignoreNextAction: true }),
  ).toBe(true);
  expect(auto.nextAction).toBe(mercado.nextAction);
}

describe("G-OPERATOR-02 full journey — one OperatorDecision", () => {
  it("ESTUDIO — VIGILAR on cockpit, not COMPRAR", () => {
    const next = resolveOperatorNextAction({
      kind: "cockpit_phase",
      phase: "vigilar",
    });
    expect(next.title).toBe("VIGILAR");
    expect(next.title).not.toMatch(/COMPRAR|BUY/i);
    expect(next.ctaHint).not.toMatch(/COMPRAR/i);
  });

  it("PREPARADA — ESPERAR TRIGGER + condition + expires", () => {
    const { mercado } = sameAction("ESPERAR TRIGGER", {
      kind: "entry",
      truth: entryTruth("preparada"),
    });
    expect(mercado.condition).toMatch(/cierre > 184\.20/i);
    expect(mercado.expires).toMatch(/06 SEP/);
    expect(mercado.reasons?.some((r) => r.id === "setup" && r.ok)).toBe(true);
    expect(mercado.nextChange).toMatch(/cierre >/);
  });

  it("TRIGGER / ENTRY — ENTRADA LISTA", () => {
    sameAction("ENTRADA LISTA", {
      kind: "entry",
      truth: entryTruth("disparada"),
    });
  });

  it("PROTECTED — MANTENER + technical protection + AUTO remaining 100%", () => {
    const j = journey({ primaryAction: "MANTENER" });
    const { decision } = sameAction("MANTENER", {
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      birthQuantity: 62,
      hasProtectRevision: true,
    });
    expect(decision.protection.kind).toBe("technical");
    expect(decision.remaining?.remainingPct).toBe(100);
    const preview = buildOperatorAutoPlanPreview({
      journey: j,
      templateId: "moderate",
      nextAction: decision.currentAction,
      birthQuantity: 62,
    });
    expect(preview.headline).toBe("AUTO HARÁ ESTO");
    expect(preview.t1Pct).toBe(30);
    expect(preview.remainingPct).toBe(100);
    expect(
      buildOperatorMissionSteps(j, { birthQuantity: 62 }).some(
        (s) => s.id === "remaining",
      ),
    ).toBe(true);
  });

  it("T1 then TRAIL then TRAIL — remaining drops, trail active", () => {
    const afterT1 = journey({
      primaryAction: "MANTENER",
      remainingQuantity: 43,
      risk: {
        initialRisk: 400,
        initialStop: 176.8,
        currentProtected: 20,
        realizedR: 1,
        unrealizedR: 0.5,
        remainingQuantity: 43,
      },
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 191.2,
        lastRatchet: { stop: 191.2, origin: "trail", label: "Trail" },
        trailWidth: "medium",
      },
    });
    const firstTrail = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: afterT1,
      birthQuantity: 62,
    });
    expect(firstTrail.currentAction.title).toBe("MANTENER");
    expect(firstTrail.remaining?.remainingPct).toBeCloseTo(69.4, 0);
    expect(firstTrail.plan.trailActive).toBe(true);

    const secondTrail = journey({
      ...afterT1,
      trail: {
        ...afterT1.trail,
        currentStop: 193.5,
        lastRatchet: { stop: 193.5, origin: "trail", label: "Trail" },
      },
    });
    const again = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: secondTrail,
      birthQuantity: 62,
    });
    expect(again.currentAction.title).toBe("MANTENER");
    expect(again.protection.kind).toBe("technical");
    expect(mesaNextActionFromOperatorDecision(again).kind).toBe("maintain");
  });

  it("T2 then TRAIL then EXIT — Hoy CTA matches Mercado", () => {
    const afterT2 = journey({
      primaryAction: "MANTENER",
      remainingQuantity: 31,
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      t2: {
        trigger: 205,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 200,
        lastRatchet: { stop: 200, origin: "trail", label: "Trail" },
        trailWidth: "medium",
      },
    });
    const trail = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: afterT2,
      birthQuantity: 62,
    });
    expect(trail.remaining?.remainingPct).toBeCloseTo(50, 0);
    const exit = sameAction("SALIR", {
      kind: "position",
      primaryAction: "SALIR",
      journey: afterT2,
      closed: true,
      birthQuantity: 62,
    });
    expect(exit.decision.remaining?.remainingPct).toBe(0);
    expect(exit.hoy.kind).toBe("exit");
  });
});

describe("G-OPERATOR-02 Journey 2 — contractual surfaces V2.32", () => {
  it("ESTUDIO → VIGILAR — empty levels, no BUY", () => {
    const surfaces = buildOperatorJourney2Surfaces({
      kind: "cockpit_phase",
      phase: "vigilar",
    });
    expectContractualSurfaces(surfaces, {
      nextAction: "VIGILAR",
      stop: null,
      t1: null,
      t2: null,
      remainingPct: null,
    });
    expect(JSON.stringify(surfaces.mercado)).not.toMatch(/COMPRAR|BUY/i);
  });

  it("TRIGGER — ESPERAR TRIGGER · stop/T1/T2 same on Mercado·Risk·Plan·Chart·Journal", () => {
    const surfaces = buildOperatorJourney2Surfaces({
      kind: "entry",
      truth: entryTruth("preparada"),
    });
    expectContractualSurfaces(surfaces, {
      nextAction: "ESPERAR TRIGGER",
      stop: 176.8,
      t1: 195,
      t2: 205,
      remainingPct: 100,
      t1Pct: 30,
      t2Pct: 30,
    });
    expect(surfaces.hoy.nextAction).toBe("VER TESIS");
  });

  it("ENTRADA — ENTRADA LISTA contractual levels", () => {
    const surfaces = buildOperatorJourney2Surfaces({
      kind: "entry",
      truth: entryTruth("disparada"),
    });
    expectContractualSurfaces(surfaces, {
      nextAction: "ENTRADA LISTA",
      stop: 176.8,
      t1: 195,
      t2: 205,
      remainingPct: 100,
      t1Pct: 30,
      t2Pct: 30,
    });
    expect(surfaces.hoy.nextAction).toBe("REVISAR PROPUESTA");
  });

  it("PROTECCIÓN — MANTENER · 30/30 · remaining 100% on AUTO=Plan=Journal", () => {
    const j = journey({ primaryAction: "MANTENER" });
    const surfaces = buildOperatorJourney2Surfaces(
      {
        kind: "position",
        primaryAction: "MANTENER",
        journey: j,
        birthQuantity: 62,
        templateId: "moderate",
        hasProtectRevision: true,
      },
      { birthQuantity: 62, templateId: "moderate" },
    );
    expectContractualSurfaces(surfaces, {
      nextAction: "MANTENER",
      stop: 176.8,
      t1: 195,
      t2: 205,
      remainingPct: 100,
      t1Pct: 30,
      t2Pct: 30,
    });
    expect(surfaces.decision.protection.kind).toBe("technical");
    expect(surfaces.auto.t1Pct).not.toBe(25);
    expect(surfaces.plan.t1Pct).not.toBe(25);
  });

  it("T1 → TRAILING — stop/T1/T2/remaining identical across surfaces", () => {
    const afterT1 = journey({
      primaryAction: "MANTENER",
      remainingQuantity: 43,
      risk: {
        initialRisk: 400,
        initialStop: 176.8,
        currentProtected: 20,
        realizedR: 1,
        unrealizedR: 0.5,
        remainingQuantity: 43,
      },
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 191.2,
        lastRatchet: { stop: 191.2, origin: "trail", label: "Trail" },
        trailWidth: "medium",
      },
    });
    const surfaces = buildOperatorJourney2Surfaces(
      {
        kind: "position",
        primaryAction: "MANTENER",
        journey: afterT1,
        birthQuantity: 62,
        templateId: "moderate",
      },
      { birthQuantity: 62, templateId: "moderate" },
    );
    expectContractualSurfaces(surfaces, {
      nextAction: "MANTENER",
      stop: 191.2,
      t1: 195,
      t2: 205,
      remainingPct: 69,
      t1Pct: 30,
      t2Pct: 30,
    });
  });

  it("T2 → TRAILING → EXIT — SALIR · remaining 0 · Hoy=exit", () => {
    const afterT2 = journey({
      primaryAction: "SALIR",
      remainingQuantity: 31,
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      t2: {
        trigger: 205,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 200,
        lastRatchet: { stop: 200, origin: "trail", label: "Trail" },
        trailWidth: "medium",
      },
    });
    const surfaces = buildOperatorJourney2Surfaces(
      {
        kind: "position",
        primaryAction: "SALIR",
        journey: afterT2,
        closed: true,
        birthQuantity: 62,
        templateId: "moderate",
      },
      { birthQuantity: 62, templateId: "moderate" },
    );
    expectContractualSurfaces(surfaces, {
      nextAction: "SALIR",
      stop: 200,
      t1: 195,
      t2: 205,
      remainingPct: 0,
      t1Pct: 30,
      t2Pct: 30,
    });
    expect(mesaNextActionFromOperatorDecision(surfaces.decision).kind).toBe(
      "exit",
    );
    expect(surfaces.hoy.nextAction).toBe("SALIR");
  });
});
