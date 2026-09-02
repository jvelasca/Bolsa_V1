/**
 * V1.82 — E2E mock HTTP helpers + routeBody (Playwright fulfill payloads).
 */
import type { Route } from "@playwright/test";
import {
  E2E_ACCOUNT_ID,
  E2E_ENTRY_ONLY_INSTRUMENT,
  E2E_INSTRUMENT_ID,
  E2E_MULTI_POSITION_INSTRUMENTS,
  E2E_SYMBOL,
  E2E_WORKSPACE_ID,
  mercadoMultiOpenPositions,
  mercadoOhlcvBars,
  mercadoOpenPosition,
  mercadoWorkspaceDocument,
  applyGoldenPositionStage,
  buildLifecycleSnapshot,
  lifecycleDailyOpsEnvelope,
  lifecycleDecisionStudy,
  lifecycleJournalEntry,
  paperAutonomousDayDailyOpsEnvelope,
  paperAutonomousDayT1Position,
  staleNoExecuteDailyOpsEnvelope,
  staleNoExecuteOpenIncident,
  unknownOrderSubmitIntent,
} from "../integration";
import {
  getE2eMockRuntime,
  getMercadoMockWorkspaceDocument,
} from "./e2e-mock-runtime";

const demoAccount = {
  id: E2E_ACCOUNT_ID,
  userId: "e2e-user",
  name: "E2E Demo",
  description: null,
  type: "simulated" as const,
  status: "active" as const,
  currency: "EUR",
  baseCurrency: "EUR",
  initialDeposit: 100_000,
  leverage: 1,
  marginCallLevelPct: null,
  isDefault: true,
  settings: null,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
  lastActivityAt: null,
};

export function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  };
}

