import { describe, expect, it, beforeEach } from "vitest";
import type { TransactionDto } from "@bolsa/shared";
import {
  MANDATE_TENURES_KEY,
  MANDATE_TRADE_LINKS_KEY,
  applyMandateChange,
  linkTradeToMandate,
} from "@/features/platform/operating-mandate";
import {
  buildMandatePnlReport,
  computeTenureCashflow,
} from "@/features/platform/mandate-tenure-pnl";

function tx(
  partial: Partial<TransactionDto> &
    Pick<TransactionDto, "id" | "type" | "total">,
): TransactionDto {
  return {
    instrumentId: "inst-1",
    symbol: "ACS",
    quantity: 1,
    price: 10,
    executedAt: "2026-01-01T00:00:00Z",
    ...partial,
  };
}

describe("mandate-tenure-pnl", () => {
  beforeEach(() => {
    localStorage.removeItem(MANDATE_TENURES_KEY);
    localStorage.removeItem(MANDATE_TRADE_LINKS_KEY);
  });

  it("aggregates buy/sell notional per tenure", () => {
    const { opened } = applyMandateChange({
      instrumentId: "inst-1",
      accountId: "acc-1",
      open: {
        strategyDefinitionId: "s1",
        strategyLabelSnapshot: "SMA",
      },
    });
    expect(opened).toBeTruthy();
    linkTradeToMandate({
      transactionId: "t-buy",
      instrumentId: "inst-1",
      accountId: "acc-1",
      mandateTenureId: opened!.id,
    });
    linkTradeToMandate({
      transactionId: "t-sell",
      instrumentId: "inst-1",
      accountId: "acc-1",
      mandateTenureId: opened!.id,
    });
    const byId = new Map([
      ["t-buy", tx({ id: "t-buy", type: "buy", total: 1000 })],
      ["t-sell", tx({ id: "t-sell", type: "sell", total: 1200 })],
    ]);
    const row = computeTenureCashflow(opened!, byId);
    expect(row.tradeCount).toBe(2);
    expect(row.buyNotional).toBe(1000);
    expect(row.sellNotional).toBe(1200);
    expect(row.netCashFlow).toBe(200);

    const report = buildMandatePnlReport({
      instrumentId: "inst-1",
      accountId: "acc-1",
      transactions: [...byId.values()],
    });
    expect(report.totalNetCashFlow).toBe(200);
    expect(report.totalLinkedTrades).toBe(2);
  });
});
