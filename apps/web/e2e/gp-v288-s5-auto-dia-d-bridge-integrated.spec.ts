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
 * Ciclo de vida del fixture (H2, v2.88.106 — HONESTIDAD y NO-RESIDUO):
 * - Cada recurso se **registra en cuanto existe** (la cuenta justo tras su `POST`), no al final:
 *   si una petición intermedia falla, el `afterAll` todavía conoce lo creado y lo limpia.
 * - El TOP de Finalistas es una tabla **GLOBAL por instrumento**: el journey **guarda** el TOP
 *   previo antes de tocarlo y lo **restaura** al terminar, y **verifica** que quedó como estaba
 *   (no «best-effort»: si no cuadra, el run es ROJO).
 * - La limpieza se ejecuta SIEMPRE (equivale a `finally`), y termina borrando la cuenta efímera.
 *
 * `E2E_S5_REQUIRED=1` (CI del tag): una precondición ausente (entorno/ciclo/catálogo) se
 * convierte en **FALLO**, no en `skipped`, para que un skip no pueda dar verde en CI. Sin ese
 * modo, `skipped` SIGUE siendo un skip declarado con motivo.
 *
 * Run (API :8000 + PG + Vite proxy; el harness siembra y limpia el ciclo):
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-v288-s5
 * Against an existing dev server (PLAYWRIGHT_BASE_URL):
 *   E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v288-s5
 * Modo CI del tag (precondición = fallo, no skip):
 *   E2E_S5_REQUIRED=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-v288-s5
 *
 * Reproducción manual de lo que hace el harness (mismos pasos, mismo CLI):
 *   uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py \
 *     --account-id e2e-v288-s5-xxxxxxxx --symbol <símbolo del catálogo> \
 *     --api-base http://localhost:5173
 *   # … abrir /auto/operar/operacion/<cycleId> y ejercitar el CTA «Verificar D→hoy»
 *   uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py --cleanup \
 *     --account-id e2e-v288-s5-xxxxxxxx --api-base http://localhost:5173
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

/** El catálogo de instrumentos está vacío: no hay símbolo con el que sembrar el ciclo AUTO. */
const NO_CATALOG_REASON =
  "El catálogo /api/instruments está vacío: no hay símbolo con el que sembrar el ciclo AUTO.";

const MONITOR_PATH = "/api/auto/operational-monitor";
const RUN_PATH = "/api/backtests/run";
const TOP_TIMEFRAME = "1d";
const PRESET_KEY = "sma_crossover";
const STRATEGY_LABEL = "E2E S5 · Cruce SMA 20/50";
const STRATEGY_REASON = "E2E S5 · razones del coach";

/** `E2E_S5_REQUIRED=1` (CI del tag) convierte cualquier precondición ausente en FALLO. */
function s5Required(): boolean {
  return process.env.E2E_S5_REQUIRED === "1";
}

type MonitorCycle = {
  cycleId: string;
  instrumentId?: string | null;
};

/** Estado del TOP global ANTES de tocarlo (para restaurarlo y verificarlo). */
type TopSnapshot = { status: "absent" } | { status: "present"; body: unknown };

/**
 * Registro MUTABLE del harness: se rellena recurso a recurso en cuanto existe, de modo que el
 * teardown puede limpiar aunque una petición intermedia falle (H2).
 */
type S5State = {
  /** Cuenta efímera: se registra justo tras su `POST` (primer recurso). */
  accountId: string | null;
  /** Fallo de seed/fixture (producto): se propaga como FAIL, nunca como skip. */
  seedError: Error | null;
  /** El harness lanzó el seed (aunque fallara): hay residuo durable que verificar. */
  seedAttempted: boolean;
  cycleId: string | null;
  cycleSymbol: string | null;
  instrumentId: string | null;
  strategyDefinitionId: string | null;
  strategyLabel: string;
  /** Motivo del hueco (ciclo ausente), o `null` si hay ciclo. */
  noCycleReason: string | null;
  /** Motivo del hueco (símbolo del ciclo fuera del catálogo), o `null`. */
  noChainReason: string | null;
  /** TOP(s) global(es) que el journey tocó, con su estado previo. */
  topBackups: Array<{ instrumentId: string; snapshot: TopSnapshot }>;
};

function emptyState(): S5State {
  return {
    accountId: null,
    seedError: null,
    seedAttempted: false,
    cycleId: null,
    cycleSymbol: null,
    instrumentId: null,
    strategyDefinitionId: null,
    strategyLabel: "",
    noCycleReason: null,
    noChainReason: null,
    topBackups: [],
  };
}

