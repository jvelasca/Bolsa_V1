/**
 * V1.37 — misma posición → misma OperationalTruth en Mercado / Hoy / Journal / Operaciones.
 * Contrato de builders: no E2E browser.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import { mapMesaNextAction } from "./mesa-next-action.js";
import {
  buildOperationalTruth,
  formatExecutionHintCopy,
  mesaNextActionFromDecision,
  openPositionNeedsAction,
  operationalTruthSurfaceSnapshot,
} from "./operational-truth.js";

const ASOF = "2026-08-31T08:15:00.000Z";

function aaplOpen(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p-aapl",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 1020,
    unrealizedPnl: 20,
    unrealizedPnlPct: 2,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-aapl",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 105,
      target2: 110,
      unrealizedR: 0.4,
    },
    ...overrides,
  };
}

function fourSurfaces(
  position: PositionDto,
  recon?: string | null,
  extra: { orderPending?: boolean } = {},
) {
  const input = {
    position,
    portfolioReconStatus: recon,
    asOf: ASOF,
    ...extra,
  };
  const mercado = buildOperationalTruth(input);
  const hoy = buildOperationalTruth(input);
  const journal = buildOperationalTruth(input);
  const operaciones = buildOperationalTruth(input);
  return { mercado, hoy, journal, operaciones };
}

describe("sameOperationalTruthAcrossSurfaces V1.37", () => {
  it("HOLD + ACTIVE + T1 is identical on Mercado/Hoy/Journal/Operaciones", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces(
      aaplOpen(),
      "ok",
    );
    expect(mercado).not.toBeNull();
    const snap = operationalTruthSurfaceSnapshot(mercado!);
    expect(snap).toEqual({
      action: "HOLD",
      ctaLabel: "Mantener",
      ctaKind: "maintain",
      protection: "ACTIVE",
      nextEvent: "T1",
      reconHealth: "CLEAN",
      asOf: ASOF,
      stopOperativo: 95,
      target1: 105,
      target2: 110,
      executionHint: "none",
    });
    expect(operationalTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
    expect(mesaNextActionFromDecision(mercado!.decision).kind).toBe("maintain");
    expect(mesaNextActionFromDecision(mercado!.decision).label).toBe(
      "Mantener",
    );
    expect(mercado!.primaryCta).toEqual({
      kind: "maintain",
      label: "Mantener",
    });
    expect(openPositionNeedsAction(mercado!.decision)).toBe(false);
  });

  it("T1 reached → TAKE_PROFIT on every surface (not HOLD)", () => {
    const pos = aaplOpen({
      lastPrice: 105,
      marketValue: 1050,
      unrealizedPnl: 50,
    });
    const { mercado, hoy, journal, operaciones } = fourSurfaces(pos);
    const snap = operationalTruthSurfaceSnapshot(mercado!);
    expect(snap.action).toBe("TAKE_PROFIT");
    expect(snap.ctaLabel).toBe("Reducir");
    expect(snap.ctaKind).toBe("reduce");
    expect(snap.nextEvent).toBe("T1");
    expect(snap.executionHint).toBe("recommended_not_executed");
    expect(operationalTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
    expect(mesaNextActionFromDecision(mercado!.decision).kind).toBe("reduce");
    expect(openPositionNeedsAction(mercado!.decision)).toBe(true);
    expect(formatExecutionHintCopy(mercado!)).toMatch(/aún no ejecutada/i);
  });

  it("recon drift → REVIEW + CRITICAL + RECONCILIATION on every surface", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces(
      aaplOpen(),
      "drift",
    );
    const snap = operationalTruthSurfaceSnapshot(mercado!);
    expect(snap).toMatchObject({
      action: "REVIEW",
      ctaLabel: "Revisar",
      ctaKind: "review",
      reconHealth: "CRITICAL",
      nextEvent: "RECONCILIATION",
      asOf: ASOF,
      executionHint: "none",
    });
    expect(operationalTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(operationalTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
    expect(mesaNextActionFromDecision(mercado!.decision).kind).toBe("review");
  });

  it("protect_hint thin cannot force PROTEGER when PositionDecision is HOLD", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen(),
      asOf: ASOF,
    });
    expect(truth?.decision.action).toBe("HOLD");
    const legacyHoy = mapMesaNextAction({
      hasOpenPosition: true,
      protectPlan: { status: "protect_hint" },
    });
    expect(legacyHoy.kind).toBe("protect");
    expect(mesaNextActionFromDecision(truth!.decision).kind).toBe("maintain");
    expect(mesaNextActionFromDecision(truth!.decision).kind).not.toBe(
      legacyHoy.kind,
    );
  });

  it("missing recon status is CLEAN, not ATTENTION", () => {
    const truth = buildOperationalTruth({ position: aaplOpen(), asOf: ASOF });
    expect(truth?.reconHealth).toBe("CLEAN");
    expect(truth?.decision.action).toBe("HOLD");
  });

  it("orderPending suppresses execution hint", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const pending = buildOperationalTruth({
      position: pos,
      asOf: ASOF,
      orderPending: true,
    });
    expect(pending?.executionHint).toBe("none");
    expect(formatExecutionHintCopy(pending!)).toBeNull();
  });

  it("same orderPending → same executionHint on Mercado/Hoy/Journal/Operaciones", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const { mercado, hoy, journal, operaciones } = fourSurfaces(pos, "ok", {
      orderPending: true,
    });
    expect(mercado?.executionHint).toBe("none");
    expect(hoy?.executionHint).toBe(mercado?.executionHint);
    expect(journal?.executionHint).toBe(mercado?.executionHint);
    expect(operaciones?.executionHint).toBe(mercado?.executionHint);
    expect(formatExecutionHintCopy(mercado!)).toBeNull();
    const open = fourSurfaces(pos, "ok", { orderPending: false });
    expect(open.mercado?.executionHint).toBe("recommended_not_executed");
    expect(open.hoy?.executionHint).toBe(open.mercado?.executionHint);
    expect(open.journal?.executionHint).toBe(open.mercado?.executionHint);
    expect(open.operaciones?.executionHint).toBe(open.mercado?.executionHint);
  });
});
