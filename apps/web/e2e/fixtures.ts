import type { Page, Route } from "@playwright/test";

/** True when E2E should run (auto webServer or explicit base URL). */
export function e2eEnabled(): boolean {
  return (
    process.env.E2E_RUN === "1" ||
    Boolean(process.env.PLAYWRIGHT_BASE_URL?.trim())
  );
}

export const E2E_SKIP_REASON =
  "Set E2E_RUN=1 (starts Vite + API mocks) or PLAYWRIGHT_BASE_URL (existing server). See e2e/*.spec.ts headers.";

const E2E_ACCOUNT_ID = "default-account-seed";

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

function routeBody(route: Route): Record<string, unknown> {
  const path = apiPath(route.request().url());

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
        positions: [],
        cash: 100_000,
        totalEquity: 100_000,
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
    return { data: [] };
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
    return { data: [] };
  }
  if (path === "/api/features/catalog") {
    return { data: { features: [] } };
  }

  return { data: [] };
}

/** Intercept /api/* so smoke tests run without the Python stack. */
export async function installApiMocks(page: Page): Promise<void> {
  await page.route(/\/api\//, async (route) => {
    await route.fulfill(jsonResponse(routeBody(route)));
  });
}