async function body<T>(res: { json(): Promise<unknown> }): Promise<T> {
  return (await res.json()) as T;
}

function strategyTopUrl(baseURL: string, instrumentId: string): string {
  return new URL(
    `/api/instruments/${encodeURIComponent(instrumentId)}/strategy-top`,
    baseURL,
  ).toString();
}

/**
 * Lee el TOP de Finalistas (tabla GLOBAL por instrumento). El endpoint NO usa 404: devuelve
 * `{ data: null }` cuando no hay TOP, así que la ausencia es un estado DECLARADO.
 */
async function readStrategyTop(
  request: APIRequestContext,
  baseURL: string,
  instrumentId: string,
): Promise<TopSnapshot> {
  const res = await request.get(strategyTopUrl(baseURL, instrumentId));
  if (!res.ok()) {
    throw new Error(
      `GET strategy-top de ${instrumentId} falló (${res.status()}): ${await res.text()}`,
    );
  }
  const json = await body<{ data: unknown }>(res);
  return json?.data == null
    ? { status: "absent" }
    : { status: "present", body: json.data };
}

/**
 * Guarda el TOP previo ANTES de tocarlo (una sola vez por instrumento). El CLI de seed también
 * hace `PUT .../strategy-top`, así que la captura debe ocurrir antes de lanzarlo.
 */
async function backupStrategyTop(
  request: APIRequestContext,
  baseURL: string,
  state: S5State,
  instrumentId: string,
): Promise<void> {
  if (state.topBackups.some((b) => b.instrumentId === instrumentId)) return;
  const snapshot = await readStrategyTop(request, baseURL, instrumentId);
  state.topBackups.push({ instrumentId, snapshot });
}

