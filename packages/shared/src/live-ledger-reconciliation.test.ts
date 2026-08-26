/**
 * LiveLedgerReconciliation LR-1 — detect/report (ADR-034).
 */

import { describe, expect, it } from "vitest";
import {
  buildLiveLedgerReconciliation,
  liveLedgerReconciliationStatusCopy,
} from "./cognitive/live-ledger-reconciliation.js";

describe("LR-1 buildLiveLedgerReconciliation", () => {
  it("clean when cash matches and qty aligns", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1000,
      liveCash: 1000,
      holdings: [{ instrumentId: "inst-1", quantity: 10 }],
      livePositions: [{ instrumentId: "inst-1", quantity: 10 }],
    });
    expect(report.status).toBe("clean");
    expect(report.checks.every((c) => c.outcome !== "mismatch")).toBe(true);
    expect(
      report.checks.some(
        (c) => c.id === "live_cash_vs_ledger" && c.outcome === "ok",
      ),
    ).toBe(true);
    expect(
      report.checks.some(
        (c) => c.id === "live_qty_vs_holding" && c.outcome === "ok",
      ),
    ).toBe(true);
  });

  it("cash mismatch → drift", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1000,
      liveCash: 900,
      holdings: [],
      livePositions: [],
    });
    expect(report.status).toBe("drift");
    expect(
      report.checks.find((c) => c.id === "live_cash_vs_ledger")?.outcome,
    ).toBe("mismatch");
  });

  it("unavailable → status unavailable", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1,
      liveCash: 0,
      holdings: [],
      livePositions: [],
      unavailable: true,
    });
    expect(report.status).toBe("unavailable");
    expect(report.checks.some((c) => c.outcome === "unknown")).toBe(true);
  });

  it("holding without live → expected", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1,
      liveCash: 1,
      holdings: [{ instrumentId: "legacy", quantity: 3 }],
      livePositions: [],
    });
    expect(report.status).toBe("clean");
    expect(
      report.checks.find((c) => c.id === "holding_without_live")?.outcome,
    ).toBe("expected");
  });

  it("live without holding → mismatch drift", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1,
      liveCash: 1,
      holdings: [],
      livePositions: [{ instrumentId: "inst-1", quantity: 5 }],
    });
    expect(report.status).toBe("drift");
    expect(
      report.checks.find((c) => c.id === "live_without_holding")?.outcome,
    ).toBe("mismatch");
  });

  it("qty mismatch → drift", () => {
    const report = buildLiveLedgerReconciliation({
      accountId: "acc-1",
      ledgerCash: 1,
      liveCash: 1,
      holdings: [{ instrumentId: "inst-1", quantity: 10 }],
      livePositions: [{ instrumentId: "inst-1", quantity: 7 }],
    });
    expect(report.status).toBe("drift");
    expect(
      report.checks.find((c) => c.id === "live_qty_vs_holding")?.outcome,
    ).toBe("mismatch");
  });
});

describe("LR-1 liveLedgerReconciliationStatusCopy", () => {
  it("copies cover unavailable / drift / clean", () => {
    expect(liveLedgerReconciliationStatusCopy("unavailable")).toMatch(
      /no disponible/i,
    );
    expect(liveLedgerReconciliationStatusCopy("drift")).toMatch(
      /no auto-heal/i,
    );
    expect(liveLedgerReconciliationStatusCopy("clean")).toMatch(/alineados/i);
  });
});
