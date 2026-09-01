import { describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { buildPositionOperationalViewFromDto } from "@/features/trading/use-position-operational-view";

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
    const view = buildPositionOperationalViewFromDto(position, "ok");
    expect(view?.operatingState).toBe("T2_READY");
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
    const view = buildPositionOperationalViewFromDto(position, "drift");
    expect(view?.operatingState).toBe("RECONCILIATION_DRIFT");
  });
});
