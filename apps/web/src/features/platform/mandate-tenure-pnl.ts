/**
 * PnL / flujo de caja por tenure de mandato (ADR-020 M4 cliente).
 * Usa trades enlazados (`linkTradeToMandate`) + transacciones del ledger.
 * No es PnL mark-to-market: flujo neto = ventas − compras de los fills enlazados.
 */

import type { TransactionDto } from "@bolsa/shared";
import {
  listMandateTenures,
  listTradeLinksForMandate,
  type MandateTenure,
} from "@/features/platform/operating-mandate";

export type MandateTenureCashflow = {
  tenureId: string;
  strategyLabel: string | null;
  tradeCount: number;
  buyNotional: number;
  sellNotional: number;
  /** sell totals − buy totals (flujo de caja enlazado). */
  netCashFlow: number;
  open: boolean;
};

export function computeTenureCashflow(
  tenure: MandateTenure,
  transactionsById: ReadonlyMap<string, TransactionDto>,
): MandateTenureCashflow {
  const links = listTradeLinksForMandate(tenure.id);
  let buyNotional = 0;
  let sellNotional = 0;
  let tradeCount = 0;
  for (const link of links) {
    const tx = transactionsById.get(link.transactionId);
    if (!tx) continue;
    tradeCount += 1;
    const notional = Number(tx.total);
    if (!Number.isFinite(notional)) continue;
    if (tx.type === "buy") buyNotional += notional;
    else sellNotional += notional;
  }
  return {
    tenureId: tenure.id,
    strategyLabel: tenure.strategyLabelSnapshot ?? null,
    tradeCount,
    buyNotional,
    sellNotional,
    netCashFlow: sellNotional - buyNotional,
    open: tenure.effectiveTo == null,
  };
}

export function buildMandatePnlReport(opts: {
  instrumentId: string;
  accountId: string;
  transactions: ReadonlyArray<TransactionDto>;
}): {
  rows: MandateTenureCashflow[];
  totalNetCashFlow: number;
  totalLinkedTrades: number;
} {
  const byId = new Map(opts.transactions.map((t) => [t.id, t]));
  const tenures = listMandateTenures(opts.instrumentId, opts.accountId);
  const rows = tenures.map((t) => computeTenureCashflow(t, byId));
  return {
    rows,
    totalNetCashFlow: rows.reduce((s, r) => s + r.netCashFlow, 0),
    totalLinkedTrades: rows.reduce((s, r) => s + r.tradeCount, 0),
  };
}

export function formatMandateCashflow(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}`;
}
