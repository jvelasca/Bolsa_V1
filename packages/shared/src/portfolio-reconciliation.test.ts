/**
 * PortfolioReconciliation OI-6 — detect/report (ADR-034).
 */

import { describe, expect, it } from "vitest";
import {
  buildPortfolioReconciliation,
  reconciliationStatusCopy,
} from "./cognitive/portfolio-reconciliation.js";

describe("OI-6 buildPortfolioReconciliation", () => {
  it("clean when cash matches and qty aligns with known tx", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1000,
      ledgerCashSum: 1000,
      holdings: [{ instrumentId: "inst-1", quantity: 10 }],
      openPositions: [
        {
          instrumentId: "inst-1",
          remainingQuantity: 10,
          openTransactionId: "tx-1",
          status: "OPEN",
        },
      ],
      knownTransactionIds: ["tx-1"],
    });
    expect(report.status).toBe("clean");
    expect(report.checks.every((c) => c.outcome !== "mismatch")).toBe(true);
    expect(
      report.checks.some((c) => c.id === "cash_ledger" && c.outcome === "ok"),
    ).toBe(true);
    expect(
      report.checks.some(
        (c) => c.id === "holding_qty_vs_position" && c.outcome === "ok",
      ),
    ).toBe(true);
    expect(
      report.checks.some((c) => c.id === "open_tx_link" && c.outcome === "ok"),
    ).toBe(true);
  });

  it("cash mismatch → drift", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1000,
      ledgerCashSum: 900,
      holdings: [],
      openPositions: [],
    });
    expect(report.status).toBe("drift");
    expect(report.checks.find((c) => c.id === "cash_ledger")?.outcome).toBe(
      "mismatch",
    );
  });

  it("addon holding > remaining → expected (not mismatch)", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1,
      ledgerCashSum: 1,
      holdings: [{ instrumentId: "inst-1", quantity: 15 }],
      openPositions: [
        {
          instrumentId: "inst-1",
          remainingQuantity: 10,
          openTransactionId: "tx-1",
          status: "OPEN",
        },
      ],
      knownTransactionIds: ["tx-1"],
    });
    expect(report.status).toBe("clean");
    expect(
      report.checks.find((c) => c.id === "holding_qty_vs_position")?.outcome,
    ).toBe("expected");
  });

  it("holding without OPEN → expected", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1,
      ledgerCashSum: 1,
      holdings: [{ instrumentId: "legacy", quantity: 3 }],
      openPositions: [],
    });
    expect(report.status).toBe("clean");
    expect(
      report.checks.find((c) => c.id === "holding_without_open")?.outcome,
    ).toBe("expected");
  });

  it("OPEN without holding → mismatch drift", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1,
      ledgerCashSum: 1,
      holdings: [],
      openPositions: [
        {
          instrumentId: "inst-1",
          remainingQuantity: 5,
          openTransactionId: "tx-1",
          status: "OPEN",
        },
      ],
      knownTransactionIds: ["tx-1"],
    });
    expect(report.status).toBe("drift");
    expect(
      report.checks.find((c) => c.id === "open_without_holding")?.outcome,
    ).toBe("mismatch");
  });

  it("open_tx_link unknown when known set omitted", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1,
      ledgerCashSum: 1,
      holdings: [{ instrumentId: "inst-1", quantity: 1 }],
      openPositions: [
        {
          instrumentId: "inst-1",
          remainingQuantity: 1,
          openTransactionId: "tx-1",
          status: "OPEN",
        },
      ],
    });
    expect(report.status).toBe("clean");
    expect(report.checks.find((c) => c.id === "open_tx_link")?.outcome).toBe(
      "unknown",
    );
  });

  it("missing openTransactionId → mismatch", () => {
    const report = buildPortfolioReconciliation({
      accountId: "acc-1",
      portfolioCash: 1,
      ledgerCashSum: 1,
      holdings: [{ instrumentId: "inst-1", quantity: 1 }],
      openPositions: [
        {
          instrumentId: "inst-1",
          remainingQuantity: 1,
          openTransactionId: null,
          status: "OPEN",
        },
      ],
      knownTransactionIds: ["tx-1"],
    });
    expect(report.status).toBe("drift");
    expect(report.checks.find((c) => c.id === "open_tx_link")?.outcome).toBe(
      "mismatch",
    );
  });
});

describe("OI-6 reconciliationStatusCopy", () => {
  it("drift copy does not claim heal", () => {
    expect(reconciliationStatusCopy("drift")).toMatch(/no auto-heal/i);
    expect(reconciliationStatusCopy("clean")).toMatch(/alineadas/i);
  });
});