/** Restaura el TOP previo (o asegura su ausencia) para no contaminar runs futuros. */
async function restoreStrategyTop(
  request: APIRequestContext,
  baseURL: string,
  backup: { instrumentId: string; snapshot: TopSnapshot },
): Promise<void> {
  const url = strategyTopUrl(baseURL, backup.instrumentId);
  if (backup.snapshot.status === "present") {
    const raw = (backup.snapshot.body ?? {}) as Record<string, unknown>;
    const putRes = await request.put(url, {
      data: {
        ...raw,
        instrumentId: backup.instrumentId,
        timeframe: raw.timeframe ?? TOP_TIMEFRAME,
      },
    });
    if (!putRes.ok()) {
      throw new Error(
        `PUT de restauración del TOP ${backup.instrumentId} falló (${putRes.status()}): ${await putRes.text()}`,
      );
    }
    return;
  }
  const delRes = await request.delete(
    `${url}?timeframe=${encodeURIComponent(TOP_TIMEFRAME)}`,
  );
  if (!delRes.ok() && delRes.status() !== 404) {
    throw new Error(
      `DELETE de restauración del TOP ${backup.instrumentId} falló (${delRes.status()}).`,
    );
  }
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value) ?? "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
    .join(",")}}`;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

/**
 * Proyección semántica del TOP (ignora `id`/`version`/`updatedAt`, que cambian al reescribirlo)
 * para comparar el ANTES con el DESPUÉS de la restauración.
 */
function normalizeTop(snapshot: TopSnapshot): unknown {
  if (snapshot.status === "absent") return { absent: true };
  const raw = asRecord(snapshot.body);
  const slots = (Array.isArray(raw.slots) ? raw.slots : [])
    .map((slot) => asRecord(slot))
    .sort((a, b) => Number(a.rank ?? 0) - Number(b.rank ?? 0))
    .map((s) => ({
      rank: s.rank ?? null,
      label: s.label ?? null,
      strategyType: s.strategyType ?? null,
      strategyDefinitionId: s.strategyDefinitionId ?? null,
      stars: s.stars ?? null,
      score: s.score ?? null,
      source: s.source ?? null,
      runId: s.runId ?? null,
    }));
  return {
    status: raw.status ?? null,
    evidenceLevel: raw.evidenceLevel ?? null,
    symbol: raw.symbol ?? null,
    timeframe: raw.timeframe ?? null,
    slots,
    coachFacts: raw.coachFacts ?? null,
  };
}

function sameTop(before: TopSnapshot, after: TopSnapshot): boolean {
  return (
    stableStringify(normalizeTop(before)) ===
    stableStringify(normalizeTop(after))
  );
}

/**
 * Estado observable de la cuenta efímera. `gone` (404) es el estado DESEADO al final del run: la
 * cuenta ya no existe y no hay nada más que limpiar (no es un error). Se usa el mismo guard de
 * visibilidad que `DELETE`, así que «gone» siempre significa «fuera del alcance de este principal».
 */
type AccountProbe =
  | { kind: "gone" }
  | { kind: "present"; status: string | null; type: string | null };

/** Lee el estado de la cuenta efímera sin tragárse el diagnóstico de un fallo inesperado. */
async function probeAccount(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
): Promise<AccountProbe> {
  const res = await request.get(
    new URL(`/api/accounts/${accountId}`, baseURL).toString(),
  );
  if (res.status() === 404) return { kind: "gone" };
  if (!res.ok()) {
    throw new Error(
      `GET /api/accounts/${accountId} falló (${res.status()}): ${await res.text()}`,
    );
  }
  const data = (
    await body<{ data?: { status?: string | null; type?: string | null } }>(res)
  ).data;
  return {
    kind: "present",
    status: data?.status ?? null,
    type: data?.type ?? null,
  };
}

function describeProbe(probe: AccountProbe): string {
  return probe.kind === "gone"
    ? "gone"
    : `status=${String(probe.status)}, type=${String(probe.type)}`;
}

/**
 * Cierra la cuenta efímera y la BORRA, verificando cada paso. El `DELETE` exige la cuenta
 * `closed` (conservación contable) y el `400` no distingue motivos, de modo que el teardown:
 * 1. sondea el estado real antes de actuar (una cuenta ya borrada es el estado deseado, no un rojo);
 * 2. cierra y RE-VERIFICA (con un reintento) que quedó `closed` antes de borrar;
 * 3. borra con un reintento y, si falla, adjunta el cuerpo de la respuesta + el estado observado;
 * 4. comprueba al final que la cuenta NO sobrevive (residuo = rojo).
 * Nunca lanza: acumula los motivos en `failures` para que el `afterAll` decida.
 */
async function disposeEphemeralAccount(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
  failures: string[],
): Promise<void> {
  const accountUrl = new URL(`/api/accounts/${accountId}`, baseURL).toString();

  const closeOnce = async (): Promise<string | null> => {
    const res = await request.post(`${accountUrl}/close`);
    if (res.ok() || res.status() === 404) return null;
    return `POST /api/accounts/${accountId}/close falló (${res.status()}): ${await res.text()}`;
  };

  try {
    let probe = await probeAccount(request, baseURL, accountId);
    if (probe.kind === "gone") return;

    const closeError = await closeOnce();
    if (closeError) failures.push(closeError);

    // El cierre es un requisito DURO del borrado: no se insiste en borrar sin confirmarlo.
    probe = await probeAccount(request, baseURL, accountId);
    if (probe.kind === "present" && probe.status !== "closed") {
      const retryError = await closeOnce();
      if (retryError) failures.push(retryError);
      probe = await probeAccount(request, baseURL, accountId);
    }
    if (probe.kind === "gone") return;
    if (probe.status !== "closed") {
      failures.push(
        `la cuenta ${accountId} no quedó cerrada antes del borrado (${describeProbe(probe)}).`,
      );
      return;
    }

    for (let attempt = 1; attempt <= 2; attempt += 1) {
      const delRes = await request.delete(accountUrl);
      if (delRes.ok() || delRes.status() === 404) break;
      const detail = await delRes.text();
      const after = await probeAccount(request, baseURL, accountId);
      // El `400` puede llegar con el borrado YA efectivo: el sondeo manda, no el código.
      if (after.kind === "gone") break;
      if (attempt === 2) {
        failures.push(
          `DELETE /api/accounts/${accountId} falló (${delRes.status()}): ${detail} [tras el intento: ${describeProbe(after)}]`,
        );
        break;
      }
    }
  } catch (err) {
    failures.push(
      `el cierre/borrado de la cuenta ${accountId} lanzó: ${err instanceof Error ? err.message : String(err)}`,
    );
    return;
  }

  // Residuo = rojo: la cuenta efímera no puede sobrevivir al teardown.
  try {
    const finalProbe = await probeAccount(request, baseURL, accountId);
    if (finalProbe.kind !== "gone") {
      failures.push(
        `la cuenta efímera ${accountId} sigue existiendo tras el teardown (${describeProbe(finalProbe)}).`,
      );
    }
  } catch (err) {
    failures.push(
      `no se pudo verificar el borrado de ${accountId}: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

/**
 * Siembra la cadena completa registrando CADA recurso en cuanto existe:
 * cuenta efímera → catálogo → (snapshot del TOP) → ciclo AUTO durable → TOP real de Finalistas.
 *
 * NO lanza en huecos DECLARADOS (catálogo vacío / seed no opt-in / símbolo fuera del catálogo):
 * esos son `skipped` con motivo. Los fallos de producto (HTTP) SÍ lanzan y el `beforeAll` los
 * captura para fallar sin perder el registro de limpieza.
 */