function apiPath(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

function gateMark(mark = "UNAVAILABLE") {
  return { mark, need: 0 };
}

function mercadoInstrumentCatalog(multi: boolean) {
  if (multi) {
    return [
      ...E2E_MULTI_POSITION_INSTRUMENTS.map((row) => ({
        id: row.id,
        symbol: row.symbol,
        yahooSymbol: row.symbol,
        name: row.name,
        exchange: "NASDAQ",
        currency: "USD",
        isActive: true,
        meta: {
          barCount: 30,
          lastSync: "2026-08-30T00:00:00.000Z",
          lastClose: 102,
          changePct: 2,
        },
      })),
      {
        id: E2E_ENTRY_ONLY_INSTRUMENT.id,
        symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
        yahooSymbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
        name: E2E_ENTRY_ONLY_INSTRUMENT.name,
        exchange: "NASDAQ",
        currency: "USD",
        isActive: true,
        meta: {
          barCount: 30,
          lastSync: "2026-08-30T00:00:00.000Z",
          lastClose: 120,
          changePct: 1,
        },
      },
    ];
  }
  return [
    {
      id: E2E_INSTRUMENT_ID,
      symbol: E2E_SYMBOL,
      yahooSymbol: E2E_SYMBOL,
      name: "Apple E2E",
      exchange: "NASDAQ",
      currency: "USD",
      isActive: true,
      meta: {
        barCount: 30,
        lastSync: "2026-08-30T00:00:00.000Z",
        lastClose: 102,
        changePct: 2,
      },
    },
  ];
}

export type E2eMockRouteOpts = {
  mercado?: boolean;
  multi?: boolean;
  hoyDay?: boolean;
  /** V1.75 — separado de hoyDay; no contaminar Paper Day feliz. */
  hoyStale?: boolean;
  /** V1.76 — UNKNOWN order aislado (sin stale, sin incidente). */
  hoyUnknown?: boolean;
};

export function routeBody(
  route: Route,
  opts?: E2eMockRouteOpts,
): Record<string, unknown> {
  const e2eMockRuntime = getE2eMockRuntime();
  const path = apiPath(route.request().url());
  const lifecycleDesk =
    e2eMockRuntime.deskMode === "lifecycle" ||
    e2eMockRuntime.deskMode === "lifecycle_stale";
  const lifecycleStale = e2eMockRuntime.deskMode === "lifecycle_stale";
  const hoyStale =
    opts?.hoyStale === true || e2eMockRuntime.deskMode === "stale";
  const hoyUnknown = opts?.hoyUnknown === true;
  const hoyDay = opts?.hoyDay === true || e2eMockRuntime.deskMode === "day";
  const mercado =
    opts?.mercado === true ||
    hoyDay === true ||
    hoyStale === true ||
    hoyUnknown === true ||
    lifecycleDesk;
  const multi = opts?.multi === true && !lifecycleDesk;
  const deskDay = hoyDay || hoyStale || hoyUnknown;
  const deskHappy = hoyDay || hoyUnknown;

  if (path === "/api/auth/status") {
    return { data: { authEnabled: false, authenticated: false } };
  }
  if (path === "/api/auth/logout") {
    return { data: { ok: true } };
  }
  if (path === "/api/health") {
    return { data: { status: "ok" } };
  }
  if (path === "/api/accounts") {
    return { data: [demoAccount] };
  }
  if (path === "/api/portfolio") {
    const stage = e2eMockRuntime.positionStage;
    const lifecycleSnap = lifecycleDesk
      ? buildLifecycleSnapshot({
          stage,
          lineagePath: e2eMockRuntime.lineagePath,
        })
      : null;
    const lifecyclePositions =
      lifecycleSnap?.position != null ? [lifecycleSnap.position] : [];
    const positions = lifecycleDesk
      ? lifecyclePositions
      : deskDay
        ? [paperAutonomousDayT1Position()]
        : multi
          ? mercadoMultiOpenPositions().map((pos, index) =>
              index === 0
                ? applyGoldenPositionStage(
                    pos,
                    e2eMockRuntime.positionStage,
                    e2eMockRuntime.lineagePath,
                  )
                : pos,
            )
          : mercado
            ? [
                applyGoldenPositionStage(
                  mercadoOpenPosition(),
                  e2eMockRuntime.positionStage,
                  e2eMockRuntime.lineagePath,
                ),
              ]
            : [];
    const equity = lifecycleSnap
      ? lifecycleSnap.totalEquity
      : deskDay
        ? 101_060
        : multi
          ? 103_500
          : mercado
            ? 101_020
            : 100_000;
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        portfolio: {
          cash: lifecycleSnap?.cash ?? 100_000,
          totalEquity: equity,
        },
        positions,
      },
    };
  }
  if (path === "/api/lists") {
    if (deskDay || lifecycleDesk) {
      return {
        data: [
          {
            id: "estudio",
            name: "Estudio",
            description: "E2E estudio universe",
            kind: "estudio",
            instrumentIds: [
              E2E_INSTRUMENT_ID,
              "inst-msft",
              E2E_ENTRY_ONLY_INSTRUMENT.id,
            ],
          },
        ],
      };
    }
    return { data: [] };
  }
  if (path === "/api/lists/memberships") {
    return { data: {} };
  }
  if ((deskDay || lifecycleDesk) && path === "/api/lists/estudio") {
    return {
      data: {
        id: "estudio",
        name: "Estudio",
        instrumentIds: [
          E2E_INSTRUMENT_ID,
          "inst-msft",
          E2E_ENTRY_ONLY_INSTRUMENT.id,
        ],
      },
    };
  }
  if (path === "/api/workspaces") {
    if (mercado) {
      return {
        data: [
          {
            id: E2E_WORKSPACE_ID,
            name: "E2E Mercado",
            isDefault: true,
            updatedAt: "2026-09-02T12:00:00.000Z",
          },
        ],
      };
    }
    return { data: [] };
  }
  if (mercado && path.startsWith("/api/workspaces/")) {
    const doc = getMercadoMockWorkspaceDocument() ?? mercadoWorkspaceDocument();
    return {
      data: {
        id: doc.id || E2E_WORKSPACE_ID,
        name: doc.name ?? "E2E Mercado",
        isDefault: true,
        updatedAt: doc.updatedAt,
        document: { ...doc, id: doc.id || E2E_WORKSPACE_ID },
        dockLayout: null,
      },
    };
  }

  if (path === "/api/risk/ops-self-eval") {
    return {
      schemaVersion: "1.0.0",
      rule: "e2e-mock",
      accountId: E2E_ACCOUNT_ID,
      lookbackDays: 120,
      lanes: {
        semi: {
          mark: "UNAVAILABLE",
          confirmSeed: null,
          journalSeed: null,
          buysSeed: null,
          tradeLike: null,
        },
        auto: {
          mark: "UNAVAILABLE",
          paperDExecuteEnv: false,
          executeOptIn: false,
          strictAcceptReady: false,
          p1: { daysWithOpinions: null, ...gateMark() },
          p2: { confirmSeed: null, ...gateMark() },
          p3: {
            buyPrecision5d: null,
            alarmaBuyCount: null,
            matureBuySample: null,
            ...gateMark(),
          },
          p4: { buyRecall5d: null, ...gateMark() },
          p5: {
            tradeLike: null,
            cashMaxDdFrac: null,
            note: null,
            ...gateMark(),
          },
        },
      },
      runtime: {
        killSwitchEffective: false,
        brokerVenue: "paper",
        accountVenuePreference: null,
        paperDExecuteEnv: false,
        confirmPathHonesty: "e2e-mock",
      },
      portfolioReconciliation: { status: e2eMockRuntime.reconStatus },
      operationalReadiness: {
        state: "PAPER_READY",
        venue: "paper",
        reasons: [],
        notes: [],
        rule: "e2e-mock",
      },
    };
  }
  if (path.endsWith("/decision-board")) {
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        generatedAt: "2026-09-01T12:00:00.000Z",
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
          total: 0,
        },
        semiF3Queue: [],
        decisionSessions: [],
      },
    };
  }
  if (path.endsWith("/operational-incidents/active")) {
    if (hoyStale) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          incidents: [staleNoExecuteOpenIncident()],
          total: 1,
        },
      };
    }
    return {
      data: { accountId: E2E_ACCOUNT_ID, incidents: [], total: 0 },
    };
  }
  if (path === "/api/paper-desk/daily-report") {
    if (lifecycleDesk) {
      const snap = buildLifecycleSnapshot({
        stage: e2eMockRuntime.positionStage,
        lineagePath: e2eMockRuntime.lineagePath,
      });
      return {
        data: lifecycleDailyOpsEnvelope(E2E_ACCOUNT_ID, lifecycleStale, snap),
      };
    }
    if (hoyStale) {
      return { data: staleNoExecuteDailyOpsEnvelope(E2E_ACCOUNT_ID) };
    }
    if (deskHappy) {
      return { data: paperAutonomousDayDailyOpsEnvelope(E2E_ACCOUNT_ID) };
    }
    return { data: { autoDesk: null } };
  }
  if (path.endsWith("/summary")) {
    const lifecycleSnap = lifecycleDesk
      ? buildLifecycleSnapshot({
          stage: e2eMockRuntime.positionStage,
          lineagePath: e2eMockRuntime.lineagePath,
        })
      : null;
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        cash: lifecycleSnap?.cash ?? 100_000,
        totalEquity: lifecycleSnap
          ? lifecycleSnap.totalEquity
          : deskDay
            ? 101_060
            : 100_000,
        openPositions: lifecycleSnap
          ? lifecycleSnap.openPositions
          : deskDay
            ? 1
            : 0,
        dayPnl: lifecycleSnap ? lifecycleSnap.dayPnl : deskDay ? 60 : 0,
        dayPnlPct: lifecycleSnap ? lifecycleSnap.dayPnlPct : deskDay ? 0.06 : 0,
      },
    };
  }
  if (path.endsWith("/decision-studies")) {
    if (lifecycleDesk) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          studies: [lifecycleDecisionStudy()],
          total: 1,
          limit: 200,
          offset: 0,
        },
      };
    }
    if (hoyStale) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          studies: [
            {
              decisionId: "dec-e2e-msft-stale",
              instrumentId: "inst-msft",
              symbol: "MSFT",
              hasOperationalPlan: true,
              tradePlanStatus: "ARMED",
              studiedAt: "2026-09-02T09:00:00.000Z",
              entry: 420,
              stop: 400,
              target1: 440,
              target2: 460,
            },
            {
              decisionId: "dec-e2e-nvda-stale",
              instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
              symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
              hasOperationalPlan: true,
              tradePlanStatus: "ARMED",
              studiedAt: "2026-09-02T09:00:00.000Z",
              entry: 118,
              stop: 110,
              target1: 130,
              target2: 140,
            },
          ],
          total: 2,
          limit: 200,
          offset: 0,
        },
      };
    }
    if (deskHappy) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          studies: [
            {
              decisionId: "dec-e2e-msft-day",
              instrumentId: "inst-msft",
              symbol: "MSFT",
              hasOperationalPlan: true,
              tradePlanStatus: "ARMED",
              studiedAt: "2026-09-02T09:00:00.000Z",
              entry: 420,
              stop: 400,
              target1: 440,
              target2: 460,
            },
          ],
          total: 1,
          limit: 200,
          offset: 0,
        },
      };
    }
    if (multi) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          studies: [
            {
              decisionId: "dec-e2e-nvda",
              instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
              symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
              hasOperationalPlan: true,
              tradePlanStatus: "ARMED",
              studiedAt: "2026-09-02T09:00:00.000Z",
              entry: 118,
              stop: 110,
              target1: 130,
              target2: 140,
            },
          ],
          total: 1,
          limit: 200,
          offset: 0,
        },
      };
    }
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        studies: [],
        total: 0,
        limit: 200,
        offset: 0,
      },
    };
  }
  if (path.endsWith("/decision-journal")) {
    if (lifecycleDesk) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          entries: [
            lifecycleJournalEntry(e2eMockRuntime.positionStage === "closed"),
          ],
          limit: 50,
          offset: 0,
          total: 1,
        },
      };
    }
    if (deskDay) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          entries: [
            {
              id: "journal-e2e-stale-1",
              decisionId: hoyStale ? "dec-e2e-msft-stale" : "dec-e2e-msft-day",
              instrumentId: "inst-msft",
              symbol: "MSFT",
              studiedAt: "2026-09-02T09:00:00.000Z",
              headline: hoyStale
                ? "ENTRY_STALE_DATA — no execute"
                : "Plan armado — dryRun",
              status: "studied",
            },
          ],
          limit: 50,
          offset: 0,
          total: 1,
        },
      };
    }
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        entries: [],
        limit: 50,
        offset: 0,
        total: 0,
      },
    };
  }
  if (path.endsWith("/submit-intents")) {
    if (hoyUnknown || e2eMockRuntime.unknownOrder) {
      return {
        data: {
          accountId: E2E_ACCOUNT_ID,
          intents: [unknownOrderSubmitIntent()],
          total: 1,
        },
      };
    }
    return {
      data: { accountId: E2E_ACCOUNT_ID, intents: [], total: 0 },
    };
  }
  if (path.includes("/instrument-daily-opinions/auto-telemetry")) {
    return { data: null };
  }
  if (path === "/api/risk/kill-switch") {
    return { data: { enabled: false } };
  }
  if (path === "/api/risk/broker-venue") {
    return { data: { venue: "paper" } };
  }
  if (path === "/api/ai/status") {
    return {
      data: {
        preferredProvider: "none",
        ollamaAvailable: false,
        openaiAvailable: false,
        callsRecorded: 0,
        mode: "off",
        auditSink: "none",
        producerVersion: "e2e",
      },
    };
  }
  if (path === "/api/scans/jobs") {
    return { data: [] };
  }
  if (path === "/api/alerts") {
    return { data: [] };
  }
  if (path === "/api/signal-alerts") {
    return { data: [] };
  }
  if (path === "/api/instruments") {
    if (multi || deskDay || lifecycleDesk) {
      return { data: mercadoInstrumentCatalog(true) };
    }
    if (mercado) {
      return { data: mercadoInstrumentCatalog(false) };
    }
    return { data: [] };
  }
  if (
    (mercado || multi || deskDay || lifecycleDesk) &&
    path === "/api/instruments/quotes"
  ) {
    return {
      data: mercadoInstrumentCatalog(multi || deskDay || lifecycleDesk),
    };
  }
  if (
    (mercado || multi || hoyStale || lifecycleDesk) &&
    path.endsWith("/ohlcv")
  ) {
    const bars = mercadoOhlcvBars();
    return {
      data: bars,
      meta: { timeframe: "1d", count: bars.length },
    };
  }
  if ((mercado || multi || hoyStale) && path.endsWith("/sync")) {
    return {
      data: {
        synced: true,
        barCount: 30,
        lastBarDate: "2026-08-30",
      },
    };
  }
  if (
    (mercado || multi || hoyStale) &&
    path.match(/\/api\/instruments\/[^/]+$/) &&
    path !== "/api/instruments/quotes"
  ) {
    const id = path.split("/").pop() ?? E2E_INSTRUMENT_ID;
    const known = [
      ...E2E_MULTI_POSITION_INSTRUMENTS,
      E2E_ENTRY_ONLY_INSTRUMENT,
      { id: E2E_INSTRUMENT_ID, symbol: E2E_SYMBOL, name: "Apple E2E" },
      { id: "inst-msft", symbol: "MSFT", name: "Microsoft E2E" },
    ].find((row) => row.id === id);
    return {
      data: {
        id: known?.id ?? id,
        symbol: known?.symbol ?? E2E_SYMBOL,
        name: known?.name ?? "Apple E2E",
        exchange: "NASDAQ",
        currency: "USD",
      },
    };
  }
  if ((mercado || multi || hoyStale) && path.endsWith("/strategy-top")) {
    return { data: null };
  }
  if ((mercado || multi || hoyStale) && path.endsWith("/indicators")) {
    return {
      data: [],
      meta: { timeframe: "1d", count: 0, indicators: [] },
    };
  }
  if (
    (mercado || multi || hoyStale) &&
    path.includes("/instrument-daily-opinions")
  ) {
    return { data: [] };
  }
  if ((mercado || multi) && path.endsWith("/data-status")) {
    const segments = path.split("/").filter(Boolean);
    const requestedId =
      segments.length >= 2
        ? (segments[segments.length - 2] ?? E2E_INSTRUMENT_ID)
        : E2E_INSTRUMENT_ID;
    const stale =
      hoyStale || lifecycleStale || e2eMockRuntime.dataFreshness === "stale";
    return {
      data: {
        instrumentId: requestedId,
        timeframe: "1d",
        freshnessStatus: stale ? "stale" : "current",
        barCount: 30,
        lastBarDate: "2026-08-30",
      },
    };
  }
  if (path === "/api/features/catalog") {
    return { data: { features: [] } };
  }

  return { data: [] };
}
