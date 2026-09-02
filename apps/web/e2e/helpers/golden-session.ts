/**
 * V1.78 golden stages + V1.79 stateful lifecycle + V1.81 T2 POV + V1.83 snapshot adapters.
 */
import { buildPaperDailyReport } from "@bolsa/shared";
import {
  E2E_ACCOUNT_ID,
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_SYMBOL,
  type MercadoInstrumentSlice,
} from "./ids";
import {
  applyGoldenPositionStage,
  LIFECYCLE_CASH,
  lifecycleOpenPosition,
  type LifecycleAccountSnapshot,
} from "./lifecycle-snapshot";

export function lifecycleInstrumentSlice(): MercadoInstrumentSlice {
  const pos = applyGoldenPositionStage(lifecycleOpenPosition(), "open");
  return {
    instrumentId: pos.instrumentId,
    symbol: pos.symbol,
    positionId: pos.operational.operationalView.positionId,
    tradePlanId: pos.operational.tradePlanId,
    decisionId: pos.operational.operationalView.decisionId,
    levels: pos.operational.operationalView.levels,
  };
}

function lifecycleAaplCandidate(stale: boolean) {
  return {
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    rank: 1,
    score: 8.2,
    symbol: E2E_SYMBOL,
    autoSource: "estudio_ranking",
    templateId: "moderate",
    freshness: stale ? ("stale" as const) : ("current" as const),
    reasonCode: stale ? ("ENTRY_STALE_DATA" as const) : undefined,
    humanMessage: stale ? "Datos obsoletos — no proponer." : undefined,
    vetoes: stale ? ["data_freshness:stale"] : undefined,
    tradePlan: {
      decisionId: E2E_LIFECYCLE_DECISION_ID,
      instrumentId: E2E_INSTRUMENT_ID,
      direction: "long" as const,
      status: "ARMED" as const,
      quantity: 10,
      riskPct: 0.5,
      whyNot: [],
      executionAllowed: !stale,
      entry: 100,
      structuralStop: 95,
      target1: 105,
      target2: 110,
    },
    entry: 100,
    structuralStop: 95,
    target1: 105,
    target2: 110,
  };
}

export function lifecycleAutoDesk(accountId = E2E_ACCOUNT_ID, stale = false) {
  const candidates = [lifecycleAaplCandidate(stale)];
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
    positions: [],
    notes: [
      "dryRun=true — V1.79 lifecycle AAPL.",
      stale
        ? "ENTRY_STALE_DATA · PAPER_D_EXECUTE off."
        : "AUTO armado · PAPER_D_EXECUTE off — sin ejecución ledger.",
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

export function lifecycleDailyOpsEnvelope(
  accountId = E2E_ACCOUNT_ID,
  stale = false,
  account?: Pick<
    LifecycleAccountSnapshot,
    "cash" | "totalEquity" | "openPositions" | "dayPnl" | "dayPnlPct"
  >,
) {
  const autoDesk = lifecycleAutoDesk(accountId, stale);
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-09-02",
    generatedAt: "2026-09-02T12:00:00.000Z",
    accountId,
    summary: {
      accountId,
      cash: account?.cash ?? LIFECYCLE_CASH,
      totalEquity: account?.totalEquity ?? LIFECYCLE_CASH,
      openPositions: account?.openPositions ?? 0,
      dayPnl: account?.dayPnl ?? 0,
      dayPnlPct: account?.dayPnlPct ?? 0,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [],
    f3PendingCount: 0,
    channels: { alarma: 0, aviso: 0, none: 0 },
    opinions: [],
    notes: autoDesk.notes,
    estudioStatus: "ok",
    estudioCount: 1,
    autoDesk,
  };
}

export function lifecycleDecisionStudy() {
  return {
    sessionId: "sess-e2e-lifecycle-1",
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    hasOperationalPlan: true,
    tradePlanStatus: "ARMED",
    studiedAt: "2026-09-02T09:00:00.000Z",
    entry: 100,
    stop: 95,
    target1: 105,
    target2: 110,
  };
}

export function lifecycleJournalEntry(closed: boolean) {
  return {
    id: "journal-e2e-lifecycle-1",
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    studiedAt: "2026-09-02T09:00:00.000Z",
    headline: closed
      ? "POSITION_CLOSED — remainingQuantity=0"
      : "Plan armado — dryRun",
    status: closed ? "closed" : "studied",
  };
}
