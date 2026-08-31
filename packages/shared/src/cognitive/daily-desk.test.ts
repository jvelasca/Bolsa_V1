/**
 * V1.41 — Daily Desk: misma attention → mismo inbox (contratos de builders).
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import {
  attentionRank,
  buildDailyDeskInbox,
  dailyDeskSurfaceSnapshot,
} from "./daily-desk.js";

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

describe("dailyDesk V1.41", () => {
  it("HOLD clean position → empty inbox (NORMAL)", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "ok",
      pendingConfirm: 0,
    });
    expect(inbox.count).toBe(0);
    expect(inbox.emptyLabel).toMatch(/Nada requiere/i);
  });

  it("pending confirm → URGENT item first", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      pendingConfirm: 2,
      portfolioReconStatus: "ok",
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.kind).toBe("pending_confirm");
    expect(inbox.items[0]?.attention).toBe("URGENT");
    expect(inbox.items[0]?.ctaLabel).toBe("Revisar y confirmar");
  });

  it("T1 reached → position item with Reducir CTA", () => {
    const pos = aaplOpen({
      lastPrice: 105,
      marketValue: 1050,
      unrealizedPnl: 50,
    });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.kind).toBe("position");
    expect(inbox.items[0]?.ctaLabel).toBe("Reducir");
    expect(attentionRank(inbox.items[0]!.attention)).toBeGreaterThan(0);
  });

  it("recon drift → BLOCKED attention ahead of HOLD noise", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "drift",
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.attention).toBe("BLOCKED");
    expect(inbox.items[0]?.ctaLabel).toBe("Revisar");
  });

  it("protection discrepancy appears as board_attention", () => {
    const inbox = buildDailyDeskInbox({
      positions: [],
      protectionDiscrepancies: [
        {
          symbol: "MSFT",
          reason: "Discrepancia de protección",
          recommendedAction: "REVISAR PROTECCIÓN",
        },
      ],
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.kind).toBe("board_attention");
    expect(inbox.items[0]?.ctaLabel).toBe("Proteger");
    expect(inbox.items[0]?.attention).toBe("URGENT");
  });

  it("surface snapshot is stable for same inputs", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const a = buildDailyDeskInbox({
      positions: [pos],
      pendingConfirm: 1,
      portfolioReconStatus: "ok",
    });
    const b = buildDailyDeskInbox({
      positions: [pos],
      pendingConfirm: 1,
      portfolioReconStatus: "ok",
    });
    expect(dailyDeskSurfaceSnapshot(a)).toEqual(dailyDeskSurfaceSnapshot(b));
    expect(dailyDeskSurfaceSnapshot(a).ctaLabels).toContain(
      "Revisar y confirmar",
    );
    expect(dailyDeskSurfaceSnapshot(a).ctaLabels).toContain("Reducir");
  });

  it("never exposes BUY in CTA labels", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen({ lastPrice: 105 })],
      pendingConfirm: 1,
      protectionDiscrepancies: [
        {
          symbol: "X",
          reason: "x",
          recommendedAction: "REVISAR",
        },
      ],
    });
    for (const item of inbox.items) {
      expect(item.ctaLabel.toUpperCase()).not.toContain("BUY");
      expect(item.ctaLabel.toUpperCase()).not.toContain("COMPRAR");
    }
  });

  it("orderPending on T1 still lists the position (hint is none internally)", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
      pendingInstrumentIds: [pos.instrumentId],
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.ctaLabel).toBe("Reducir");
  });
});
