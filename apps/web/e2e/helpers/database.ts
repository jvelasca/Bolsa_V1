/**
 * Integrated E2E environment gates + HTTP seeds (V1.64+).
 */
import { randomUUID } from "node:crypto";
import type { APIRequestContext } from "@playwright/test";
import {
  E2E_HOY_ACCOUNT_PREFIX,
  E2E_INSTRUMENT_ID,
  E2E_MERCADO_ACCOUNT_PREFIX,
  E2E_MERCADO_MULTI_ACCOUNT_PREFIX,
  E2E_MULTI_POSITION_INSTRUMENTS,
} from "./ids";
import {
  mercadoListFocusWorkspaceDocument,
  mercadoWorkspaceDocument,
  sliceFromPortfolioPosition,
  type MercadoIntegrationFixture,
  type MultiInstrumentMercadoFixture,
  type PortfolioPositionRow,
} from "./mercado";

export function e2eIntegrationMode(): boolean {
  return process.env.E2E_INTEGRATION === "1";
}

export function e2eMockMode(): boolean {
  return !e2eIntegrationMode();
}

export const E2E_SKIP_INTEGRATION_REASON =
  "Set E2E_INTEGRATION=1 and ensure FastAPI (:8000) + PostgreSQL are running. See spec-v164.";

export const E2E_SKIP_DB_ISOLATION_REASON =
  "Set E2E_ALLOW_DEV_DB=1 to run integrated Mercado E2E against local PostgreSQL (creates ephemeral e2e-v167-* accounts). See spec-v167.";

/** Environment unavailable → SKIP. Fixture/product errors must FAIL. */
export async function gateIntegratedE2eEnvironment(
  request: APIRequestContext,
  baseURL: string | undefined,
  opts: { e2eEnabled: boolean; e2eSkipReason: string },
): Promise<string | null> {
  if (!opts.e2eEnabled) return opts.e2eSkipReason;
  if (!e2eIntegrationMode()) return E2E_SKIP_INTEGRATION_REASON;
  if (!baseURL) return "baseURL required";
  if (process.env.E2E_ALLOW_DEV_DB !== "1") return E2E_SKIP_DB_ISOLATION_REASON;
  try {
    await assertApiHealthy(request, baseURL);
  } catch (err) {
    return String(err);
  }
  return null;
}

/**
 * Fail-closed unless explicitly opted in. Integrated Mercado E2E mutates PG
 * (ephemeral accounts). Prefer `E2E_DATABASE_URL` pointing to a dedicated test DB.
 */
export function assertE2eDatabaseIsolation(): void {
  if (process.env.E2E_ALLOW_DEV_DB === "1") return;
  throw new Error(E2E_SKIP_DB_ISOLATION_REASON);
}

export async function assertApiHealthy(
  request: APIRequestContext,
  baseURL: string,
): Promise<void> {
  const healthUrl = new URL("/api/health", baseURL).toString();
  const res = await request.get(healthUrl);
  if (!res.ok()) {
    throw new Error(
      `API health check failed (${res.status()}). Start FastAPI + PostgreSQL before E2E_INTEGRATION=1.`,
    );
  }
}

