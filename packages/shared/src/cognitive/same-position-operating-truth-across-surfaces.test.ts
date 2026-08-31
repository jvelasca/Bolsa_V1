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
