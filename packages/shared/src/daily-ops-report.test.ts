/**
 * DailyOpsReport schema — optional autoDesk (V1.46).
 */

import { describe, expect, it } from "vitest";
import {
  DAILY_OPS_REPORT_SCHEMA,
  type DailyOpsReportV1,
} from "./daily-ops-report.js";
import {
  buildPaperDailyReport,
  PAPER_DAILY_REPORT_SCHEMA,
} from "./cognitive/paper-daily-report.js";

describe("daily-ops-report", () => {
  it("accepts optional autoDesk without breaking base shape", () => {
    const autoDesk = buildPaperDailyReport({
      accountId: "acc-1",
      asOf: "2026-08-31",
      dryRun: true,
      paperDExecute: false,
      entry: { status: "dry_run", proposedCount: 0, executedCount: 0 },
      positions: [],
    });
    const withDesk: DailyOpsReportV1 = {
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
      estudioStatus: "empty",
      estudioCount: 0,
      autoDesk,
    };
    expect(withDesk.autoDesk?.schemaVersion).toBe(PAPER_DAILY_REPORT_SCHEMA);
  });
});