async function seedAutoBridge(
  request: APIRequestContext,
  baseURL: string,
  state: S5State,
): Promise<void> {
  const suffix = randomUUID().slice(0, 8);

  // 1) Cuenta efímera PRIMERO — se registra de inmediato, antes de cualquier petición que pueda
  //    fallar, para que el teardown pueda borrarla aun con un fallo aguas abajo.
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
  state.accountId = (await body<{ data: { id: string } }>(accountRes)).data.id;

  // 2) Catálogo: necesitamos un símbolo real con el que sembrar el ciclo durable.
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

  // 3) Siembra del ciclo AUTO durable reutilizando el CLI dev (subproceso `uv run … python …`).
  //    El CLI también hace PUT del TOP: capturamos el TOP previo ANTES de lanzarlo.
  let seedReason = "";
  if (!seedTarget) {
    seedReason = NO_CATALOG_REASON;
  } else if (autoCycleSeedEnabled()) {
    await backupStrategyTop(request, baseURL, state, seedTarget.id);
    state.seedAttempted = true;
    const seeded = await seedAutoCycleForAccount({
      accountId: state.accountId,
      symbol: seedTarget.symbol,
      apiBase: baseURL,
    });
    if (!seeded.ok) seedReason = seeded.reason;
  } else {
    seedReason = AUTO_CYCLE_SEED_DISABLED_REASON;
  }
  const seedOk = seedReason === "";

  const monitorRes = await request.get(
    new URL(`${MONITOR_PATH}?limit=20`, baseURL).toString(),
    { headers: { "X-Account-Id": state.accountId } },
  );
  if (!monitorRes.ok()) {
    throw new Error(
      `GET ${MONITOR_PATH} failed (${monitorRes.status()}): ${await monitorRes.text()}`,
    );
  }
  const monitor = await body<{ cycles?: MonitorCycle[] }>(monitorRes);
  const cycle = (monitor.cycles ?? [])[0] ?? null;
  state.cycleId = cycle?.cycleId ?? null;
  state.cycleSymbol = cycle?.instrumentId?.trim() || null;

  if (!cycle || !state.cycleSymbol) {
    state.noCycleReason = seedOk
      ? NO_CYCLE_REASON
      : `${NO_CYCLE_REASON} Seed: ${seedReason}`;
    return;
  }

  const upper = state.cycleSymbol.toUpperCase();
  const instrument = (catalog.data ?? []).find(
    (row) => row.symbol?.toUpperCase() === upper,
  );
  if (!instrument) {
    state.noChainReason = NO_CHAIN_REASON;
    return;
  }
  state.instrumentId = instrument.id;

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
  state.strategyDefinitionId = (
    await body<{ data: { id: string } }>(strategyRes)
  ).data.id;

  // El TOP de Finalistas es GLOBAL por instrumento: guardamos el previo (si no se capturó ya) y
  // SOBRESCRIBIMOS para que la UI muestre EXACTAMENTE la etiqueta/razón que el spec asserta.
  await backupStrategyTop(request, baseURL, state, instrument.id);
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
            strategyDefinitionId: state.strategyDefinitionId,
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
  state.strategyLabel = STRATEGY_LABEL;
}

