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
 * ciclo lo produce el MOTOR AUTO (worker de simulación), que el harness E2E no arranca. Para
 * que este journey sea REPRODUCIBLE, el propio `beforeAll` **siembra** un ciclo durable en la
 * cuenta efímera **reutilizando** el CLI dev `scripts/dev/seed_auto_cycle_for_ui.py` como
 * subproceso (ver `e2e/helpers/auto-cycle-seed.ts`); NO reimplementa lógica de backend.
 *
 * Run (API :8000 + PG + Vite proxy; el harness siembra y limpia el ciclo):
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-v288-s5
 * Against an existing dev server (PLAYWRIGHT_BASE_URL):
 *   E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v288-s5
 *
 * Reproducción manual de lo que hace el harness (mismos pasos, mismo CLI):
 *   uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py \
 *     --account-id e2e-v288-s5-xxxxxxxx --symbol <símbolo del catálogo> \
 *     --api-base http://localhost:5173
 *   # … abrir /auto/operar/operacion/<cycleId> y ejercitar el CTA «Verificar D→hoy»
 *   uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py --cleanup \
 *     --account-id e2e-v288-s5-xxxxxxxx --api-base http://localhost:5173
 *
 * `skipped` SIGUE siendo un skip declarado (no certifica): el journey se declara `skipped` con
 * motivo explícito si (a) `uv`/python no están disponibles (el seed devuelve el motivo), (b) el
 * monitor no declara ciclo tras el seed, o (c) el símbolo del ciclo no está en el catálogo.
 * Default (sin env): skipped.
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
import {
  autoCycleSeedEnabled,
  cleanupAutoCycleForAccount,
  seedAutoCycleForAccount,
  AUTO_CYCLE_SEED_DISABLED_REASON,
} from "./helpers/auto-cycle-seed";

/** Ciclo AUTO durable ausente: el motor (worker) no corre en el harness ⇒ hueco declarado. */
const NO_CYCLE_REASON =
  "Sin ciclo AUTO durable en la cuenta (el worker del motor AUTO no corre en el harness E2E). " +
  "El harness intenta sembrarlo con scripts/dev/seed_auto_cycle_for_ui.py.";

/** El ciclo existe pero su símbolo no está en el catálogo: no hay cadena de estrategia que probar. */
const NO_CHAIN_REASON =
  "El símbolo del ciclo AUTO no está en el catálogo /api/instruments: no se puede resolver la " +
  "estrategia #1 ni el UUID del instrumento para el deep-link DÍA-D.";

/** El catálogo de instrumentos está vacío: no hay símbolo con el que sembrar el ciclo. */
const NO_CATALOG_REASON =
  "El catálogo /api/instruments está vacío: no hay símbolo con el que sembrar el ciclo AUTO.";

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
  /** El harness lanzó el seed (aunque fallara): el `afterAll` debe limpiar/verificar. */
  seedAttempted: boolean;
  /** Motivo del hueco (ciclo ausente), o `null` si hay ciclo. */
  noCycleReason: string | null;
  /** Motivo del hueco (símbolo del ciclo fuera del catálogo), o `null`. */
  noChainReason: string | null;
};

async function body<T>(res: { json(): Promise<unknown> }): Promise<T> {
  return (await res.json()) as T;
}

/**
 * Cuenta efímera + ciclo AUTO durable sembrado (subproceso del CLI dev) + estrategia #1 y su
 * TOP de Finalistas REAL, para que la cadena `operación → estrategia/indicadores → DÍA-D` sea
 * verificable sin mocks.
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

  // Catálogo PRIMERO: necesitamos un símbolo real con el que sembrar el ciclo durable.
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
  const seedTarget = (catalog.data ?? [])[0] ?? null;

  // Siembra del ciclo AUTO durable reutilizando el CLI dev (subproceso `uv run … python …`).
  // No lanza: un fallo del seed se DECLARA (motivo) y el journey queda `skipped`, no verde.
  let seedAttempted = false;
  let seedOk = true;
  let seedReason = "";
  if (!seedTarget) {
    seedOk = false;
    seedReason = NO_CATALOG_REASON;
  } else if (autoCycleSeedEnabled()) {
    seedAttempted = true;
    const seeded = await seedAutoCycleForAccount({
      accountId,
      symbol: seedTarget.symbol,
      apiBase: baseURL,
    });
    seedOk = seeded.ok;
    if (!seeded.ok) seedReason = seeded.reason;
  } else {
    seedOk = false;
    seedReason = AUTO_CYCLE_SEED_DISABLED_REASON;
  }

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
      seedAttempted,
      noCycleReason: seedOk
        ? NO_CYCLE_REASON
        : `${NO_CYCLE_REASON} Seed: ${seedReason}`,
      noChainReason: null,
    };
  }

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
      seedAttempted,
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

  // El TOP de Finalistas es GLOBAL por instrumento: este PUT SOBRESCRIBE el TOP que el seed
  // hubiera dejado, para que la UI muestre EXACTAMENTE la etiqueta/razón que el spec asserta.
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
    seedAttempted,
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
  test.describe.configure({ mode: "serial", timeout: 240_000 });

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
    if (!fixture || !baseURL) return;

    // 1) Limpieza del seed durable: borra las filas del ciclo `cyc-ui-*` de la cuenta
    //    (reserva/fills/journal) + el `DELETE` del TOP que hace el propio CLI. NO es una
    //    aserción: si no puede correr, la verificación de residuo de abajo lo declara.
    let seedCleanupOk = true;
    let seedCleanupReason = "";
    if (fixture.seedAttempted) {
      const cleaned = await cleanupAutoCycleForAccount({
        accountId: fixture.accountId,
        apiBase: baseURL,
      });
      seedCleanupOk = cleaned.ok;
      if (!cleaned.ok) seedCleanupReason = cleaned.reason;
    }

    // 2) Higiene determinista (pre-existente): el TOP de Finalistas es una tabla GLOBAL (NO
    //    acotada por cuenta), así que el PUT de este journey dejaría un residuo que
    //    contaminaría runs futuros. Se retira el instrumento usado. La limpieza es
    //    best-effort (su fallo no cambia el resultado del run; el gate de entorno ya declaró
    //    la disponibilidad del stack). Sin cadena resuelta `fixture.instrumentId` es `null`.
    if (fixture.instrumentId) {
      const cleanupUrl = new URL(
        `/api/instruments/${encodeURIComponent(fixture.instrumentId)}/strategy-top?timeframe=1d`,
        baseURL,
      ).toString();
      try {
        await request.delete(cleanupUrl);
      } catch {
        // best-effort: se declara implícitamente por ausencia de ruido en el run.
      }
    }

    // 3) Aserción de NO-residuo: tras el teardown la cuenta efímera no puede declarar ciclo.
    //    Si el seed no llegó a lanzarse (sin opt-in / sin símbolo) no hay nada que verificar.
    if (fixture.seedAttempted) {
      const monitorRes = await request.get(
        new URL(`${MONITOR_PATH}?limit=20`, baseURL).toString(),
        { headers: { "X-Account-Id": fixture.accountId } },
      );
      if (monitorRes.ok()) {
        const monitor = await body<{ cycles?: MonitorCycle[] }>(monitorRes);
        expect(
          monitor.cycles ?? [],
          seedCleanupOk
            ? "El teardown dejó un ciclo AUTO residual en la cuenta efímera."
            : `La limpieza del seed no pudo correr: ${seedCleanupReason}`,
        ).toHaveLength(0);
      }
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
