/**
 * GP-E2E-AUTO-DAILY-CHAIN-LIVE — operativa diaria + DÍA-D del valor con API y WORKER reales.
 *
 * Qué certifica (y qué no)
 * ------------------------
 * Journey de NAVEGADOR sobre el sistema real: PostgreSQL + API FastAPI + worker de la cola
 * durable (`AUTO_OPS_JOB_WORKER_ENABLED=true`). Se pulsan los CTA reales y se comprueba, en la
 * UI, lo que el dictamen exige:
 *
 * 1. «Calcular operativa diaria» encola `estudio_daily` y el worker lo TERMINA (nada de
 *    esperas infinitas: un job que no termina es FALLO declarado, no un skip).
 * 2. Cada valor esperado declara un estado TERMINAL (`ok|no_signal|no_plan|error`) con
 *    explicación legible en las CUATRO preguntas de la ficha.
 * 3. La validación NO se afirma: el resumen publica `data-validation="false"` y la ficha
 *    separa «clasificación del selector» de «validación estadística».
 * 4. Los ids técnicos (cadena, plan, señal) NO están en la vista inicial: viven tras el
 *    desplegable `Detalle técnico` (mismo mecanismo único de la casa).
 * 5. «Verificar DÍA-D de este valor» encola el replay por valor; la cola declara la verdad del
 *    servidor (una por cuenta y día), la ruta se declara de SOLO LECTURA y el artefacto final
 *    declara SU cuenta, SU día y SU `watch` (el símbolo del valor, no el día completo).
 *
 * El mundo ESTUDIO lo siembra `scripts/dev/seed_estudio_daily_for_ui.py` (subproceso), que
 * reutiliza el harness real de siembra de Python. No se rebaja ningún gate: si el dato no
 * justifica el plan, el parte lo dirá y este spec fallará con el motivo visible.
 *
 * Gate de honestidad
 * ------------------
 * - Sin `E2E_INTEGRATION=1` + `E2E_ALLOW_DEV_DB=1` + API sana el journey se declara `skipped`.
 * - Con `E2E_LIVE_REQUIRED=1` (CI del tag) una precondición ausente es **FALLO**, no skip.
 *
 * Run:
 *   E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 E2E_RUN=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-e2e-auto-daily-chain-live
 * CI (precondición = fallo):
 *   E2E_LIVE_REQUIRED=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-e2e-auto-daily-chain-live
 */
import { randomUUID } from "node:crypto";
import {
  test,
  expect,
  type APIRequestContext,
  type Locator,
} from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  gateIntegratedE2eEnvironment,
  seedHoyBrowserState,
} from "./integration";
import {
  cleanupEstudioDailyWorld,
  estudioDailySeedEnabled,
  ESTUDIO_DAILY_SEED_DISABLED_REASON,
  seedEstudioDailyWorld,
  type EstudioDailySeedManifest,
} from "./helpers/estudio-daily-seed";

/** Símbolo sembrado (sintético y determinista: no toca valores reales del catálogo). */
const SEED_SYMBOL = (process.env.E2E_LIVE_SYMBOL ?? "E2EDAILY")
  .trim()
  .toUpperCase();
/** Estados TERMINALES del contrato del parte (ningún valor puede quedarse a medias). */
const TERMINAL_VALUE_STATUSES = new Set([
  "ok",
  "no_signal",
  "no_plan",
  "error",
]);
/** Estados terminales de un job de la cola durable. */
const TERMINAL_JOB_STATUSES = new Set(["completed", "failed"]);
const OPS_JOBS_PATH = "/api/auto/ops-jobs";
const DAILY_WAIT_MS = 240_000;
const DIA_D_WAIT_MS = 300_000;

/** `E2E_LIVE_REQUIRED=1` (CI del tag) convierte cualquier precondición ausente en FALLO. */
function liveRequired(): boolean {
  return process.env.E2E_LIVE_REQUIRED === "1";
}

/** Declara un hueco: `skipped` con motivo, o FALLO si el run exige el journey. */
function declareGap(reason: string): never | void {
  if (liveRequired()) {
    throw new Error(
      `E2E_LIVE_REQUIRED=1: precondición del journey diario ausente — ${reason}`,
    );
  }
  test.skip(true, reason);
}

