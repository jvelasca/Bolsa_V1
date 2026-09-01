/**
 * V1.46/V1.47 — Paper Daily Report / autoDesk (proyección de PaperDeskCycle).
 *
 * @see docs/engineering/spec-v147-paper-desk-runtime-truth-2026-09-01.md
 */

import type { PaperDeskNextActionV1 } from "./operational-context.js";
import type { TradePlanV1 } from "./trade-plan.js";

export const PAPER_DAILY_REPORT_SCHEMA = "paper_daily_report_v1" as const;

/** V1.50 — reason codes de EntryTick (mirror Python EntryReasonCode). */
export type PaperDeskEntryReasonCodeV1 =
  | "ENTRY_NO_TRIGGER"
  | "ENTRY_INVALID_STOP"
  | "ENTRY_RISK_LIMIT"
  | "ENTRY_STALE_DATA"
  | "ENTRY_MANDATE_BLOCK"
  | "ENTRY_POLICY_MISSING"
  | "ENTRY_MARKET_CLOSED"
  | "ENTRY_DUPLICATE"
  | "ENTRY_ENV_BLOCKED"
  | "ENTRY_UNIVERSE_EMPTY"
  | "ENTRY_UNIVERSE_UNAVAILABLE"
  | "ENTRY_INFRA_UNAVAILABLE";

/** V1.50 — CandidateSnapshot transport (mirror Python paper_desk_cycle). */
export type PaperDeskCandidateSnapshotV1 = {
  decisionId: string;
  instrumentId: string;
  rank: number;
  score: number;
  symbol?: string | null;
  autoSource?: string | null;
  templateId?: string | null;
  analysisAsOf?: string | null;
  marketAsOf?: string | null;
  executionAsOf?: string | null;
  tradePlan?: TradePlanV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
  target1?: number | null;
  target2?: number | null;
  riskAmount?: number | null;
  expectedRr?: number | null;
  mandate?: string;
  freshness?: string;
  vetoes?: string[];
  reasonCode?: PaperDeskEntryReasonCodeV1 | null;
  humanMessage?: string | null;
};

/** V1.54 — excepciones operativas para cubo 🔴 (sin auto-heal). */
export type DailyDeskExceptionKindV1 =
  | "position_birth_failed"
  | "portfolio_recon_drift"
  | "portfolio_recon_unavailable";

export type DailyDeskExceptionFactV1 = {
  kind: DailyDeskExceptionKindV1;
  instrumentId?: string | null;
  symbol?: string | null;
  decisionId?: string | null;
  message?: string | null;
};

export type PaperDailyReportEntryV1 = {
  status: string;
  proposed: number;
  executed: number;
  candidates?: PaperDeskCandidateSnapshotV1[];
  skipped?: PaperDeskCandidateSnapshotV1[];
};

export type PaperDailyReportJitDenyCodeV1 =
  | "data_stale"
  | "market_closed"
  | "portfolio_drift"
  | "paper_auto_env_blocked"
  | "data_unavailable";

export type PaperDeskPositionRowV1 = {
  instrumentId: string;
  status: string;
  reason?: string | null;
  decisionVerdict?: string | null;
  permissionReasons?: string[];
  nextAction?: PaperDeskNextActionV1 | string | null;
  decisionAction?: string | null;
  executedAction?: string | null;
  operatingState?: string | null;
};

export type PaperDailyReportSectionsV1 = {
  decisiones: {
    candidates: number;
    proposed: number;
    authorized: number;
    executed: number;
  };
  operativa: {
    entries: number;
    t1: number;
    trails: number;
    exits: number;
  };
  resultado: {
    realizedR: number | null;
    dayPct: number | null;
  };
  noOperadas: {
    skipped: number;
    reasonCodes: Partial<Record<PaperDeskEntryReasonCodeV1, number>>;
  };
};

export type PaperDailyReportV1 = {
  schemaVersion: typeof PAPER_DAILY_REPORT_SCHEMA;
  accountId: string;
  asOf: string | null;
  dryRun: boolean;
  paperDExecute: boolean;
  blocked?: boolean;
  blockReason?: string | null;
  entry: PaperDailyReportEntryV1;
  /** V1.55 — DECISIONES / OPERATIVA / RESULTADO / NO OPERADAS */
  sections?: PaperDailyReportSectionsV1;
  /** V1.54 — hechos de excepción para proyección Desk (opcional). */
  exceptionFacts?: DailyDeskExceptionFactV1[];
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
  "data_unavailable",
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
    sections: buildPaperDailyReportSections(cycle, {
      protected: protectedCount,
      reduced,
      exited,
    }),
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

export function buildPaperDailyReportSections(
  cycle: PaperDeskCycleLikeV1,
  counts: { protected: number; reduced: number; exited: number },
): PaperDailyReportSectionsV1 {
  const proposed = cycle.entry.proposedCount ?? 0;
  const executed = cycle.entry.executedCount ?? 0;
  const skippedReasons: Partial<Record<PaperDeskEntryReasonCodeV1, number>> =
    {};
  let trails = 0;
  for (const row of cycle.positions) {
    if (row.decisionAction === "TRAIL" || row.decisionVerdict === "TRAIL") {
      trails += 1;
    }
  }
  return {
    decisiones: {
      candidates: proposed,
      proposed,
      authorized: executed > 0 ? 1 : 0,
      executed,
    },
    operativa: {
      entries: executed,
      t1: counts.reduced,
      trails,
      exits: counts.exited,
    },
    resultado: {
      realizedR: null,
      dayPct: null,
    },
    noOperadas: {
      skipped: Math.max(0, proposed - executed),
      reasonCodes: skippedReasons,
    },
  };
}
