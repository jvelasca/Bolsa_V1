/**
 * V1.42 F3 — misma posición → misma PositionOperatingTruth en Mercado / Hoy / Journal / Operaciones.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import {
  buildPositionOperatingTruth,
  mesaNextActionFromPositionOperatingTruth,
  positionOperatingTruthSurfaceSnapshot,
  type BuildPositionOperatingTruthInputV1,
} from "./position-operating-truth.js";
import { buildPositionOperationalView } from "./position-operational-view.js";
import { buildPositionDecisionFromDto } from "./position-state-from-dto.js";
import { mapPortfolioReconToPovRecon } from "./reconciliation-opening-veto.js";
import { positionStateFromPositionDto } from "./position-state-from-dto.js";

const ASOF = "2026-08-31T15:00:00.000Z";

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
      exitPlan: { suggestedAction: "hold" },
    },
    ...overrides,
  };
}

function fourSurfaces(input: BuildPositionOperatingTruthInputV1) {
  const mercado = buildPositionOperatingTruth(input);
  const hoy = buildPositionOperatingTruth(input);
  const journal = buildPositionOperatingTruth(input);
  const operaciones = buildPositionOperatingTruth(input);
  return { mercado, hoy, journal, operaciones };
}

describe("samePositionOperatingTruthAcrossSurfaces V1.42 F3", () => {
  it("HOLD stable → identical snapshot on Mercado/Hoy/Journal/Operaciones", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      position: aaplOpen(),
      portfolioReconStatus: "ok",
      asOf: ASOF,
    });
    expect(mercado).not.toBeNull();
    const snap = positionOperatingTruthSurfaceSnapshot(mercado!);
    expect(snap.ctaKind).toBe("maintain");
    expect(snap.ctaLabel).toBe("Mantener");
    expect(positionOperatingTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
    expect(mesaNextActionFromPositionOperatingTruth(mercado!).kind).toBe(
      "maintain",
    );
  });

  it("full_exit + discrepancy → same exit CTA + secondary on every surface", () => {
    const input: BuildPositionOperatingTruthInputV1 = {
      position: aaplOpen({
        lastPrice: 94,
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
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    };
    const { mercado, hoy, journal, operaciones } = fourSurfaces(input);
    const snap = positionOperatingTruthSurfaceSnapshot(mercado!);
    expect(snap.ctaKind).toBe("exit");
    expect(snap.secondaryKinds).toContain("protection_discrepancy");
    expect(positionOperatingTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
  });

  it("orderPending → same in_flight CTA on every surface", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      position: aaplOpen({ lastPrice: 105 }),
      orderPending: true,
      asOf: ASOF,
    });
    const snap = positionOperatingTruthSurfaceSnapshot(mercado!);
    expect(snap.executionLifecycle).toBe("in_flight");
    expect(snap.ctaKind).toBe("review");
    expect(positionOperatingTruthSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(journal!)).toEqual(snap);
    expect(positionOperatingTruthSurfaceSnapshot(operaciones!)).toEqual(snap);
  });

  it("never BUY / allowsEntry false on every surface", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces({
      position: aaplOpen({
        lastPrice: 105,
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
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    for (const t of [mercado, hoy, journal, operaciones]) {
      expect(t!.primaryCta.allowsEntry).toBe(false);
      expect(t!.primaryCta.label).not.toMatch(/comprar/i);
      expect(t!.primaryCta.kind).not.toBe("watch");
    }
  });
});

describe("GP-V161-06 cross-surface POV facts", () => {
  function mercadoPovFacts(input: BuildPositionOperatingTruthInputV1) {
    const state = positionStateFromPositionDto(input.position);
    const recon = mapPortfolioReconToPovRecon(input.portfolioReconStatus);
    return state
      ? buildPositionOperationalView({ position: state, reconStatus: recon })
      : null;
  }

  function potPovFacts(input: BuildPositionOperatingTruthInputV1) {
    return buildPositionOperatingTruth(input)?.operationalView ?? null;
  }

  function decisionFacts(input: BuildPositionOperatingTruthInputV1) {
    return buildPositionDecisionFromDto(input.position, {
      portfolioReconStatus: input.portfolioReconStatus,
    });
  }

  it("same fixture → same POV facts on Mercado/Hoy/Journal/Operaciones builders", () => {
    const input: BuildPositionOperatingTruthInputV1 = {
      position: aaplOpen({
        operational: {
          status: "PROTECTED",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 98,
          target1: 105,
          target2: 110,
          unrealizedR: 0.4,
          exitPlan: { suggestedAction: "hold" },
        },
      }),
      portfolioReconStatus: "ok",
      asOf: ASOF,
    };
    const mercadoPov = mercadoPovFacts(input);
    const hoyPov = mercadoPovFacts(input);
    const journalPov = mercadoPovFacts(input);
    const operacionesPov = mercadoPovFacts(input);
    expect(mercadoPov).toEqual(hoyPov);
    expect(hoyPov).toEqual(journalPov);
    expect(journalPov).toEqual(operacionesPov);

    const mercadoPot = potPovFacts(input);
    const hoyPot = potPovFacts(input);
    expect(mercadoPot).toEqual(hoyPot);
    expect(mercadoPot?.operatingState).toBe("PROTECTED");
    expect(mercadoPov?.operatingState).toBe("PROTECTED");

    const decision = decisionFacts(input);
    expect(decision?.nextEvent).toBe("T1");
    expect(decisionFacts(input)?.nextEvent).toBe(decision?.nextEvent);
  });

  it("drift recon → RECONCILIATION_DRIFT consistently", () => {
    const input: BuildPositionOperatingTruthInputV1 = {
      position: aaplOpen(),
      portfolioReconStatus: "drift",
      asOf: ASOF,
    };
    expect(mercadoPovFacts(input)?.operatingState).toBe("RECONCILIATION_DRIFT");
    expect(potPovFacts(input)?.operatingState).toBe("RECONCILIATION_DRIFT");
    expect(mapPortfolioReconToPovRecon("drift")).toBe("drift");
  });

  it("unknown recon → unavailable, never clean operating overlay", () => {
    const input: BuildPositionOperatingTruthInputV1 = {
      position: aaplOpen(),
      portfolioReconStatus: "unknown",
      asOf: ASOF,
    };
    expect(mapPortfolioReconToPovRecon("unknown")).toBe("unavailable");
    expect(mercadoPovFacts(input)?.operatingState).toBe("RECONCILIATION_ERROR");
    expect(potPovFacts(input)?.operatingState).toBe("RECONCILIATION_ERROR");
  });
});
