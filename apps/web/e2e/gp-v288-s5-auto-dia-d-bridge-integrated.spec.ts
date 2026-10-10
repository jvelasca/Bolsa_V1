/**
 * GP-V288-S5 — puente AUTO operación → estrategia #1 → verificación DÍA-D (integrado).
 *
 * Extiende el journey INTEGRADO (API real + PostgreSQL + navegador) al hueco que quedó
 * `skipped` en `v2.88.103`: desde la pantalla de operación AUTO, el CTA «Verificar D→hoy»
 * debe montar el host DÍA-D LAB (`dia-d-verify-host`) y **arrancar el run real** (película
 * D→hoy, `POST /api/backtests/run`). Hermano integrado del mock
 * `gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts` (mismos testids, sin mocks aquí).
 *
 * Precondición DURA (declarada, no fingida): para que exista una operación que verificar, el
 * monitor AUTO de la cuenta debe declarar ≥1 ciclo **durable** (reserva/fill con `cycleId`). El
 * ciclo lo produce el MOTOR AUTO (worker de simulación), que el harness E2E no arranca: con una
 * BD recién migrada/sembrada no hay ninguno y el journey del puente se declara `skipped` con
 * motivo explícito. La pantalla `/auto/operar` sí se certifica siempre (declara su hueco honesto:
 * «Sin operaciones en la ventana»), así que este spec NO es un skip total.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-v288-s5
 * Against an existing dev server (PLAYWRIGHT_BASE_URL):
 *   E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v288-s5
 *
 * Default (no env): skipped.
 */
import { randomUUID } from "node:crypto";
import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  gateIntegratedE2eEnvironment,
  seedHoyBrowserState,
} from "./integration";

/** Ciclo AUTO durable ausente: el motor (worker) no corre en el harness ⇒ hueco declarado. */
const NO_CYCLE_REASON =
  "Sin ciclo AUTO durable en la cuenta (el worker del motor AUTO no corre en el harness E2E). " +
  "Seedea ≥1 reserva/fill con cycleId para ejecutar el journey del puente.";

/** El ciclo existe pero su símbolo no está en el catálogo: no hay cadena de estrategia que probar. */
const NO_CHAIN_REASON =
  "El símbolo del ciclo AUTO no está en el catálogo /api/instruments: no se puede resolver la " +
  "estrategia #1 ni el UUID del instrumento para el deep-link DÍA-D.";

const MONITOR_PATH = "/api/auto/operational-monitor";
const RUN_PATH = "/api/backtests/run";
const PRESET_KEY = "sma_crossover";
const STRATEGY_LABEL = "E2E S5 · Cruce SMA 20/50";
const STRATEGY_REASON = "E2E S5 · razones del coach";

type MonitorCycle = {
  cycleId: string;
  instrumentId?: string | null;
};

type AutoBridgeFixture = {
  accountId: string;
  /** Ciclo durable que la UI debe mostrar como primera operación (o `null` = hueco). */
  cycleId: string | null;
  /** Símbolo (ticker) del ciclo — la identidad humana que resuelve el UUID. */
  cycleSymbol: string | null;
  /** UUID resuelto del instrumento; `null` si la cadena no se puede cerrar. */
  instrumentId: string | null;
  strategyDefinitionId: string | null;
  strategyLabel: string;
  /** Motivo del hueco (ciclo ausente), o `null` si hay ciclo. */
  noCycleReason: string | null;
  /** Motivo del hueco (símbolo del ciclo fuera del catálogo), o `null`. */
  noChainReason: string | null;
};

async function body<T>(res: { json(): Promise<unknown> }): Promise<T> {
  return (await res.json()) as T;
}

/**
 * Cuenta efímera + (si el monitor trae ciclo) estrategia #1 y su TOP de Finalistas REAL, para
 * que la cadena `operación → estrategia/indicadores → DÍA-D` sea verificable sin mocks.
 */
