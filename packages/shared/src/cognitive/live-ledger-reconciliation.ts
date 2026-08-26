/**
 * LiveLedgerReconciliation — detect/report live venue ↔ ledger (ADR-034 LR-1).
 * Live cash/positions vs portfolio cash/holdings. No auto-heal. ≠ execute_trade.
 */

export type LiveReconciliationCheckOutcomeV1 =
  | "ok"
  | "mismatch"
  | "expected"
  | "unknown";

export type LiveReconciliationCheckIdV1 =
  | "live_cash_vs_ledger"
  | "live_qty_vs_holding"
  | "live_without_holding"
  | "holding_without_live";

export type LiveReconciliationCheckV1 = {
  id: LiveReconciliationCheckIdV1;
  outcome: LiveReconciliationCheckOutcomeV1;
  detail: string | null;
  instrumentId: string | null;
};

export type LiveLedgerReconciliationStatusV1 =
  | "clean"
  | "drift"
  | "unavailable";

export type LiveLedgerReconciliationV1 = {
  accountId: string;
  status: LiveLedgerReconciliationStatusV1;
  checks: LiveReconciliationCheckV1[];
};

export const LIVE_LEDGER_RECONCILIATION_KEY = "liveLedgerReconciliation";

const CASH_EPS = 1e-6;
const QTY_EPS = 1e-9;

/** HoldingSnapV1-style snap for live venue positions. */
export type LivePositionSnapV1 = {
  instrumentId: string;
  quantity: number;
};

export type HoldingSnapForLiveV1 = {
  instrumentId: string;
  quantity: number;
};

export type BuildLiveLedgerReconciliationInputV1 = {
  accountId: string;
  ledgerCash: number;
  liveCash: number;
  holdings: HoldingSnapForLiveV1[];
  livePositions: LivePositionSnapV1[];
  /** Venue unreachable / client missing → status unavailable. */
  unavailable?: boolean;
};

function trimId(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const t = value.trim();
  return t ? t : null;
}

function check(
  id: LiveReconciliationCheckIdV1,
  outcome: LiveReconciliationCheckOutcomeV1,
  detail: string | null = null,
  instrumentId: string | null = null,
): LiveReconciliationCheckV1 {
  return { id, outcome, detail, instrumentId };
}

/** Pure detect/report. No mutates. */
export function buildLiveLedgerReconciliation(
  input: BuildLiveLedgerReconciliationInputV1,
): LiveLedgerReconciliationV1 {
  const accountId = (input.accountId ?? "").trim();

  if (input.unavailable === true) {
    return {
      accountId,
      status: "unavailable",
      checks: [
        check("live_cash_vs_ledger", "unknown", "live venue unavailable"),
      ],
    };
  }

  const checks: LiveReconciliationCheckV1[] = [];

  const cashDelta = Math.abs(Number(input.liveCash) - Number(input.ledgerCash));
  if (Number.isFinite(cashDelta) && cashDelta < CASH_EPS) {
    checks.push(check("live_cash_vs_ledger", "ok", "liveCash == ledgerCash"));
  } else {
    checks.push(
      check(
        "live_cash_vs_ledger",
        "mismatch",
        `liveCash=${input.liveCash} ledgerCash=${input.ledgerCash}`,
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

  const liveByInst = new Map<string, number>();
  for (const p of input.livePositions ?? []) {
    const id = trimId(p.instrumentId);
    if (!id) continue;
    const qty = Number(p.quantity);
    if (!Number.isFinite(qty) || qty <= QTY_EPS) continue;
    liveByInst.set(id, (liveByInst.get(id) ?? 0) + qty);
  }

  for (const [instId, liveQty] of liveByInst) {
    const holdingQty = holdingByInst.get(instId) ?? 0;
    if (holdingQty <= QTY_EPS) {
      checks.push(
        check(
          "live_without_holding",
          "mismatch",
          `live qty=${liveQty} without holding`,
          instId,
        ),
      );
    } else if (Math.abs(holdingQty - liveQty) < QTY_EPS) {
      checks.push(
        check(
          "live_qty_vs_holding",
          "ok",
          `qty=${liveQty} holding=${holdingQty}`,
          instId,
        ),
      );
    } else {
      checks.push(
        check(
          "live_qty_vs_holding",
          "mismatch",
          `live=${liveQty} holding=${holdingQty}`,
          instId,
        ),
      );
    }
  }

  for (const [instId, qty] of holdingByInst) {
    if (liveByInst.has(instId)) continue;
    checks.push(
      check(
        "holding_without_live",
        "expected",
        `holding qty=${qty} without live position`,
        instId,
      ),
    );
  }

  const status: LiveLedgerReconciliationStatusV1 = checks.some(
    (c) => c.outcome === "mismatch",
  )
    ? "drift"
    : "clean";

  return { accountId, status, checks };
}

export function liveLedgerReconciliationStatusCopy(
  status: LiveLedgerReconciliationStatusV1,
): string {
  if (status === "unavailable") {
    return "Venue live no disponible — sin reconcile";
  }
  if (status === "drift") {
    return "Deriva live↔ledger detectada — no auto-heal";
  }
  return "Live y ledger alineados (o solo expected)";
}
