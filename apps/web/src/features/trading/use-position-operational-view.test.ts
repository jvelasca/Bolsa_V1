import { describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { mapPortfolioReconToPovRecon } from "@bolsa/shared";
import { buildPositionOperationalViewFromDto } from "@/features/trading/use-position-operational-view";

describe("mapPortfolioReconToPovRecon GP-V161-01", () => {
  it("known clean values → clean", () => {
    expect(mapPortfolioReconToPovRecon("clean")).toBe("clean");
    expect(mapPortfolioReconToPovRecon("ok")).toBe("clean");
    expect(mapPortfolioReconToPovRecon("OK")).toBe("clean");
  });

  it("drift → drift", () => {
    expect(mapPortfolioReconToPovRecon("drift")).toBe("drift");
  });

  it("unavailable family → unavailable", () => {
    expect(mapPortfolioReconToPovRecon("unavailable")).toBe("unavailable");
    expect(mapPortfolioReconToPovRecon("not_wired")).toBe("unavailable");
    expect(mapPortfolioReconToPovRecon("error")).toBe("unavailable");
  });

  it("empty/null → null (not clean)", () => {
    expect(mapPortfolioReconToPovRecon(null)).toBeNull();
    expect(mapPortfolioReconToPovRecon(undefined)).toBeNull();
    expect(mapPortfolioReconToPovRecon("")).toBeNull();
  });

  it("unknown wire values → unavailable, never clean", () => {
    for (const bad of ["unknown", "degraded", "garbage", "pending"]) {
      expect(mapPortfolioReconToPovRecon(bad)).toBe("unavailable");
      expect(mapPortfolioReconToPovRecon(bad)).not.toBe("clean");
    }
  });

  it("error/unknown → RECONCILIATION_ERROR operatingState", () => {
    const position: PositionDto = {
      id: "p1",
      instrumentId: "inst-aapl",
      symbol: "AAPL",
      name: "Apple",
      quantity: 10,
      avgCost: 100,
      lastPrice: 102,
      marketValue: 1020,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      operational: {
        status: "PROTECTED",
        direction: "long",
        tradePlanId: "tp-1",
        currentStop: 98,
        target1: 110,
        target2: 120,
        initialStop: 95,
      },
    };
    for (const bad of ["error", "unknown", "degraded"]) {
      const result = buildPositionOperationalViewFromDto(position, bad);
      expect(result?.view.operatingState).toBe("RECONCILIATION_ERROR");
    }
  });
});

describe("buildPositionOperationalViewFromDto", () => {
  it("T2_READY from operational blob legs", () => {
    const position: PositionDto = {
      id: "p1",
      instrumentId: "inst-aapl",
      symbol: "AAPL",
      name: "Apple",
      quantity: 7,
      avgCost: 100,
      lastPrice: 102,
      marketValue: 714,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      operational: {
        status: "PARTIAL",
        direction: "long",
        tradePlanId: "tp-1",
        plannedEntry: 100,
        actualEntry: 100,
        initialStop: 95,
        currentStop: 98,
        target1: 110,
        target2: 120,
        remainingQuantity: 7,
        target1Leg: {
          status: "executed",
          fillId: "tx-t1",
          at: "2026-09-01T11:00:00.000Z",
        },
        target2Leg: {
          status: "triggered",
          at: "2026-09-01T13:00:00.000Z",
        },
      } as PositionDto["operational"],
    };
    const result = buildPositionOperationalViewFromDto(position, "ok");
    expect(result?.view.operatingState).toBe("T2_READY");
    expect(result?.source).toBe("canonical");
  });

  it("RECONCILIATION_DRIFT when portfolio recon drift", () => {
    const position: PositionDto = {
      id: "p1",
      instrumentId: "inst-aapl",
      symbol: "AAPL",
      name: "Apple",
      quantity: 10,
      avgCost: 100,
      lastPrice: 102,
      marketValue: 1020,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      operational: {
        status: "PROTECTED",
        direction: "long",
        tradePlanId: "tp-1",
        currentStop: 98,
        target1: 110,
        target2: 120,
        initialStop: 95,
      },
    };
    const result = buildPositionOperationalViewFromDto(position, "drift");
    expect(result?.view.operatingState).toBe("RECONCILIATION_DRIFT");
  });

  it("GP-V165-06: prefers wire operationalView without rebuilding", () => {
    const wireView = {
      positionId: "p1",
      instrumentId: "inst-aapl",
      tradePlanId: "TP-1",
      decisionId: "DEC-1",
      lineageCollapsed: false,
      operatingState: "PROTECTED",
      primaryAction: "SUBIR_STOP",
      levels: {
        entry: 100,
        currentStop: 98,
        target1: 110,
        target2: 120,
        unrealizedR: 0.5,
      },
      t1: null,
      t2: null,
      stopHistory: [],
      events: [],
      quantity: 10,
      remainingQuantity: 10,
    };
    const position: PositionDto = {
      id: "p1",
      instrumentId: "inst-aapl",
      symbol: "AAPL",
      name: "Apple",
      quantity: 10,
      avgCost: 100,
      lastPrice: 102,
      marketValue: 1020,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      operational: {
        status: "OPEN",
        direction: "long",
        tradePlanId: "TP-1",
        decisionId: "DEC-1",
        currentStop: 98,
        target1: 110,
        target2: 120,
        operationalView: wireView,
      },
    };
    const result = buildPositionOperationalViewFromDto(position, "ok");
    expect(result?.source).toBe("canonical");
    expect(result?.view).toBe(wireView);
    expect(result?.view.decisionId).toBe("DEC-1");
    expect(result?.view.tradePlanId).toBe("TP-1");
  });

  it("GP-V170-05: fail-closed without wire or operational blob", () => {
    const position: PositionDto = {
      id: "p-fallback",
      instrumentId: "inst-x",
      symbol: "X",
      name: "No wire",
      quantity: 10,
      avgCost: 100,
      lastPrice: 102,
      marketValue: 1020,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
    };
    expect(buildPositionOperationalViewFromDto(position, "ok")).toBeNull();
  });
});