/** Crea cuenta aislada, workspace con gráfico AAPL y buy opcional vía HTTP real. */
export async function ensureMercadoIntegrationFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<MercadoIntegrationFixture> {
  assertE2eDatabaseIsolation();

  const instrumentsRes = await request.get(
    new URL("/api/instruments", baseURL).toString(),
  );
  if (!instrumentsRes.ok()) {
    throw new Error(
      `GET /api/instruments failed (${instrumentsRes.status()}).`,
    );
  }
  const instruments = (await instrumentsRes.json()).data as Array<{
    id: string;
    symbol: string;
  }>;
  const instrument =
    instruments.find((row) => row.id === E2E_INSTRUMENT_ID) ?? instruments[0];
  if (!instrument) {
    throw new Error("No instruments available for Mercado E2E seed.");
  }

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_MERCADO_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 100_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts failed (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  const accountId = (await accountRes.json()).data.id as string;

  const now = new Date().toISOString();
  const mandateRes = await request.put(
    new URL(`/api/accounts/${accountId}/mandates`, baseURL).toString(),
    {
      data: {
        tenures: [
          {
            id: `mt-e2e-${suffix}`,
            accountId,
            instrumentId: instrument.id,
            effectiveFrom: now,
            actor: "user",
            reason: "adopt",
          },
        ],
        links: [],
      },
    },
  );
  if (!mandateRes.ok()) {
    throw new Error(
      `PUT mandates failed (${mandateRes.status()}): ${await mandateRes.text()}`,
    );
  }

  let hasOpenPosition = false;
  let positionId: string | null = null;
  let tradePlanId: string | null = null;
  let decisionId: string | null = null;
  let levels: MercadoIntegrationFixture["levels"] = null;
  const tradeRes = await request.post(
    new URL("/api/portfolio/trade", baseURL).toString(),
    {
      headers: { "X-Account-Id": accountId },
      data: {
        instrumentId: instrument.id,
        type: "buy",
        quantity: 5,
        price: 50,
        idempotencyKey: `e2e-v167-${suffix}`,
      },
    },
  );
  if (!tradeRes.ok()) {
    throw new Error(
      `POST /api/portfolio/trade failed (${tradeRes.status()}): ${await tradeRes.text()}. Open position seed is required.`,
    );
  }
  hasOpenPosition = true;
  const portfolioRes = await request.get(
    new URL("/api/portfolio", baseURL).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!portfolioRes.ok()) {
    throw new Error(
      `GET /api/portfolio after buy failed (${portfolioRes.status()}): ${await portfolioRes.text()}`,
    );
  }
  const portfolioJson = (await portfolioRes.json()) as {
    data?: { positions?: PortfolioPositionRow[] };
  };
  const seeded = portfolioJson.data?.positions?.find(
    (row) => row.instrumentId === instrument.id,
  );
  if (!seeded) {
    throw new Error(
      `Portfolio buy seed did not persist an open position for ${instrument.symbol}.`,
    );
  }
  positionId = seeded.operational?.operationalView?.positionId ?? seeded.id;
  tradePlanId =
    seeded.operational?.operationalView?.tradePlanId ??
    seeded.operational?.tradePlanId ??
    null;
  decisionId =
    seeded.operational?.operationalView?.decisionId ??
    seeded.operational?.decisionId ??
    null;
  const viewLevels = seeded.operational?.operationalView?.levels;
  levels = viewLevels
    ? {
        entry: viewLevels.entry ?? null,
        currentStop: viewLevels.currentStop ?? null,
        target1: viewLevels.target1 ?? null,
        target2: viewLevels.target2 ?? null,
      }
    : null;

  const workspaceDocument = mercadoWorkspaceDocument({
    instrumentId: instrument.id,
    symbol: instrument.symbol,
    name: `E2E Mercado ${suffix}`,
  });
  const workspaceRes = await request.post(
    new URL("/api/workspaces", baseURL).toString(),
    {
      data: {
        name: workspaceDocument.name,
        document: workspaceDocument,
        isDefault: false,
      },
    },
  );
  if (!workspaceRes.ok()) {
    throw new Error(
      `POST /api/workspaces failed (${workspaceRes.status()}): ${await workspaceRes.text()}`,
    );
  }
  const workspaceId = (await workspaceRes.json()).data.id as string;
  const workspaceDocumentWithId = {
    ...workspaceDocument,
    id: workspaceId,
  };

  return {
    accountId,
    instrumentId: instrument.id,
    symbol: instrument.symbol,
    workspaceId,
    hasOpenPosition,
    positionId,
    tradePlanId,
    decisionId,
    levels,
    workspaceDocument: workspaceDocumentWithId,
  };
}

/**
 * Cuenta aislada con ≥3 buys PAPER + mandato Entry-only (4º instrumento) si el catálogo lo permite.
 * FAIL-closed si hay menos de 3 instrumentos disponibles.
 */
export async function ensureMultiInstrumentMercadoFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<MultiInstrumentMercadoFixture> {
  assertE2eDatabaseIsolation();

  const instrumentsRes = await request.get(
    new URL("/api/instruments", baseURL).toString(),
  );
  if (!instrumentsRes.ok()) {
    throw new Error(
      `GET /api/instruments failed (${instrumentsRes.status()}).`,
    );
  }
  const catalog = (await instrumentsRes.json()).data as Array<{
    id: string;
    symbol: string;
  }>;
  if (catalog.length < 3) {
    throw new Error(
      `Multi-instrument Mercado E2E requires ≥3 instruments in catalog (got ${catalog.length}).`,
    );
  }

  const preferredIds = new Set(
    E2E_MULTI_POSITION_INSTRUMENTS.map((row) => row.id),
  );
  const preferred = catalog.filter((row) => preferredIds.has(row.id));
  const rest = catalog.filter((row) => !preferredIds.has(row.id));
  const ordered = [...preferred, ...rest];
  const buyTargets = ordered.slice(0, 3);
  const entryTarget = ordered.length >= 4 ? ordered[3]! : null;

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_MERCADO_MULTI_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 250_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts failed (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  const accountId = (await accountRes.json()).data.id as string;

  const now = new Date().toISOString();
  const mandateInstruments = entryTarget
    ? [...buyTargets, entryTarget]
    : buyTargets;
  const mandateRes = await request.put(
    new URL(`/api/accounts/${accountId}/mandates`, baseURL).toString(),
    {
      data: {
        tenures: mandateInstruments.map((instrument, index) => ({
          id: `mt-e2e-v173-${suffix}-${index}`,
          accountId,
          instrumentId: instrument.id,
          effectiveFrom: now,
          actor: "user",
          reason: "adopt",
        })),
        links: [],
      },
    },
  );
  if (!mandateRes.ok()) {
    throw new Error(
      `PUT mandates failed (${mandateRes.status()}): ${await mandateRes.text()}`,
    );
  }

  for (let i = 0; i < buyTargets.length; i++) {
    const instrument = buyTargets[i]!;
    const tradeRes = await request.post(
      new URL("/api/portfolio/trade", baseURL).toString(),
      {
        headers: { "X-Account-Id": accountId },
        data: {
          instrumentId: instrument.id,
          type: "buy",
          quantity: 5,
          price: 50 + i * 5,
          idempotencyKey: `e2e-v173-${suffix}-${i}`,
        },
      },
    );
    if (!tradeRes.ok()) {
      throw new Error(
        `POST /api/portfolio/trade failed for ${instrument.symbol} (${tradeRes.status()}): ${await tradeRes.text()}.`,
      );
    }
  }

  const portfolioRes = await request.get(
    new URL("/api/portfolio", baseURL).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!portfolioRes.ok()) {
    throw new Error(
      `GET /api/portfolio after buys failed (${portfolioRes.status()}): ${await portfolioRes.text()}`,
    );
  }
  const portfolioJson = (await portfolioRes.json()) as {
    data?: { positions?: PortfolioPositionRow[] };
  };
  const positions = portfolioJson.data?.positions ?? [];
  const instruments = buyTargets.map((target) => {
    const seeded = positions.find((row) => row.instrumentId === target.id);
    if (!seeded) {
      throw new Error(
        `Portfolio buy seed missing open position for ${target.symbol}.`,
      );
    }
    return sliceFromPortfolioPosition(seeded, target.symbol);
  });
  if (instruments.length < 3) {
    throw new Error(
      `Multi-instrument fixture expected ≥3 open positions (got ${instruments.length}).`,
    );
  }

  const workspaceDocument = mercadoListFocusWorkspaceDocument({
    instrumentId: instruments[0]!.instrumentId,
    symbol: instruments[0]!.symbol,
    name: `E2E Mercado Multi ${suffix}`,
  });
  const workspaceRes = await request.post(
    new URL("/api/workspaces", baseURL).toString(),
    {
      data: {
        name: workspaceDocument.name,
        document: workspaceDocument,
        isDefault: false,
      },
    },
  );
  if (!workspaceRes.ok()) {
    throw new Error(
      `POST /api/workspaces failed (${workspaceRes.status()}): ${await workspaceRes.text()}`,
    );
  }
  const workspaceId = (await workspaceRes.json()).data.id as string;

  return {
    accountId,
    workspaceId,
    instruments,
    entryOnly: entryTarget
      ? { instrumentId: entryTarget.id, symbol: entryTarget.symbol }
      : null,
    workspaceDocument: { ...workspaceDocument, id: workspaceId },
  };
}

export type HoyIntegrationFixture = {
  accountId: string;
  hasAutoDesk: boolean;
  entryProposed: number;
};

/** Cuenta aislada para Hoy / Paper Autonomous Desk E2E. */
export async function ensureHoyIntegrationFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<HoyIntegrationFixture> {
  assertE2eDatabaseIsolation();

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_HOY_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 100_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts failed (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  const accountId = (await accountRes.json()).data.id as string;

  const reportRes = await request.get(
    new URL(
      `/api/paper-desk/daily-report?accountId=${encodeURIComponent(accountId)}`,
      baseURL,
    ).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!reportRes.ok()) {
    throw new Error(
      `GET /paper-desk/daily-report failed (${reportRes.status()}): ${await reportRes.text()}`,
    );
  }
  const autoDesk = (await reportRes.json()).data?.autoDesk as
    | { entry?: { proposed?: number } }
    | undefined;

  return {
    accountId,
    hasAutoDesk: Boolean(autoDesk),
    entryProposed: autoDesk?.entry?.proposed ?? 0,
  };
}
