/**
 * V1.46 — Paper Daily Report / autoDesk (proyección de PaperDeskCycle).
 *
 * @see docs/engineering/spec-v146-paper-desk-foundation-2026-08-31.md
 */

export const PAPER_DAILY_REPORT_SCHEMA = "paper_daily_report_v1" as const;

export type PaperDailyReportJitDenyCodeV1 =
  | "data_stale"
  | "market_closed"
  | "portfolio_drift"
  | "paper_auto_env_blocked";

export type PaperDeskPositionRowV1 = {
  instrumentId: string;
  status: string;
  reason?: string | null;
  decisionVerdict?: string | null;
  permissionReasons?: string[];
};

export type PaperDailyReportV1 = {
  schemaVersion: typeof PAPER_DAILY_REPORT_SCHEMA;
  accountId: string;
  asOf: string | null;
  dryRun: boolean;
  paperDExecute: boolean;
  blocked?: boolean;
  blockReason?: string | null;
  entry: {
    status: string;
    proposed: number;
    executed: number;
  };
  positions: {
    held: number;
    denied: number;
    protected: number;
    reduced: number;
    exited: number;
    rows: PaperDeskPositionRowV1[];
  };
  jitDenies: Partial<Record<PaperDailyReportJitDenyCodeV1, number>>;
  notes: string[];
};

export type PaperDeskCycleLikeV1 = {
  accountId: string;
  asOf?: string | null;
  dryRun: boolean;
  paperDExecute: boolean;
  blocked?: boolean;
  blockReason?: string | null;
  entry: {
    status: string;
    proposedCount?: number;
    executedCount?: number;
    notes?: string[];
  };
  positions: PaperDeskPositionRowV1[];
  notes?: string[];
};

const JIT_CODES: readonly PaperDailyReportJitDenyCodeV1[] = [
  "data_stale",
  "market_closed",
  "portfolio_drift",
  "paper_auto_env_blocked",
] as const;

export function buildPaperDailyReport(
  cycle: PaperDeskCycleLikeV1,
): PaperDailyReportV1 {
  const jitDenies: Partial<Record<PaperDailyReportJitDenyCodeV1, number>> = {};
  for (const code of JIT_CODES) {
    jitDenies[code] = 0;
  }

  const notes = [...(cycle.notes ?? []), ...(cycle.entry.notes ?? [])];
  if (cycle.blocked || cycle.blockReason === "paper_auto_env_blocked") {
    jitDenies.paper_auto_env_blocked =
      (jitDenies.paper_auto_env_blocked ?? 0) + 1;
    if (!notes.includes("paper_auto_env_blocked")) {
      notes.push("paper_auto_env_blocked");
    }
  }
  if (cycle.dryRun && !notes.some((n) => n.toLowerCase().includes("dryrun"))) {
    notes.push("dryRun");
  }

  let held = 0;
  let denied = 0;
  let protectedCount = 0;
  let reduced = 0;
  let exited = 0;

  for (const row of cycle.positions) {
    if (row.status === "held") held += 1;
    else if (row.status === "denied") {
      denied += 1;
      for (const code of row.permissionReasons ?? []) {
        if ((JIT_CODES as readonly string[]).includes(code)) {
          const key = code as PaperDailyReportJitDenyCodeV1;
          jitDenies[key] = (jitDenies[key] ?? 0) + 1;
        }
      }
      if (row.reason?.includes("paper_auto_env_blocked")) {
        jitDenies.paper_auto_env_blocked =
          (jitDenies.paper_auto_env_blocked ?? 0) + 1;
      }
    } else if (row.status === "protected") protectedCount += 1;
    else if (row.status === "reduced") reduced += 1;
    else if (row.status === "exited") exited += 1;
  }

  return {
    schemaVersion: PAPER_DAILY_REPORT_SCHEMA,
    accountId: cycle.accountId,
    asOf: cycle.asOf ?? null,
    dryRun: cycle.dryRun,
    paperDExecute: cycle.paperDExecute,
    blocked: cycle.blocked,
    blockReason: cycle.blockReason ?? null,
    entry: {
      status: cycle.entry.status,
      proposed: cycle.entry.proposedCount ?? 0,
      executed: cycle.entry.executedCount ?? 0,
    },
    positions: {
      held,
      denied,
      protected: protectedCount,
      reduced,
      exited,
      rows: [...cycle.positions],
    },
    jitDenies,
    notes,
  };
}
