/**
 * PortfolioReconciliation — detect/report integrity paper (ADR-034 OI-6).
 * Ledger ↔ holdings ↔ PositionState ↔ cash. No auto-heal. ≠ broker ≠ ADR-021.
 */

export type ReconciliationCheckOutcomeV1 =
  | "ok"
  | "mismatch"
  | "expected"
  | "unknown";

export type ReconciliationCheckIdV1 =
  | "cash_ledger"
  | "holding_qty_vs_position"
  | "open_without_holding"
  | "holding_without_open"
  | "open_tx_link";

export type ReconciliationCheckV1 = {
  id: ReconciliationCheckIdV1;
  outcome: ReconciliationCheckOutcomeV1;
  detail: string | null;
  instrumentId: string | null;
};

export type PortfolioReconciliationStatusV1 = "clean" | "drift";

export type PortfolioReconciliationV1 = {
  accountId: string;
  status: PortfolioReconciliationStatusV1;
  checks: ReconciliationCheckV1[];
};

export const PORTFOLIO_RECONCILIATION_KEY = "portfolioReconciliation";

const CASH_EPS = 1e-6;
const QTY_EPS = 1e-9;

export type HoldingSnapV1 = {
  instrumentId: string;
  quantity: number;
};

export type OpenPositionSnapV1 = {
  instrumentId: string;
  remainingQuantity: number;
  openTransactionId: string | null;
  status: string;
};

export type BuildPortfolioReconciliationInputV1 = {
  accountId: string;
  portfolioCash: number;
  ledgerCashSum: number;
  holdings: HoldingSnapV1[];
  openPositions: OpenPositionSnapV1[];
  /** Si se omite, open_tx_link → unknown. */
  knownTransactionIds?: readonly string[] | null;
};

function trimId(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const t = value.trim();
  return t ? t : null;
}

function check(
  id: ReconciliationCheckIdV1,
  outcome: ReconciliationCheckOutcomeV1,
  detail: string | null = null,
  instrumentId: string | null = null,
): ReconciliationCheckV1 {
  return { id, outcome, detail, instrumentId };
}

/** Pure detect/report. No mutates. */
export function buildPortfolioReconciliation(
  input: BuildPortfolioReconciliationInputV1,
): PortfolioReconciliationV1 {
  const accountId = (input.accountId ?? "").trim();
  const checks: ReconciliationCheckV1[] = [];

  const cashDelta = Math.abs(
    Number(input.portfolioCash) - Number(input.ledgerCashSum),
  );
  if (Number.isFinite(cashDelta) && cashDelta < CASH_EPS) {
    checks.push(check("cash_ledger", "ok", "portfolioCash == Σ ledger"));
  } else {
    checks.push(
      check(
        "cash_ledger",
        "mismatch",
        `portfolioCash=${input.portfolioCash} ledgerSum=${input.ledgerCashSum}`,
      ),
    );
  }

  const holdingByInst = new Map<string, number>();
  for (const h of input.holdings ?? []) {
    const id = trimId(h.instrumentId);
    if (!id) continue;
    const qty = Number(h.quantity);
    if (!Number.isFinite(qty) || qty <= QTY_EPS) continue;
    holdingByInst.set(id, (holdingByInst.get(id) ?? 0) + qty);
  }

  const openByInst = new Map<string, OpenPositionSnapV1>();
  for (const p of input.openPositions ?? []) {
    const id = trimId(p.instrumentId);
    if (!id) continue;
    if (p.status === "CLOSED") continue;
    openByInst.set(id, p);
  }

  const known =
    input.knownTransactionIds == null
      ? null
      : new Set(
          [...input.knownTransactionIds]
            .map((x) => trimId(x))
            .filter((x): x is string => Boolean(x)),
        );

  for (const [instId, pos] of openByInst) {
    const remaining = Number(pos.remainingQuantity);
    const holdingQty = holdingByInst.get(instId) ?? 0;

    if (!Number.isFinite(remaining) || remaining <= QTY_EPS) {
      continue;
    }

    if (holdingQty <= QTY_EPS) {
      checks.push(
        check(
          "open_without_holding",
          "mismatch",
          `OPEN remaining=${remaining} without holding`,
          instId,
        ),
      );
    } else if (Math.abs(holdingQty - remaining) < QTY_EPS) {
      checks.push(
        check(
          "holding_qty_vs_position",
          "ok",
          `qty=${holdingQty} remaining=${remaining}`,
          instId,
        ),
      );
    } else if (holdingQty > remaining + QTY_EPS) {
      checks.push(
        check(
          "holding_qty_vs_position",
          "expected",
          `addon holding=${holdingQty} > remaining=${remaining}`,
          instId,
        ),
      );
    } else {
      checks.push(
        check(
          "holding_qty_vs_position",
          "mismatch",
          `holding=${holdingQty} < remaining=${remaining}`,
          instId,
        ),
      );
    }

    const txId = trimId(pos.openTransactionId);
    if (known == null) {
      checks.push(
        check("open_tx_link", "unknown", "knownTransactionIds omitted", instId),
      );
    } else if (!txId) {
      checks.push(
        check("open_tx_link", "mismatch", "openTransactionId missing", instId),
      );
    } else if (known.has(txId)) {
      checks.push(check("open_tx_link", "ok", `tx=${txId}`, instId));
    } else {
      checks.push(
        check(
          "open_tx_link",
          "mismatch",
          `tx=${txId} not in known transactions`,
          instId,
        ),
      );
    }
  }

  for (const [instId, qty] of holdingByInst) {
    if (openByInst.has(instId)) continue;
    checks.push(
      check(
        "holding_without_open",
        "expected",
        `holding qty=${qty} without OPEN PositionState (legacy/orphan)`,
        instId,
      ),
    );
  }

  const status: PortfolioReconciliationStatusV1 = checks.some(
    (c) => c.outcome === "mismatch",
  )
    ? "drift"
    : "clean";

  return { accountId, status, checks };
}

export function reconciliationStatusCopy(
  status: PortfolioReconciliationStatusV1,
): string {
  if (status === "drift") {
    return "Deriva paper detectada — no auto-heal";
  }
  return "Capas paper alineadas (o solo expected)";
}
