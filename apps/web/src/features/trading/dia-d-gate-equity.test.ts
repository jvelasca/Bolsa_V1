import { describe, expect, it } from "vitest";
import type { BacktestTradeDto } from "@bolsa/shared";
import {
  applyGateFills,
  computeGatedSessionMetrics,
  maxDrawdownPct,
  rebuildEquityCurve,
} from "./dia-d-gate-equity";

function trade(
  partial: Partial<BacktestTradeDto> &
    Pick<BacktestTradeDto, "id" | "type" | "timestamp">,
): BacktestTradeDto {
  return {
    price: 10,
    quantity: 1,
    equityAfter: 10_000,
    ...partial,
  };
}

describe("applyGateFills", () => {
  const trades = [
    trade({
      id: "b1",
      type: "buy",
      timestamp: "2024-01-02",
      price: 100,
      quantity: 10,
    }),
    trade({
      id: "s1",
      type: "sell",
      timestamp: "2024-01-10",
      price: 110,
      quantity: 10,
    }),
    trade({
      id: "b2",
      type: "buy",
      timestamp: "2024-01-15",
      price: 105,
      quantity: 10,
    }),
    trade({
      id: "s2",
      type: "sell",
      timestamp: "2024-01-20",
      price: 108,
      quantity: 10,
    }),
  ];

  it("auto: keeps all trades when no rejects", () => {
    expect(applyGateFills(trades, [], "auto").map((t) => t.id)).toEqual([
      "b1",
      "s1",
      "b2",
      "s2",
    ]);
  });

  it("auto: reject buy drops entry; orphan sell skipped", () => {
    const out = applyGateFills(
      trades,
      [{ tradeId: "b1", action: "reject" }],
      "auto",
    );
    expect(out.map((t) => t.id)).toEqual(["b2", "s2"]);
  });

  it("auto: reject sell keeps position; next buy skipped; later sell closes", () => {
    const out = applyGateFills(
      trades,
      [{ tradeId: "s1", action: "reject" }],
      "auto",
    );
    expect(out.map((t) => t.id)).toEqual(["b1", "s2"]);
  });

  it("auto: initialShares carry allows OOS sell without prior buy in window", () => {
    const oosOnly = [
      trade({
        id: "s1",
        type: "sell",
        timestamp: "2024-01-10",
        price: 110,
        quantity: 10,
      }),
    ];
    const out = applyGateFills(oosOnly, [], "auto", { initialShares: 10 });
    expect(out.map((t) => t.id)).toEqual(["s1"]);
  });

  it("gated: undecided does not fill; only accept executes", () => {
    expect(applyGateFills(trades, [], "gated")).toEqual([]);
    const out = applyGateFills(
      trades,
      [
        { tradeId: "b1", action: "accept" },
        { tradeId: "s1", action: "reject" },
        { tradeId: "b2", action: "accept" },
        { tradeId: "s2", action: "accept" },
      ],
      "gated",
    );
    // s1 rejected → still long from b1 → b2 skipped → s2 closes b1
    expect(out.map((t) => t.id)).toEqual(["b1", "s2"]);
  });
});

describe("rebuildEquityCurve", () => {
  it("marks to market between fills", () => {
    const bars = [
      { timestamp: "2024-01-01", close: 100 },
      { timestamp: "2024-01-02", close: 100 },
      { timestamp: "2024-01-03", close: 120 },
      { timestamp: "2024-01-04", close: 110 },
    ];
    const trades = [
      trade({
        id: "b1",
        type: "buy",
        timestamp: "2024-01-02",
        price: 100,
        quantity: 10,
      }),
      trade({
        id: "s1",
        type: "sell",
        timestamp: "2024-01-04",
        price: 110,
        quantity: 10,
      }),
    ];
    const curve = rebuildEquityCurve({ initialCash: 10_000, bars, trades });
    expect(curve).toHaveLength(4);
    expect(curve[0]!.equity).toBe(10_000);
    expect(curve[1]!.equity).toBe(10_000);
    expect(curve[2]!.equity).toBe(9000 + 10 * 120);
    expect(curve[3]!.equity).toBe(10_100);
  });
});

describe("computeGatedSessionMetrics", () => {
  it("reject entry leaves cash flat vs full auto", () => {
    const bars = [
      { timestamp: "2024-01-01", close: 100 },
      { timestamp: "2024-01-02", close: 100 },
      { timestamp: "2024-01-10", close: 120 },
      { timestamp: "2024-01-11", close: 120 },
    ];
    const autoTrades = [
      trade({
        id: "b1",
        type: "buy",
        timestamp: "2024-01-02",
        price: 100,
        quantity: 10,
      }),
      trade({
        id: "s1",
        type: "sell",
        timestamp: "2024-01-10",
        price: 120,
        quantity: 10,
      }),
    ];
    const full = computeGatedSessionMetrics({
      initialCash: 10_000,
      bars,
      autoTrades,
      decisions: [],
      policy: "auto",
    });
    const gated = computeGatedSessionMetrics({
      initialCash: 10_000,
      bars,
      autoTrades,
      decisions: [{ tradeId: "b1", action: "reject" }],
      policy: "gated",
    });
    expect(full.finalEquity).toBe(10_200);
    expect(gated.tradeCount).toBe(0);
    expect(gated.finalEquity).toBe(10_000);
    expect(gated.totalReturnPct).toBe(0);
  });
});

describe("maxDrawdownPct", () => {
  it("computes peak-to-trough", () => {
    expect(
      maxDrawdownPct([
        { timestamp: "a", equity: 100 },
        { timestamp: "b", equity: 120 },
        { timestamp: "c", equity: 90 },
      ]),
    ).toBeCloseTo(25, 5);
  });
});