async function ensureAutoBridgeFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<AutoBridgeFixture> {
  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `e2e-v288-s5-${suffix}`,
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
  const accountId = (await body<{ data: { id: string } }>(accountRes)).data.id;

  const monitorRes = await request.get(
    new URL(`${MONITOR_PATH}?limit=20`, baseURL).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!monitorRes.ok()) {
    throw new Error(
      `GET ${MONITOR_PATH} failed (${monitorRes.status()}): ${await monitorRes.text()}`,
    );
  }
  const monitor = await body<{ cycles?: MonitorCycle[] }>(monitorRes);
  const cycle = (monitor.cycles ?? [])[0] ?? null;
  const cycleSymbol = cycle?.instrumentId?.trim() || null;

  if (!cycle || !cycleSymbol) {
    return {
      accountId,
      cycleId: null,
      cycleSymbol: null,
      instrumentId: null,
      strategyDefinitionId: null,
      strategyLabel: "",
      noCycleReason: NO_CYCLE_REASON,
      noChainReason: null,
    };
  }

  const instrumentsRes = await request.get(
    new URL("/api/instruments", baseURL).toString(),
  );
  if (!instrumentsRes.ok()) {
    throw new Error(
      `GET /api/instruments failed (${instrumentsRes.status()}).`,
    );
  }
  const catalog = await body<{
    data: Array<{ id: string; symbol: string }>;
  }>(instrumentsRes);
  const upper = cycleSymbol.toUpperCase();
  const instrument = (catalog.data ?? []).find(
    (row) => row.symbol?.toUpperCase() === upper,
  );
  if (!instrument) {
    return {
      accountId,
      cycleId: cycle.cycleId,
      cycleSymbol,
      instrumentId: null,
      strategyDefinitionId: null,
      strategyLabel: "",
      noCycleReason: null,
      noChainReason: NO_CHAIN_REASON,
    };
  }

  const strategyRes = await request.post(
    new URL("/api/strategies/from-preset", baseURL).toString(),
    {
      data: {
        name: `E2E S5 ${suffix}`,
        presetKey: PRESET_KEY,
        timeframe: "1d",
      },
    },
  );
  if (!strategyRes.ok()) {
    throw new Error(
      `POST /api/strategies/from-preset failed (${strategyRes.status()}): ${await strategyRes.text()}`,
    );
  }
  const strategyDefinitionId = (
    await body<{ data: { id: string } }>(strategyRes)
  ).data.id;

  const topRes = await request.put(
    new URL(
      `/api/instruments/${encodeURIComponent(instrument.id)}/strategy-top`,
      baseURL,
    ).toString(),
    {
      data: {
        instrumentId: instrument.id,
        symbol: instrument.symbol,
        timeframe: "1d",
        // `semifinal` + `in_sample_only` no exigen `runId` en cada slot (ver schema del TOP).
        status: "semifinal",
        evidenceLevel: "in_sample_only",
        slots: [
          {
            rank: 1,
            label: STRATEGY_LABEL,
            strategyType: PRESET_KEY,
            strategyDefinitionId,
            stars: 3,
            score: 70,
            source: "coach",
          },
        ],
        coachFacts: {
          recommendations: [{ rank: 1, reasons: [STRATEGY_REASON] }],
        },
      },
    },
  );
  if (!topRes.ok()) {
    throw new Error(
      `PUT /api/instruments/${instrument.id}/strategy-top failed (${topRes.status()}): ${await topRes.text()}`,
    );
  }

  return {
    accountId,
    cycleId: cycle.cycleId,
    cycleSymbol,
    instrumentId: instrument.id,
    strategyDefinitionId,
    strategyLabel: STRATEGY_LABEL,
    noCycleReason: null,
    noChainReason: null,
  };
}