/** Abre la PRIMERA operación AUTO canónica de la cuenta (ruta `/auto/operar/operacion/:id`). */
async function openFirstOperation(page: Page, accountId: string) {
  await seedHoyBrowserState(page, { accountId });
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
  const state: S5State = emptyState();

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    try {
      await seedAutoBridge(request, baseURL, state);
    } catch (err) {
      // Fallo de producto: se DECLARA y propaga como FAIL, pero NO se pierde el registro de
      // recursos (la cuenta ya creada queda en `state` para que el `afterAll` la limpie).
      state.seedError = err instanceof Error ? err : new Error(String(err));
    }
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      // En modo requerido (CI del tag) un entorno no disponible es FAIL, no skip.
      if (s5Required()) {
        throw new Error(
          `E2E_S5_REQUIRED=1 pero el entorno integrado no está disponible: ${environmentSkip}`,
        );
      }
      test.skip(true, environmentSkip);
    }
    if (state.seedError) {
      throw state.seedError;
    }
  });

  test.afterAll(async ({ request, baseURL }) => {
    if (!baseURL || !state.accountId) return;
    const failures: string[] = [];

    // 1) Limpieza del seed durable (filas ciclos `cyc-ui-*` + DELETE del TOP del símbolo).
    //    No es una aserción por sí sola: si no puede correr, la verificación de residuo lo declara.
    if (state.seedAttempted) {
      try {
        const cleaned = await cleanupAutoCycleForAccount({
          accountId: state.accountId,
          apiBase: baseURL,
        });
        if (!cleaned.ok) {
          failures.push(
            `la limpieza del seed no pudo correr: ${cleaned.reason}`,
          );
        }
      } catch (err) {
        failures.push(`la limpieza del seed lanzó: ${String(err)}`);
      }
    }

    // 2) Restauración del TOP global: el PUT del journey dejaría un residuo que contaminaría
    //    runs futuros. Se restaura el valor previo y se VERIFICA que quedó como estaba.
    for (const backup of state.topBackups) {
      try {
        await restoreStrategyTop(request, baseURL, backup);
        const after = await readStrategyTop(
          request,
          baseURL,
          backup.instrumentId,
        );
        if (!sameTop(backup.snapshot, after)) {
          failures.push(
            `el TOP de ${backup.instrumentId} no quedó restaurado tras el teardown.`,
          );
        }
      } catch (err) {
        failures.push(
          `no se pudo restaurar el TOP de ${backup.instrumentId}: ${String(err)}`,
        );
      }
    }

    // 3) Aserción de NO-residuo: tras el teardown la cuenta efímera no puede declarar ciclo.
    if (state.seedAttempted) {
      const monitorRes = await request.get(
        new URL(`${MONITOR_PATH}?limit=20`, baseURL).toString(),
        { headers: { "X-Account-Id": state.accountId } },
      );
      if (monitorRes.ok()) {
        const monitor = await body<{ cycles?: MonitorCycle[] }>(monitorRes);
        if ((monitor.cycles ?? []).length > 0) {
          failures.push(
            "el teardown dejó un ciclo AUTO residual en la cuenta efímera.",
          );
        }
      } else {
        failures.push(
          `no se pudo verificar el residuo de ciclos (${monitorRes.status()}).`,
        );
      }
    }

    // 4) Cierre + borrado de la cuenta efímera (cierre del ciclo de vida del fixture). El
    //    borrado exige la cuenta CERRADA (conservación contable): sin el `close` sería un
    //    400 permanente. El helper sondea/verifica cada paso y adjunta el cuerpo del fallo,
    //    para que un `400` no quede sin diagnóstico (un 400 con la cuenta ya borrada es OK).
    await disposeEphemeralAccount(request, baseURL, state.accountId, failures);

    if (failures.length > 0) {
      throw new Error(
        `Teardown del S5 no completó la limpieza:\n- ${failures.join("\n- ")}`,
      );
    }
  });

  test("GP-V288-S5-01: /auto/operar monta y declara su estado sin fabricar la operación", async ({
    page,
  }) => {
    const accountId = state.accountId;
    if (!accountId) throw new Error("fixture required");
    await seedHoyBrowserState(page, { accountId });
    await page.goto("/auto/operar");
    await expect(page.getByTestId("auto-operar-page")).toBeVisible({
      timeout: 20_000,
    });

    // La UI NO inventa una operación: o lista el ciclo durable, o declara el hueco.
    if (state.cycleId) {
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
    if (!state.cycleId) {
      declareGap(state.noCycleReason ?? NO_CYCLE_REASON);
      return;
    }
    if (!state.instrumentId || !state.strategyDefinitionId) {
      declareGap(state.noChainReason ?? NO_CHAIN_REASON);
      return;
    }
    if (!state.accountId) throw new Error("fixture required");

    await openFirstOperation(page, state.accountId);

    await expect(page.getByTestId("auto-operation-strategy")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByTestId("auto-operation-strategy-label"),
    ).toContainText(`#1 ${state.strategyLabel}`);
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
    if (!state.cycleId) {
      declareGap(state.noCycleReason ?? NO_CYCLE_REASON);
      return;
    }
    if (!state.instrumentId || !state.strategyDefinitionId) {
      declareGap(state.noChainReason ?? NO_CHAIN_REASON);
      return;
    }
    if (!state.accountId) throw new Error("fixture required");

    await openFirstOperation(page, state.accountId);

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
    expect(url.searchParams.get("instrumentId")).toBe(state.instrumentId);
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

/**
 * Declara un hueco de precondición: `skipped` con motivo por defecto, o **FALLO** si el run
 * exige el journey (`E2E_S5_REQUIRED=1`, CI del tag) — así un skip no puede dar verde.
 */
function declareGap(reason: string): void {
  if (s5Required()) {
    throw new Error(
      `E2E_S5_REQUIRED=1: precondición del S5 ausente — ${reason}`,
    );
  }
  test.skip(true, reason);
}
