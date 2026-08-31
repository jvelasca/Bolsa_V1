/**
 * V1.40 — misma posición → misma ExitRouteView en Mercado / Hoy / Journal / Operaciones.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import {
  buildExitRouteView,
  exitRouteSurfaceSnapshot,
} from "./exit-route-view.js";
import { buildOperationalTruth } from "./operational-truth.js";

const ASOF = "2026-08-31T10:00:00.000Z";

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

function fourSurfaces(position: PositionDto) {
  const truth = buildOperationalTruth({ position, asOf: ASOF });
  expect(truth).not.toBeNull();
  const input = { truth: truth!, position, asOf: ASOF };
  return {
    mercado: buildExitRouteView(input),
    hoy: buildExitRouteView(input),
    journal: buildExitRouteView(input),
    operaciones: buildExitRouteView(input),
  };
}

describe("sameExitRouteAcrossSurfaces V1.40", () => {
  it("open long → misma ruta Entrada/Stop/T1/T2 en las cuatro superficies", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces(aaplOpen());
    expect(mercado).not.toBeNull();
    const snap = exitRouteSurfaceSnapshot(mercado!);
    expect(snap).toEqual({
      labels: ["T2", "T1", "Precio", "Entrada", "Stop"],
      roleLabels: ["T2", "T1", "Actual", "Entrada", "Proteger"],
      values: [110, 105, 102, 100, 95],
      trailingActive: false,
    });
    expect(exitRouteSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(exitRouteSurfaceSnapshot(journal!)).toEqual(snap);
    expect(exitRouteSurfaceSnapshot(operaciones!)).toEqual(snap);
  });

  it("T1 touched → progress hint coherente (no confundir con gestionado)", () => {
    const pos = aaplOpen({
      lastPrice: 105,
      marketValue: 1050,
      unrealizedPnl: 50,
    });
    const route = buildExitRouteView({
      truth: buildOperationalTruth({ position: pos, asOf: ASOF })!,
      position: pos,
    });
    const t1 = route?.nodes.find((n) => n.kind === "target1");
    expect(t1?.progressHint).toMatch(/alcanzado/i);
    expect(t1?.progressHint).not.toBe("✓ gestionado");
  });

  it("trailing active → T2 roleLabel incluye trailing", () => {
    const pos = aaplOpen({
      lastPrice: 115,
      marketValue: 1150,
      unrealizedPnl: 150,
      operational: {
        status: "OPEN",
        direction: "long",
        tradePlanId: "tp-aapl",
        plannedEntry: 100,
        actualEntry: 100,
        initialStop: 95,
        currentStop: 100,
        target1: 105,
        target2: 110,
        unrealizedR: 2.5,
        mfeMae: { mfeR: 2.5, maeR: -0.2, source: "close_proxy" },
      },
    });
    const route = buildExitRouteView({
      truth: buildOperationalTruth({ position: pos, asOf: ASOF })!,
      position: pos,
    });
    expect(route?.trailingActive).toBe(true);
    const t2 = route?.nodes.find((n) => n.kind === "target2");
    expect(t2?.roleLabel).toBe("T2 · trailing");
  });

  it("sin plan operativo → truth null (sin ruta)", () => {
    const pos = aaplOpen({ operational: undefined });
    expect(buildOperationalTruth({ position: pos, asOf: ASOF })).toBeNull();
  });
});
