/**
 * V1.46 — PaperDailyReport / autoDesk shape (shared).
 */

import { describe, expect, it } from "vitest";
import {
  buildPaperDailyReport,
  PAPER_DAILY_REPORT_SCHEMA,
} from "./paper-daily-report.js";
import type { DailyOpsReportV1 } from "../daily-ops-report.js";
import { DAILY_OPS_REPORT_SCHEMA } from "../daily-ops-report.js";

describe("paper-daily-report", () => {
  it("GP-DESK-03 builds autoDesk shape", () => {
    const report = buildPaperDailyReport({
      accountId: "acc-1",
      asOf: "2026-08-31",
      dryRun: true,
      paperDExecute: false,
      entry: { status: "dry_run", proposedCount: 2, executedCount: 0 },
      positions: [
        { instrumentId: "MSFT", status: "held", decisionVerdict: "HOLD" },
        {
          instrumentId: "AAPL",
          status: "denied",
          permissionReasons: ["market_closed"],
        },
        { instrumentId: "IBM", status: "protected" },
      ],
      notes: ["dryRun=true — no ledger mutate."],
    });
    expect(report.schemaVersion).toBe(PAPER_DAILY_REPORT_SCHEMA);
    expect(report.entry.proposed).toBe(2);
    expect(report.positions.held).toBe(1);
    expect(report.positions.denied).toBe(1);
    expect(report.positions.protected).toBe(1);
    expect(report.jitDenies.market_closed).toBe(1);
    expect(report.notes.some((n) => n.toLowerCase().includes("dryrun"))).toBe(
      true,
    );
  });

  it("GP-DESK-03 env blocked notes", () => {
    const report = buildPaperDailyReport({
      accountId: "acc-1",
      asOf: null,
      dryRun: false,
      paperDExecute: false,
      blocked: true,
      blockReason: "paper_auto_env_blocked",
      entry: { status: "blocked" },
      positions: [],
      notes: ["PAPER_D_EXECUTE off."],
    });
    expect(report.jitDenies.paper_auto_env_blocked).toBeGreaterThanOrEqual(1);
    expect(report.notes).toContain("paper_auto_env_blocked");
  });
});

describe("daily-ops-report autoDesk optional", () => {
  it("DailyOpsReport válido sin autoDesk", () => {
    const report: DailyOpsReportV1 = {
      schemaVersion: DAILY_OPS_REPORT_SCHEMA,
      asOf: "2026-08-31",
      generatedAt: "2026-08-31T12:00:00Z",
      accountId: "acc-1",
      summary: {} as DailyOpsReportV1["summary"],
      ledgerToday: [],
      tradesToday: [],
      week: [],
      f3PendingCount: 0,
      channels: { alarma: 0, aviso: 0, none: 0 },
      opinions: [],
      notes: [],
      estudioStatus: "ok",
      estudioCount: 0,
    };
    expect(report.autoDesk).toBeUndefined();
  });
});
