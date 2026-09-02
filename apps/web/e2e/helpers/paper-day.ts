/**
 * Paper Day / Hoy mock envelopes (V1.74).
 */
import type { Page } from "@playwright/test";
import { buildPaperDailyReport } from "@bolsa/shared";
import {
  E2E_ACCOUNT_ID,
  E2E_ENTRY_ONLY_INSTRUMENT,
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  E2E_WORKSPACE_ID,
  type MercadoLevels,
} from "./ids";
import {
  chartPersistBackupFromWorkspace,
  mercadoListFocusWorkspaceDocument,
  mercadoOpenPosition,
} from "./mercado";

/** Seed cuenta activa antes de navegar a /mesa. */
export async function seedHoyBrowserState(
  page: Page,
  opts?: { accountId?: string },
): Promise<void> {
  const accountId = opts?.accountId ?? E2E_ACCOUNT_ID;
  await page.addInitScript(
    ({ accountId }) => {
      localStorage.setItem(
        "bolsa-active-account",
        JSON.stringify({ state: { activeAccountId: accountId }, version: 0 }),
      );
    },
    { accountId },
  );
}

/** Posición AAPL con T1 alcanzado (lastPrice ≥ target1) para día autónomo mock. */
export function paperAutonomousDayT1Position() {
  const avgCost = 100;
  const target1 = 105;
  return mercadoOpenPosition({
    id: "pos-e2e-day-aapl",
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    name: "Apple E2E",
    tradePlanId: "tp-e2e-day-aapl",
    avgCost,
    lastPrice: target1 + 1,
    currentStop: 95,
    target1,
    target2: 110,
  });
}

export type PaperAutonomousDaySlice = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  tradePlanId: string;
  levels: MercadoLevels;
};

/** Identidad activa del día mock (AAPL T1). */
export function paperAutonomousDaySlice(): PaperAutonomousDaySlice {
  const pos = paperAutonomousDayT1Position();
  return {
    instrumentId: pos.instrumentId,
    symbol: pos.symbol,
    positionId: pos.operational.operationalView.positionId,
    tradePlanId: pos.operational.tradePlanId,
    levels: pos.operational.operationalView.levels,
  };
}

/** autoDesk V1.74 — Estudio→ranking→TradePlan→OpeningGate (dryRun, sin execute). */
export function paperAutonomousDayAutoDesk(accountId = E2E_ACCOUNT_ID) {
  const candidates = [
    {
      decisionId: "dec-e2e-msft-day",
      instrumentId: "inst-msft",
      rank: 1,
      score: 8.2,
      symbol: "MSFT",
      autoSource: "estudio_ranking",
      templateId: "moderate",
      tradePlan: {
        decisionId: "dec-e2e-msft-day",
        instrumentId: "inst-msft",
        direction: "long" as const,
        status: "ARMED" as const,
        quantity: 10,
        riskPct: 0.5,
        whyNot: [],
        executionAllowed: true,
        entry: 420,
        structuralStop: 400,
        target1: 440,
        target2: 460,
      },
      entry: 420,
      structuralStop: 400,
      target1: 440,
      target2: 460,
    },
    {
      decisionId: "dec-e2e-nvda-skip",
      instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
      rank: 2,
      score: 7.1,
      symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
      reasonCode: "ENTRY_NO_TRIGGER" as const,
      humanMessage: "Sin disparador — ranking ≠ BUY.",
      tradePlan: {
        decisionId: "dec-e2e-nvda-skip",
        instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
        direction: "long" as const,
        status: "ARMED" as const,
        quantity: 5,
        riskPct: 0.5,
        whyNot: ["no_trigger"],
        executionAllowed: false,
        entry: 118,
        structuralStop: 110,
        target1: 130,
        target2: 140,
      },
    },
  ];

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
        decisionVerdict: "REDUCE",
        nextAction: "REDUCE",
        operatingState: "T1_READY",
      },
    ],
    notes: [
      "dryRun=true — cadena Estudio→ranking→TradePlan→OpeningGate (E2E V1.74).",
      "AUTO armado · PAPER_D_EXECUTE off — sin ejecución ledger.",
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

/** DailyOps envelope mínimo para GET /paper-desk/daily-report mock. */
export function paperAutonomousDayDailyOpsEnvelope(accountId = E2E_ACCOUNT_ID) {
  const autoDesk = paperAutonomousDayAutoDesk(accountId);
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
    estudioCount: 3,
    autoDesk,
  };
}

/** Seed Hoy + AUTO armado + workspace Mercado (AAPL) para journey día mock. */
export async function seedPaperDayBrowserState(
  page: Page,
  opts?: {
    accountId?: string;
    workspaceDocument?: ReturnType<typeof mercadoListFocusWorkspaceDocument>;
  },
): Promise<void> {
  const accountId = opts?.accountId ?? E2E_ACCOUNT_ID;
  const slice = paperAutonomousDaySlice();
  const workspaceDocument =
    opts?.workspaceDocument ??
    mercadoListFocusWorkspaceDocument({
      instrumentId: slice.instrumentId,
      symbol: slice.symbol,
      name: "E2E Paper Day",
    });
  const workspaceId = workspaceDocument.id || E2E_WORKSPACE_ID;
  const chartPersistBackup = chartPersistBackupFromWorkspace(workspaceDocument);

  await page.addInitScript(
    ({ accountId, workspaceId, chartPersistBackup, workspaceDocument }) => {
      localStorage.setItem(
        "bolsa-active-account",
        JSON.stringify({ state: { activeAccountId: accountId }, version: 0 }),
      );
      localStorage.setItem(
        "bolsa-demo-book-auto-arm-v1",
        JSON.stringify({
          armed: true,
          armedAt: "2026-09-02T08:00:00.000Z",
          confirmPhrase: "ACTIVAR AUTO",
        }),
      );
      localStorage.setItem(
        "bolsa-demo-book-prefs-v1",
        JSON.stringify({
          mode: "auto",
          maxOpenPositions: 10,
          defaultSizePctOfCash: 10,
          countryPrefer: "home_first",
        }),
      );
      localStorage.setItem(
        "bolsa-mercado-decision-surface-v1",
        JSON.stringify({ placement: "panel" }),
      );
      localStorage.setItem(
        "bolsa-workspace-meta",
        JSON.stringify({
          state: {
            activeWorkspaceId: workspaceId,
            recents: [workspaceId],
            chartPersistBackup,
          },
          version: 0,
        }),
      );
      localStorage.setItem(
        "bolsa-trading-layout-v1",
        JSON.stringify({
          state: {
            operativaOpen: true,
            chartsOpen: true,
            operativaSections: {
              recommendation: false,
              info: true,
              config: true,
            },
            operativaSectionHeights: {
              recommendation: 320,
              info: 200,
              config: 180,
            },
            namedLayoutId: "trader",
          },
          version: 0,
        }),
      );
      void workspaceDocument;
    },
    { accountId, workspaceId, chartPersistBackup, workspaceDocument },
  );
}