/** Abre la PRIMERA operación AUTO canónica de la cuenta (ruta `/auto/operar/operacion/:id`). */
async function openFirstOperation(page: Page, fixture: AutoBridgeFixture) {
  await seedHoyBrowserState(page, { accountId: fixture.accountId });
  await page.goto("/auto/operar");
  await expect(page.getByTestId("auto-operar-page")).toBeVisible({
    timeout: 20_000,
  });
  const link = page.getByTestId("auto-operar-operation-link").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByTestId("auto-operacion-page")).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("GP-V288-S5 — puente AUTO → estrategia → DÍA-D (API real)", () => {
  test.describe.configure({ mode: "serial" });

  let environmentSkip: string | null = null;
  let fixture: AutoBridgeFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    fixture = await ensureAutoBridgeFixture(request, baseURL);
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      test.skip(true, environmentSkip);
    }
    if (!fixture) {
      throw new Error(
        "AUTO DÍA-D bridge fixture missing after environment gates (fixture/product failure).",
      );
    }
  });

  test.afterAll(async ({ request, baseURL }) => {
    // Higiene determinista: el TOP de Finalistas es una tabla GLOBAL (NO acotada por cuenta), así
    // que el PUT de este journey dejaría un residuo que contaminaría runs futuros. Se retira el
    // instrumento usado. NO es una aserción: la limpieza es best-effort (su fallo no cambia el
    // resultado del run; el gate de entorno ya declaró la disponibilidad del stack). Sin stack
    // live (o sin cadena resuelta) `fixture.instrumentId` es `null` y no hay nada que limpiar.
    if (!fixture?.instrumentId || !baseURL) return;
    const cleanupUrl = new URL(
      `/api/instruments/${encodeURIComponent(fixture.instrumentId)}/strategy-top?timeframe=1d`,
      baseURL,
    ).toString();
    try {
      await request.delete(cleanupUrl);
    } catch {
      // best-effort: se declara implícitamente por ausencia de ruido en el run.
    }
  });

  test("GP-V288-S5-01: /auto/operar monta y declara su estado sin fabricar la operación", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    await seedHoyBrowserState(page, { accountId: fixture.accountId });
    await page.goto("/auto/operar");
    await expect(page.getByTestId("auto-operar-page")).toBeVisible({
      timeout: 20_000,
    });

    // La UI NO inventa una operación: o lista el ciclo durable, o declara el hueco.
    if (fixture.cycleId) {
      await expect(
        page.getByTestId("auto-operar-operation-link").first(),
      ).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("auto-operar-empty")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("auto-operar-empty")).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.getByTestId("auto-operar-operation-link")).toHaveCount(
        0,
      );
    }
  });

  test("GP-V288-S5-02: la operación AUTO muestra la estrategia #1 con sus indicadores (P3)", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    if (!fixture.cycleId) test.skip(true, fixture.noCycleReason!);
    if (!fixture.instrumentId || !fixture.strategyDefinitionId) {
      test.skip(true, fixture.noChainReason ?? NO_CHAIN_REASON);
    }

    await openFirstOperation(page, fixture);

    await expect(page.getByTestId("auto-operation-strategy")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByTestId("auto-operation-strategy-label"),
    ).toContainText(`#1 ${fixture.strategyLabel}`);
    // Los indicadores salen de la DEFINICIÓN real (preset SMA 20/50) — no vacíos, no «Sin dato».
    await expect(
      page.getByTestId("auto-operation-strategy-indicators"),
    ).not.toHaveText(/Sin dato todavía/);
    await expect(
      page.getByTestId("auto-operation-strategy-reason"),
    ).toContainText(STRATEGY_REASON);
    await expect(page.getByTestId("auto-operation-strategy-gap")).toHaveCount(
      0,
    );
    await expect(
      page.getByTestId("auto-operation-strategy-verify-dia-d"),
    ).toBeEnabled();
  });

  test("GP-V288-S5-03: «Verificar D→hoy» monta el host DÍA-D y arranca el run real (P4)", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    if (!fixture.cycleId) test.skip(true, fixture.noCycleReason!);
    if (!fixture.instrumentId || !fixture.strategyDefinitionId) {
      test.skip(true, fixture.noChainReason ?? NO_CHAIN_REASON);
    }

    await openFirstOperation(page, fixture);

    const cta = page.getByTestId("auto-operation-strategy-verify-dia-d");
    await expect(cta).toBeVisible({ timeout: 20_000 });
    await expect(cta).toBeEnabled();

    // El run D→hoy lo arranca la película al montar la sesión LAB: se observa la petición REAL.
    const runRequest = page.waitForRequest(
      (req) => {
        if (req.method() !== "POST") return false;
        try {
          return new URL(req.url()).pathname === RUN_PATH;
        } catch {
          return false;
        }
      },
      { timeout: 30_000 },
    );

    await cta.click();

    await expect(page).toHaveURL(/\/backtests\?/, { timeout: 20_000 });
    const url = new URL(page.url());
    expect(url.pathname).toBe("/backtests");
    expect(url.searchParams.get("tab")).toBe("run");
    expect(url.searchParams.get("instrumentId")).toBe(fixture.instrumentId);
    expect(url.searchParams.get("focus")).toBe("detail");
    expect(url.searchParams.get("verify")).toBe("1");

    // El host DÍA-D (banner + película) queda montado y arranca el run (no es una pantalla muerta).
    await expect(page.getByTestId("dia-d-verify-host")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("dia-d-verify-banner")).toBeVisible();
    await expect(page.getByTestId("dia-d-replay-embedded")).toBeVisible();
    await runRequest;
  });
});