type JobView = {
  id: string;
  kind: string;
  day: string | null;
  status: string;
  error?: string | null;
  payload?: { symbol?: string | null } | null;
  slot?: {
    state?: string;
    activeSymbol?: string | null;
    requestedSymbol?: string | null;
    matchesRequest?: boolean;
    message?: string;
  } | null;
};

type LiveState = {
  accountId: string | null;
  seedError: Error | null;
  seedAttempted: boolean;
  manifest: EstudioDailySeedManifest | null;
};

async function body<T>(res: { json(): Promise<unknown> }): Promise<T> {
  return (await res.json()) as T;
}

function jobUrl(baseURL: string, jobId: string): string {
  return new URL(
    `${OPS_JOBS_PATH}/${encodeURIComponent(jobId)}`,
    baseURL,
  ).toString();
}

async function readJob(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
  jobId: string,
): Promise<JobView> {
  const res = await request.get(jobUrl(baseURL, jobId), {
    headers: { "X-Account-Id": accountId },
  });
  if (!res.ok()) {
    throw new Error(
      `GET ${OPS_JOBS_PATH}/${jobId} falló (${res.status()}): ${await res.text()}`,
    );
  }
  return body<JobView>(res);
}

/** Encuesta la lista de jobs del (kind, día) hasta encontrar uno TERMINAL del símbolo. */
async function waitForListedJob(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
  kind: string,
  day: string,
  timeoutMs: number,
  accept: (job: JobView) => boolean,
): Promise<JobView> {
  const deadline = Date.now() + timeoutMs;
  let seen: JobView[] = [];
  for (;;) {
    const res = await request.get(
      new URL(
        `${OPS_JOBS_PATH}?kind=${encodeURIComponent(kind)}&day=${encodeURIComponent(day)}&limit=10`,
        baseURL,
      ).toString(),
      { headers: { "X-Account-Id": accountId } },
    );
    if (res.ok()) {
      const listed = await body<{ jobs?: JobView[] }>(res);
      seen = listed.jobs ?? [];
      const match = seen.find((job) => accept(job));
      if (match && TERMINAL_JOB_STATUSES.has(match.status)) return match;
    }
    if (Date.now() >= deadline) {
      throw new Error(
        `la cola no declaró un job ${kind} terminal del día ${day} en ${timeoutMs} ms ` +
          `(observados: ${seen.map((job) => `${job.id}:${job.status}`).join(", ") || "ninguno"}).`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
}

/**
 * Prepara el escenario: gate del entorno integrado + cuenta efímera + mundo ESTUDIO sembrado.
 * Los fallos de producto se DECLARAN y se propagan como FAIL (nunca como skip silencioso).
 */
async function prepareLiveState(
  request: APIRequestContext,
  baseURL: string | undefined,
): Promise<{ skip: string | null; state: LiveState }> {
  const state: LiveState = {
    accountId: null,
    seedError: null,
    seedAttempted: false,
    manifest: null,
  };
  const environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
    e2eEnabled: e2eEnabled(),
    e2eSkipReason: E2E_SKIP_REASON,
  });
  if (environmentSkip || !baseURL) {
    return { skip: environmentSkip ?? "baseURL required", state };
  }

  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `e2e-live-daily-${randomUUID().slice(0, 8)}`,
        currency: "EUR",
        initialDeposit: 100_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts falló (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  state.accountId = (await body<{ data: { id: string } }>(accountRes)).data.id;

  if (!estudioDailySeedEnabled()) {
    state.seedError = new Error(ESTUDIO_DAILY_SEED_DISABLED_REASON);
    return { skip: null, state };
  }
  state.seedAttempted = true;
  const seeded = await seedEstudioDailyWorld({
    accountId: state.accountId,
    symbol: SEED_SYMBOL,
    apiBase: baseURL,
  });
  if (!seeded.ok) {
    state.seedError = new Error(seeded.reason);
    return { skip: null, state };
  }
  state.manifest = seeded.manifest;
  return { skip: null, state };
}

/** Cierra + borra la cuenta efímera del journey (no-residuo verificado). */
async function disposeAccount(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
  failures: string[],
): Promise<void> {
  const url = new URL(`/api/accounts/${accountId}`, baseURL).toString();
  const closeRes = await request.post(`${url}/close`);
  if (!closeRes.ok() && closeRes.status() !== 404) {
    failures.push(
      `POST /api/accounts/${accountId}/close falló (${closeRes.status()}): ${await closeRes.text()}`,
    );
  }
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const delRes = await request.delete(url);
    if (delRes.ok() || delRes.status() === 404) return;
    if (attempt === 2) {
      failures.push(
        `DELETE /api/accounts/${accountId} falló (${delRes.status()}): ${await delRes.text()}`,
      );
    }
  }
}

/**
 * Garantiza que la evidencia DÍA-D está ABIERTA. El CTA «Verificar» ya la abre, así que
 * pulsar el toggle a ciegas la cerraría justo antes de leer el artefacto (el bug que este
 * helper evita): solo se pulsa si el botón declara que está cerrada.
 */
async function ensureDiaDEvidenceOpen(diaD: Locator): Promise<void> {
  const toggle = diaD.getByTestId("estudio-chain-dia-d-toggle");
  const label = (await toggle.textContent()) ?? "";
  if (/ver evidencia/i.test(label)) await toggle.click();
}

test.describe("GP-E2E-AUTO-DAILY-CHAIN-LIVE — parte diario y DÍA-D del valor (API + worker reales)", () => {
  test.describe.configure({ mode: "serial", timeout: 420_000 });

  let environmentSkip: string | null = null;
  const state: LiveState = {
    accountId: null,
    seedError: null,
    seedAttempted: false,
    manifest: null,
  };

  test.beforeAll(async ({ request, baseURL }) => {
    test.setTimeout(360_000);
    const prepared = await prepareLiveState(request, baseURL);
    environmentSkip = prepared.skip;
    Object.assign(state, prepared.state);
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      declareGap(environmentSkip);
      return;
    }
    if (state.seedError) throw state.seedError;
    if (!state.accountId || !state.manifest) {
      declareGap("el escenario no declaró cuenta o manifiesto del seed.");
    }
  });

  test.afterAll(async ({ request, baseURL }) => {
    if (!baseURL || !state.accountId) return;
    const failures: string[] = [];
    if (state.seedAttempted) {
      const cleaned = await cleanupEstudioDailyWorld({
        accountId: state.accountId,
        symbol: state.manifest?.symbol ?? SEED_SYMBOL,
        apiBase: baseURL,
        previousMembership: state.manifest?.previousMembership,
      });
      if (!cleaned.ok) failures.push(cleaned.reason);
    }
    await disposeAccount(request, baseURL, state.accountId, failures);
    if (failures.length > 0) {
      throw new Error(
        `Teardown del journey LIVE no completó:\n- ${failures.join("\n- ")}`,
      );
    }
  });

  test("LIVE-01: «Calcular operativa diaria» termina y la ficha responde las cuatro preguntas", async ({
    page,
    request,
    baseURL,
  }) => {
    if (!state.accountId || !state.manifest || !baseURL) {
      throw new Error("fixture required");
    }
    const { accountId, manifest } = state;
    const headers = { "X-Account-Id": accountId };

    await seedHoyBrowserState(page, { accountId });
    await page.goto("/auto-monitor?mode=daily");
    await expect(page.getByTestId("estudio-daily-ops-panel")).toBeVisible({
      timeout: 60_000,
    });

    // Día del parte = la vela CERRADA sembrada (la frontera de decisión real).
    await page.getByTestId("estudio-daily-asof").fill(manifest.asOf);
    const run = page.getByTestId("estudio-daily-run");
    await expect(run).toBeEnabled({ timeout: 30_000 });
    await run.click();
    await expect(page.getByTestId("estudio-daily-job-status")).toContainText(
      manifest.asOf,
      { timeout: 60_000 },
    );

    // El worker REAL termina el job: esperar un estado terminal es la prueba de que corre.
    const daily = await waitForListedJob(
      request,
      baseURL,
      accountId,
      "estudio_daily",
      manifest.asOf,
      DAILY_WAIT_MS,
      (job) => job.kind === "estudio_daily" && job.day === manifest.asOf,
    );
    if (daily.status !== "completed") {
      throw new Error(
        `el job estudio_daily del ${manifest.asOf} terminó en '${daily.status}': ` +
          `${daily.error ?? "(sin motivo declarado)"}`,
      );
    }

    // La ficha del valor sembrado: estado TERMINAL + explicación legible.
    const card = page.locator(
      `[data-testid="estudio-daily-value"][data-symbol="${manifest.symbol}"]`,
    );
    await expect(card).toBeVisible({ timeout: 90_000 });
    const status = (await card.getAttribute("data-status")) ?? "";
    expect(
      TERMINAL_VALUE_STATUSES.has(status),
      `el valor debe declarar un estado terminal del contrato, no '${status}'`,
    ).toBe(true);
    // El mundo se sembró para que el DATO justifique el plan (SMA200 + fundamentales en corte
    // + TOP vigente). Si no lo justifica, se declara el motivo real, nunca se rebaja el gate.
    expect(
      status,
      `el valor sembrado debía declarar 'ok' (estado observado: '${status}')`,
    ).toBe("ok");

    const summary = card.getByTestId("estudio-daily-value-summary");
    await expect(summary).toBeVisible({ timeout: 30_000 });
    // La validación NO se afirma desde el parte.
    await expect(summary).toHaveAttribute("data-validation", "false");
    for (const key of ["proposal", "why", "missing", "validation"] as const) {
      const row = card.getByTestId(`estudio-daily-value-summary-${key}`);
      await expect(row).toBeVisible();
      await expect(row).not.toHaveText(/^\s*$/);
    }
    await expect(
      card.getByTestId("estudio-daily-value-summary-proposal"),
    ).toContainText(/Propone una (compra|venta)|propone una entrada/i);
    await expect(
      card.getByTestId("estudio-daily-value-summary-validation"),
    ).toContainText(/no validada|no medida/i);
    // Clasificación SEPARADA de validación (no se vende «mejor» como «validada»).
    await expect(
      card.getByTestId("estudio-daily-value-summary-classification"),
    ).toContainText(/Clasificación del selector/i);

    // Los ids técnicos NO están en la vista inicial: viven tras el desplegable.
    const technical = card.getByTestId("estudio-daily-value-technical");
    await expect(technical).toBeVisible();
    await expect(card.getByTestId("estudio-daily-value-strategy")).toBeHidden();
    await expect(card.getByTestId("estudio-daily-value-chain")).toBeHidden();
    // `first()`: el disclosure RAÍZ de la ficha (dentro vive otro disclosure técnico del
    // selector, con su PROPIO testid). Ambos comparten el rótulo único de la casa.
    await technical.locator("summary").first().click();

    await expect(
      card.getByTestId("estudio-daily-value-strategy"),
    ).toBeVisible();
    await expect(card.getByTestId("estudio-daily-value-chain")).toBeVisible();
    // La señal y el plan del parte son ids durables (no una inferencia por símbolo).
    const planId = await card
      .getByTestId("estudio-daily-value-strategy-identity")
      .textContent();
    expect(planId ?? "").toMatch(/plan \S+/i);

    // La cobertura del universo es reconciliable y se declara en la UI.
    await expect(page.getByTestId("estudio-daily-counts")).toBeVisible();
    const coverage = page.getByTestId("estudio-daily-coverage");
    await expect(coverage).toBeVisible();
    await expect(coverage).toContainText(/\d+\s*de\s*\d+/);

    // La cola es la fuente de verdad del estado del job (no una inferencia de la UI).
    const jobStatus = await readJob(request, baseURL, accountId, daily.id);
    expect(jobStatus.status).toBe("completed");
    void headers;
  });

  test("LIVE-02: «Verificar DÍA-D de este valor» encola, declara la cola y sirve SU artefacto", async ({
    page,
    request,
    baseURL,
  }) => {
    if (!state.accountId || !state.manifest || !baseURL) {
      throw new Error("fixture required");
    }
    const { accountId, manifest } = state;

    await seedHoyBrowserState(page, { accountId });
    await page.goto("/auto-monitor?mode=daily");
    await expect(page.getByTestId("estudio-daily-ops-panel")).toBeVisible({
      timeout: 60_000,
    });
    await page.getByTestId("estudio-daily-asof").fill(manifest.asOf);
    const card = page.locator(
      `[data-testid="estudio-daily-value"][data-symbol="${manifest.symbol}"]`,
    );
    await expect(card).toBeVisible({ timeout: 90_000 });

    // El DÍA-D del valor es DETALLE TÉCNICO: se abre el desplegable RAÍZ de la ficha
    // (`first()`: dentro vive otro disclosure técnico del selector con su propio testid).
    await card
      .getByTestId("estudio-daily-value-technical")
      .locator("summary")
      .first()
      .click();
    const diaD = card.getByTestId("estudio-chain-dia-d");
    await expect(diaD).toBeVisible({ timeout: 60_000 });
    // Contexto y alcance declarados: día pedido, origen y ruta de SOLO LECTURA.
    const scope = diaD.getByTestId("estudio-chain-dia-d-scope");
    await expect(scope).toContainText(/solo lectura/i);
    await expect(scope).toContainText(/Día solicitado \d{4}-\d{2}-\d{2}/);
    const requestedDay = (await diaD.getAttribute("data-day")) ?? "";
    expect(requestedDay).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const daySource = (await diaD.getAttribute("data-day-source")) ?? "";
    expect(["cycle", "bar", "none"]).toContain(daySource);

    const verify = diaD.getByTestId("estudio-chain-dia-d-verify");
    await expect(verify).toBeEnabled({ timeout: 60_000 });
    await verify.click();

    // Otro símbolo en el MISMO hueco no puede fingir que encoló el suyo. Se intenta de
    // inmediato (el job propio acaba de encolarse): si el hueco ya está ocupado, el servidor
    // devuelve SU job con `matchesRequest=false` y el mensaje del símbolo que lo ocupa.
    const conflict = await request.post(
      new URL(OPS_JOBS_PATH, baseURL).toString(),
      {
        headers: { "X-Account-Id": accountId },
        data: {
          kind: "dia_d_value_replay",
          day: requestedDay,
          payload: { symbol: "ZZLIVE" },
        },
      },
    );
    let ownJobId: string | null = null;
    if (conflict.ok()) {
      const other = await body<JobView>(conflict);
      if ((other.payload?.symbol ?? "").toUpperCase() !== "ZZLIVE") {
        expect(other.slot?.matchesRequest).toBe(false);
        expect(String(other.slot?.message ?? "")).toContain(manifest.symbol);
        ownJobId = other.id;
      } else {
        // El hueco estaba libre cuando se intentó: el job ajeno es otro declarado (no finge).
        test.info().annotations.push({
          type: "cola-libre",
          description:
            "El hueco (cuenta, día) estaba libre al intentar el segundo valor: no había cola que observar.",
        });
      }
    }

    // El job PROPIO termina: estado terminal de la cola es la prueba de que el worker corre.
    const listed = await waitForListedJob(
      request,
      baseURL,
      accountId,
      "dia_d_value_replay",
      requestedDay,
      DIA_D_WAIT_MS,
      (job) =>
        (job.payload?.symbol ?? "").toUpperCase() === manifest.symbol &&
        (ownJobId === null || job.id === ownJobId),
    );
    if (listed.status !== "completed") {
      throw new Error(
        `el replay DÍA-D del valor ${manifest.symbol} (${requestedDay}) terminó en ` +
          `'${listed.status}': ${listed.error ?? "(sin motivo declarado)"}`,
      );
    }

    // El artefacto es SUYO: cuenta, día y watch de exactamente ese valor.
    await ensureDiaDEvidenceOpen(diaD);
    const artifact = diaD.getByTestId("estudio-chain-dia-d-artifact");
    const absent = diaD.getByTestId("estudio-chain-dia-d-artifact-absent");
    await expect(artifact.or(absent)).toBeVisible({ timeout: 60_000 });
    await expect(artifact).toBeVisible();
    await expect(
      artifact.getByTestId("estudio-chain-dia-d-artifact-meta"),
    ).toHaveAttribute("data-artifact-account", accountId);
    await expect(
      artifact.getByTestId("estudio-chain-dia-d-artifact-meta"),
    ).toHaveAttribute("data-artifact-day", requestedDay);
    await expect(
      artifact.getByTestId("estudio-chain-dia-d-artifact-meta"),
    ).toHaveAttribute("data-artifact-watch", manifest.symbol);

    // La UI del job refleja el desenlace terminal del servidor (no un «verificando…» eterno).
    await expect(diaD.getByTestId("estudio-chain-dia-d-job")).toHaveAttribute(
      "data-status",
      /completed|failed/,
      { timeout: 60_000 },
    );
  });
});
