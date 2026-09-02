/**
 * Stale deny + UNKNOWN order mock fixtures (V1.75 / V1.76).
 */
import type { Page } from "@playwright/test";
import { buildPaperDailyReport } from "@bolsa/shared";
import { E2E_ACCOUNT_ID, E2E_INSTRUMENT_ID, E2E_SYMBOL } from "./ids";
import { mercadoListFocusWorkspaceDocument } from "./mercado";
import { seedPaperDayBrowserState } from "./paper-day";

/** V1.75 — candidato ENTRY_STALE_DATA (deny honesto ≠ 0 oportunidades silenciosas). */
export function staleNoExecuteStaleCandidate() {
  return {
    decisionId: "dec-e2e-msft-stale",
    instrumentId: "inst-msft",
    rank: 1,
    score: 8.2,
    symbol: "MSFT",
    autoSource: "estudio_ranking",
    templateId: "moderate",
    freshness: "stale" as const,
    reasonCode: "ENTRY_STALE_DATA" as const,
    humanMessage: "Datos obsoletos — no proponer.",
    vetoes: ["data_freshness:stale"],
    tradePlan: {
      decisionId: "dec-e2e-msft-stale",
      instrumentId: "inst-msft",
      direction: "long" as const,
      status: "ARMED" as const,
      quantity: 10,
      riskPct: 0.5,
      whyNot: [],
      executionAllowed: false,
      entry: 420,
      structuralStop: 400,
      target1: 440,
      target2: 460,
    },
    entry: 420,
    structuralStop: 400,
    target1: 440,
    target2: 460,
  };
}

/** autoDesk V1.75 — stale deny + dryRun · sin execute. */
export function staleNoExecuteAutoDesk(accountId = E2E_ACCOUNT_ID) {
  const candidates = [staleNoExecuteStaleCandidate()];
  const base = buildPaperDailyReport({
    accountId,
    asOf: "2026-09-02",
    dryRun: true,
    paperDExecute: false,
    entry: {
      status: "dry_run",
      proposedCount: candidates.length,
      executedCount: 0,
    },
    positions: [
      {
        instrumentId: E2E_INSTRUMENT_ID,
        status: "held",
        reason: "data_stale",
        decisionVerdict: "HOLD",
        nextAction: "REVISAR_DATOS_NO_FRESCOS",
        operatingState: "OPEN",
      },
    ],
    notes: [
      "dryRun=true — V1.75 stale → no-execute.",
      "ENTRY_STALE_DATA · PAPER_D_EXECUTE off.",
    ],
  });

  return {
    ...base,
    entry: {
      ...base.entry,
      candidates,
      skipped: [],
    },
  };
}

/** DailyOps envelope mock para GET /paper-desk/daily-report (stale). */
export function staleNoExecuteDailyOpsEnvelope(accountId = E2E_ACCOUNT_ID) {
  const autoDesk = staleNoExecuteAutoDesk(accountId);
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-09-02",
    generatedAt: "2026-09-02T12:00:00.000Z",
    accountId,
    summary: {
      accountId,
      cash: 100_000,
      totalEquity: 101_060,
      openPositions: 1,
      dayPnl: 60,
      dayPnlPct: 0.06,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [],
    f3PendingCount: 0,
    channels: { alarma: 0, aviso: 0, none: 0 },
    opinions: [],
    notes: autoDesk.notes,
    estudioStatus: "ok",
    estudioCount: 2,
    autoDesk,
  };
}

/** SubmitIntent send_attempted → ExecutionState UNKNOWN (OR-2). Isolated from stale. */
export function unknownOrderSubmitIntent(accountId = E2E_ACCOUNT_ID) {
  return {
    decisionId: "dec-e2e-aapl-unknown",
    intentId: "intent-e2e-aapl-unknown",
    orderId: "ord-unknown-001",
    accountId,
    phase: "send_attempted" as const,
    venueOrderId: null,
    reason: "crash_before_venue_ack",
    venue: "paper",
    sendAttemptedAt: "2026-09-02T11:55:00.000Z",
    instrumentId: E2E_INSTRUMENT_ID,
  };
}

/** @deprecated V1.76 — use unknownOrderSubmitIntent (isolated orderId). */
export function staleNoExecuteUnknownSubmitIntent(accountId = E2E_ACCOUNT_ID) {
  return unknownOrderSubmitIntent(accountId);
}

/** Incidente abierto — copy Sin auto-heal (DEX-3). */
export function staleNoExecuteOpenIncident(accountId = E2E_ACCOUNT_ID) {
  return {
    incidentId: "inc-e2e-stale-1",
    accountId,
    kind: "portfolio_drift",
    status: "open",
    snapshot: "portfolio_drift",
    openedAt: "2026-09-02T11:00:00.000Z",
    reviewedAt: null,
    reviewedBy: null,
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    clearedAt: null,
  };
}

/** Seed browser state para journey stale/UNKNOWN (reusa armado AUTO). */
export async function seedStaleNoExecuteBrowserState(
  page: Page,
  opts?: {
    accountId?: string;
    workspaceDocument?: ReturnType<typeof mercadoListFocusWorkspaceDocument>;
  },
): Promise<void> {
  await seedPaperDayBrowserState(page, {
    accountId: opts?.accountId,
    workspaceDocument:
      opts?.workspaceDocument ??
      mercadoListFocusWorkspaceDocument({
        instrumentId: E2E_INSTRUMENT_ID,
        symbol: E2E_SYMBOL,
        name: "E2E Stale No-Execute",
      }),
  });
}
