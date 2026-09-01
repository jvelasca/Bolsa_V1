import type { Page, Route } from "@playwright/test";
import {
  E2E_ACCOUNT_ID,
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  E2E_WORKSPACE_ID,
  mercadoOhlcvBars,
  mercadoOpenPosition,
  mercadoWorkspaceDocument,
} from "./integration";

/** True when E2E should run (auto webServer or explicit base URL). */
export function e2eEnabled(): boolean {
  return (
    process.env.E2E_RUN === "1" ||
    Boolean(process.env.PLAYWRIGHT_BASE_URL?.trim())
  );
}

export const E2E_SKIP_REASON =
  "Set E2E_RUN=1 (starts Vite + API mocks) or PLAYWRIGHT_BASE_URL (existing server). See e2e/*.spec.ts headers.";

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

function jsonResponse(body: unknown, status = 200) {
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

function routeBody(
  route: Route,
  opts?: { mercado?: boolean },
): Record<string, unknown> {
  const path = apiPath(route.request().url());
  const mercado = opts?.mercado === true;

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
    return {
      data: {
        accountId: E2E_ACCOUNT_ID,
        portfolio: {
          cash: 100_000,
          totalEquity: mercado ? 101_020 : 100_000,
        },
        positions: mercado ? [mercadoOpenPosition()] : [],
      },
    };
  }
  if (path === "/api/lists") {
    return { data: [] };
  }
  if (path === "/api/lists/memberships") {
    return { data: {} };
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
    const doc = mercadoWorkspaceDocument();
    return {
      data: {
        id: E2E_WORKSPACE_ID,
        name: "E2E Mercado",
        isDefault: true,
        updatedAt: doc.updatedAt,
        document: doc,
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
      portfolioReconciliation: { status: "ok" },
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
    return {
      data: { accountId: E2E_ACCOUNT_ID, incidents: [], total: 0 },
    };
  }
  if (path.endsWith("/decision-studies")) {
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
    if (mercado) {
      return {
        data: [
          {
            id: E2E_INSTRUMENT_ID,
            symbol: E2E_SYMBOL,
            name: "Apple E2E",
            exchange: "NASDAQ",
            currency: "USD",
          },
        ],
      };
    }
    return { data: [] };
  }
  if (mercado && path.endsWith("/ohlcv")) {
    const bars = mercadoOhlcvBars();
    return {
      data: bars,
      meta: { timeframe: "1d", count: bars.length },
    };
  }
  if (mercado && path.match(/\/api\/instruments\/[^/]+$/)) {
    return {
      data: {
        id: E2E_INSTRUMENT_ID,
        symbol: E2E_SYMBOL,
        name: "Apple E2E",
        exchange: "NASDAQ",
        currency: "USD",
      },
    };
  }
  if (mercado && path.endsWith("/strategy-top")) {
    return { data: null };
  }
  if (mercado && path.endsWith("/indicators")) {
    return {
      data: [],
      meta: { timeframe: "1d", count: 0, indicators: [] },
    };
  }
  if (mercado && path.includes("/instrument-daily-opinions")) {
    return { data: [] };
  }
  if (mercado && path.endsWith("/data-status")) {
    return {
      data: {
        instrumentId: E2E_INSTRUMENT_ID,
        timeframe: "1d",
        freshnessStatus: "current",
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

/** Intercept /api/* so smoke tests run without the Python stack. */
export async function installApiMocks(
  page: Page,
  opts?: { mercado?: boolean },
): Promise<void> {
  await page.route(/\/api\//, async (route) => {
    await route.fulfill(jsonResponse(routeBody(route, opts)));
  });
}

/** Mercado DECISIÓN + gráfico con posición protegida (GP-E2E-03 / GP-V164-UI-03 mock). */
export async function installMercadoApiMocks(page: Page): Promise<void> {
  await installApiMocks(page, { mercado: true });
}
