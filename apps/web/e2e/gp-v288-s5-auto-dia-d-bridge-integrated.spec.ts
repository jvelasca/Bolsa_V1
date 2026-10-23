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
  type Browser,
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
import { attachS5NetworkTimings } from "./helpers/s5-network-timings";

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
const OPS_JOBS_PATH = "/api/auto/ops-jobs";
const DIA_D_REPLAY_PATH = "/api/auto/dia-d-replay";
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

/** Cuentas extra del S5-07 (se crean dentro del test y se limpian en el `afterAll`). */
const extraAccounts: string[] = [];

/** Crea una cuenta efímera y la registra para el teardown (mismo patrón que el fixture). */
async function createEphemeralAccount(
  request: APIRequestContext,
  baseURL: string,
  label: string,
): Promise<string> {
  const res = await request.post(new URL("/api/accounts", baseURL).toString(), {
    data: {
      name: `e2e-v288-s5-${label}-${randomUUID().slice(0, 8)}`,
      currency: "EUR",
      initialDeposit: 100_000,
    },
  });
  if (!res.ok()) {
    throw new Error(
      `POST /api/accounts (${label}) falló (${res.status()}): ${await res.text()}`,
    );
  }
  const id = (await body<{ data: { id: string } }>(res)).data.id;
  extraAccounts.push(id);
  return id;
}

type DiaDArtifact = {
  available: boolean;
  day?: string;
  artifactModifiedAt?: string | null;
  meta?: { account?: string | null };
  notes?: string[];
};

/** Artefacto DÍA-D que la API sirve a UNA cuenta (nunca al de otra). */
async function readDiaDArtifact(
  request: APIRequestContext,
  baseURL: string,
  accountId: string,
  day: string,
): Promise<DiaDArtifact> {
  const res = await request.get(
    new URL(
      `${DIA_D_REPLAY_PATH}/${encodeURIComponent(day)}`,
      baseURL,
    ).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!res.ok()) {
    throw new Error(
      `GET ${DIA_D_REPLAY_PATH}/${day} (${accountId}) falló (${res.status()}): ${await res.text()}`,
    );
  }
  return body<DiaDArtifact>(res);
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

/** Barras mínimas exigidas al fixture: un run sin barras devuelve 400 (no es flakiness). */
const MIN_OHLCV_BARS = 1;

/**
 * Deja los datos de mercado LISTOS antes del journey (V2.88.153).
 *
 * En frío, el run D→hoy disparaba `POST /instruments/{id}/sync` (~9 s) y `POST /backtests/run`
 * devolvía 400 porque el instrumento aún no tenía barras; el primer intento agotaba su espera
 * por una precondición de DATOS, no por la UI. El fixture la resuelve AHORA: sincroniza y exige
 * barras > 0. Un fallo aquí es un FALLO de fixture declarado (no un `skipped`).
 */
async function ensureMarketDataReady(
  request: APIRequestContext,
  baseURL: string,
  instrumentId: string,
): Promise<{ bars: number; status: string }> {
  const syncUrl = new URL(
    `/api/instruments/${encodeURIComponent(instrumentId)}/sync`,
    baseURL,
  ).toString();
  const syncRes = await request.post(syncUrl, {
    data: { yearsBack: 5 },
    timeout: 180_000,
  });
  if (!syncRes.ok()) {
    throw new Error(
      `POST ${syncUrl} falló (${syncRes.status()}): ${await syncRes.text()}`,
    );
  }
  const sync = await body<{
    data?: { status?: string; error?: string | null };
  }>(syncRes);
  const status = sync.data?.status ?? "";
  if (status === "failed") {
    throw new Error(
      `el sync de ${instrumentId} terminó en 'failed': ${sync.data?.error ?? "sin motivo declarado"}`,
    );
  }

  const ohlcvUrl = new URL(
    `/api/instruments/${encodeURIComponent(instrumentId)}/ohlcv?limit=365&timeframe=1d`,
    baseURL,
  ).toString();
  const ohlcvRes = await request.get(ohlcvUrl, { timeout: 60_000 });
  if (!ohlcvRes.ok()) {
    throw new Error(
      `GET ${ohlcvUrl} falló (${ohlcvRes.status()}): ${await ohlcvRes.text()}`,
    );
  }
  const ohlcv = await body<{ meta?: { count?: number } }>(ohlcvRes);
  const bars = Number(ohlcv.meta?.count ?? 0);
  if (!(bars >= MIN_OHLCV_BARS)) {
    throw new Error(
      `el instrumento ${instrumentId} no declara barras tras el sync (count=${bars}); ` +
        "el run D→hoy devolvería 400 por precondición de datos.",
    );
  }
  return { bars, status: status || "unknown" };
}

/**
 * Precalienta las rutas del journey (V2.88.153): la primera visita paga la transformación de
 * módulos de Vite. Es SOLO latencia — se ejecuta en `beforeAll` y, si falla, se anota: las
 * aserciones reales del test siguen siendo el gate (no se relajan timeouts ni reintentos).
 */
async function warmJourneyRoutes(
  browser: Browser,
  baseURL: string,
  accountId: string,
): Promise<string | null> {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await seedHoyBrowserState(page, { accountId });
    await page.goto(new URL("/auto/operar", baseURL).toString());
    await expect(page.getByTestId("auto-operar-page")).toBeVisible({
      timeout: 120_000,
    });
    await page.goto(new URL("/backtests?tab=run", baseURL).toString());
    await expect(page.getByTestId("backtests-keepalive-host")).toBeVisible({
      timeout: 120_000,
    });
    return null;
  } catch (err) {
    return err instanceof Error ? err.message : String(err);
  } finally {
    await context.close();
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
      // H6 — la identidad EXACTA que el ciclo declara debe ser la MISMA clave que el
      // `strategyType` del TOP que este spec siembra justo después (`PRESET_KEY`), o el CTA
      // «Verificar D→hoy» queda inhabilitado por el fail-closed (hueco declarado, no un bug).
      strategyPresetKey: PRESET_KEY,
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

  // Datos de mercado ANTES del journey (V2.88.153): sin barras, el run real devuelve 400 y el
  // primer intento se agota esperando una precondición de DATOS, no de UI.
  await ensureMarketDataReady(request, baseURL, instrument.id);

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

  test.beforeAll(async ({ request, baseURL, browser }) => {
    // V2.88.153: el fixture (gate + seed durable + precalentamiento de Vite) excede el
    // timeout por defecto de hook (30 s). Se declara explícitamente para que el
    // precalentamiento no convierta el arranque en frío en un falso rojo.
    test.setTimeout(240_000);
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
    // Precalentamiento de Vite (solo latencia): no altera los gates del journey.
    if (state.accountId && !state.seedError) {
      const warmError = await warmJourneyRoutes(
        browser,
        baseURL,
        state.accountId,
      );
      if (warmError) {
        test.info().annotations.push({
          type: "precalentamiento",
          description: `el precalentamiento de rutas no completó: ${warmError}`,
        });
      }
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

    // 5) Cuentas EXTRA del S5-07: mismo cierre + borrado verificado (no-residuo).
    for (const extra of extraAccounts.splice(0)) {
      await disposeEphemeralAccount(request, baseURL, extra, failures);
    }

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
    // H6 — el CTA verifica la estrategia EJECUTADA del ciclo, resuelta por identidad EXACTA
    // (`presetKey`) dentro del TOP sembrado; NO la «mejor disponible» por accidente.
    await expect(
      page.getByTestId("auto-operation-strategy-executed"),
    ).toHaveAttribute("data-verify-target", "executed");
    await expect(
      page.getByTestId("auto-operation-strategy-verify-dia-d"),
    ).toHaveAttribute("data-verify-target", "executed");
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

  test("GP-V288-S5-04: guardar registra el enlace durable verificación ↔ cicloId (P2)", async ({
    page,
    request,
    baseURL,
  }, testInfo) => {
    if (!state.cycleId) {
      declareGap(state.noCycleReason ?? NO_CYCLE_REASON);
      return;
    }
    if (!state.instrumentId || !state.strategyDefinitionId) {
      declareGap(state.noChainReason ?? NO_CHAIN_REASON);
      return;
    }
    if (!state.accountId) throw new Error("fixture required");
    if (!baseURL) throw new Error("baseURL required");
    const accountId = state.accountId;

    // Precondición — IDEMPOTENTE ante reintentos del runner: el POST del panel es único por
    // (cycleId, diaD, endDate, mode), así que el reintento de Playwright (`retries: 1` en CI)
    // puede encontrar el enlace YA registrado por su intento anterior. Se comprueba que el
    // endpoint responde y se declara el baseline, pero NO se exige `total == 0`: ese supuesto
    // rompía el reintento (residuo durable del propio intento previo) y hacía imposible el verde.
    // El RESULTADO que el test fija es el enlace durable al terminar (assert final).
    const listUrl = new URL(
      `/api/auto/dia-d-verifications?cycleId=${encodeURIComponent(state.cycleId)}`,
      baseURL,
    ).toString();
    const headers = { "X-Account-Id": accountId };

    // Medición READ-ONLY de la red (arranque en frío): registra el tiempo de CADA petición
    // (API + módulos de Vite) para atribuir los ~60 s del primer intento a una FASE concreta,
    // no solo a un `test.step`. NO cambia `timeout`/`retries`/aserciones; el informe se vuelca
    // SIEMPRE (también en rojo) vía `finally`. Sin `S5_TIMINGS_OUT`, es un no-op.
    const netTimings = attachS5NetworkTimings(page, testInfo);
    try {
      const before = await request.get(listUrl, { headers });
      expect(before.ok()).toBe(true);

      // `test.step` = INSTRUMENTACIÓN read-only: nombra las fases cuyo tiempo consume el primer
      // intento del journey (ese primer intento > 60 s es el motivo de la flakiness de CI). NO
      // cambia timeouts, retries ni aserciones; solo hace medible QUÉ fase es lenta.
      await test.step("S5-04 · abrir la operación AUTO", async () => {
        await openFirstOperation(page, accountId);
      });

      const save = page.getByRole("button", { name: "Guardar Evidence" });
      await test.step("S5-04 · lanzar la verificación D→hoy", async () => {
        const cta = page.getByTestId("auto-operation-strategy-verify-dia-d");
        await expect(cta).toBeVisible({ timeout: 20_000 });
        await expect(cta).toBeEnabled();

        // Se observa la RESPUESTA real del run (registrada ANTES del clic): un 4xx/5xx es un
        // fallo declarado del run, no una espera que se agota sin diagnóstico.
        const runResponse = page.waitForResponse(
          (res) => {
            if (res.request().method() !== "POST") return false;
            try {
              return new URL(res.url()).pathname === RUN_PATH;
            } catch {
              return false;
            }
          },
          { timeout: 90_000 },
        );
        await cta.click();
        const response = await runResponse;
        if (!response.ok()) {
          throw new Error(
            `POST ${RUN_PATH} respondió ${response.status()}: ${await response
              .text()
              .catch(() => "(cuerpo ilegible)")}`,
          );
        }
      });

      await test.step("S5-04 · esperar la evidencia de la sesión LAB", async () => {
        // Estado OBSERVABLE del host (V2.88.153): `ready | error` son hechos de la UI, no la
        // aparición de un botón. Un `error` se propaga con su texto visible.
        const host = page
          .getByTestId("dia-d-replay-embedded")
          .or(page.getByTestId("dia-d-replay-full-bleed"))
          .first();
        await expect(host).toBeVisible({ timeout: 60_000 });
        await expect
          .poll(async () => (await host.getAttribute("data-run-state")) ?? "", {
            timeout: 60_000,
            message: "el run D→hoy debe declarar un estado terminal",
          })
          .toMatch(/^(ready|error)$/);

        const runState =
          (await host.getAttribute("data-run-state")) ?? "unknown";
        const runError = page.getByTestId("dia-d-run-error");
        const runErrorText =
          (await runError.count()) > 0
            ? ((await runError.first().textContent()) ?? "").trim()
            : "";
        await testInfo.attach("s5-04-run-state", {
          body: JSON.stringify({ runState, runError: runErrorText }, null, 2),
          contentType: "application/json",
        });
        if (runState === "error") {
          throw new Error(
            `el run D→hoy terminó en error: ${runErrorText || "(sin texto visible)"}`,
          );
        }
        await expect(host).toHaveAttribute("data-run-state", "ready");

        // La evidencia de sesión aloja el botón de guardado; se exige explícitamente.
        await expect(page.getByTestId("dia-d-session-evidence")).toBeVisible({
          timeout: 30_000,
        });
        await expect(save).toBeVisible({ timeout: 30_000 });
        await expect(save).toBeEnabled({ timeout: 30_000 });
      });

      await test.step("S5-04 · guardar y verificar el enlace durable", async () => {
        await save.click();
        await expect(
          page.getByText("Guardado", { exact: false }).first(),
        ).toBeVisible({
          timeout: 30_000,
        });

        // El registro durable queda ENLAZADO al ciclo desde el que se lanzó (no basta con el laboratorio):
        // se exige una fila con el `cycleId` Y el `instrumentId` del ciclo (identidad del enlace).
        await expect
          .poll(
            async () => {
              const res = await request.get(listUrl, { headers });
              if (!res.ok()) return -1;
              const json = await body<{
                data: Array<{ cycleId: string; instrumentId: string }>;
              }>(res);
              return json.data.filter(
                (v) =>
                  v.cycleId === state.cycleId &&
                  v.instrumentId === state.instrumentId,
              ).length;
            },
            { timeout: 30_000 },
          )
          .toBeGreaterThan(0);
      });
    } finally {
      netTimings.flush();
    }
  });
  test("GP-V288-S5-05: operativa diaria y DÍA-D manual por la cola durable (P5)", async ({
    request,
    baseURL,
  }) => {
    const accountId = state.accountId;
    if (!accountId) throw new Error("fixture required");
    if (!baseURL) throw new Error("baseURL required");
    const headers = { "X-Account-Id": accountId };
    const day = new Date().toISOString().slice(0, 10);

    type JobView = {
      id: string;
      status: string;
      error?: string | null;
      progress?: Record<string, unknown>;
    };

    const getJob = async (id: string): Promise<JobView> => {
      const res = await request.get(
        new URL(`/api/auto/ops-jobs/${id}`, baseURL).toString(),
        { headers },
      );
      expect(res.ok()).toBe(true);
      return body<JobView>(res);
    };

    /**
     * La cola es durable: este harness arranca SOLO `uvicorn` (sin
     * `scheduler_worker`), así que un job puede quedarse `queued`. Se espera un
     * desenlace corto y, si no llega, se declara como ANOTACIÓN (no skip): lo que
     * se verifica aquí es la semántica real de la cola (encolar + leer +
     * fail-closed); el ciclo completo lo cubre el E2E mock.
     */
    const settle = async (id: string): Promise<JobView> => {
      const deadline = Date.now() + 8_000;
      let job = await getJob(id);
      while (job.status === "queued" || job.status === "running") {
        if (Date.now() >= deadline) break;
        await new Promise((resolve) => setTimeout(resolve, 500));
        job = await getJob(id);
      }
      return job;
    };

    const annotatePending = (kind: string, job: JobView) => {
      if (job.status === "queued" || job.status === "running") {
        test.info().annotations.push({
          type: "hueco-entorno",
          description: `scheduler_worker no arrancado: ${kind} queda en cola durable (${job.status}).`,
        });
      }
    };

    // 1) La UI y el scheduler encolan el MISMO job: se comprueba por la ruta real.
    const dailyEnqueue = await request.post(
      new URL("/api/auto/ops-jobs", baseURL).toString(),
      {
        headers,
        data: { kind: "estudio_daily", day },
      },
    );
    expect(dailyEnqueue.ok()).toBe(true);
    const dailyJob = await body<{ id: string; kind: string; day: string }>(
      dailyEnqueue,
    );
    expect(dailyJob.kind).toBe("estudio_daily");

    const dailyFinal = await settle(dailyJob.id);
    annotatePending("estudio_daily", dailyFinal);
    if (dailyFinal.status === "failed") {
      // Fail-closed DECLARADO: sin universo ESTUDIO (o sin barras) el job falla con
      // motivo y CERO opiniones; no es un skip, es el contrato del servicio.
      expect((dailyFinal.error ?? "").length).toBeGreaterThan(0);
    }

    // 2) El parte durable es coherente: N valores y contadores que suman N.
    const dailyRes = await request.get(
      new URL(
        `/api/auto/estudio-daily?asOf=${encodeURIComponent(dailyJob.day)}`,
        baseURL,
      ).toString(),
      { headers },
    );
    expect(dailyRes.ok()).toBe(true);
    const daily = await body<{
      report: {
        status: string;
        scannedCount: number;
        counts: Record<string, number>;
        values: unknown[];
        countsConsistent: boolean;
      } | null;
      notes: string[];
    }>(dailyRes);
    if (daily.report) {
      const { counts, scannedCount, values } = daily.report;
      expect(values.length).toBe(scannedCount);
      if (daily.report.countsConsistent) {
        expect(
          Number(counts.ok ?? 0) +
            Number(counts.no_signal ?? 0) +
            Number(counts.no_plan ?? 0) +
            Number(counts.error ?? 0),
        ).toBe(scannedCount);
      }
      // Un universo vacío se declara; nunca se finge un parte con valores inventados.
      if (daily.report.status === "empty") expect(values.length).toBe(0);
    }

    // 3) DÍA-D manual: encola el replay y su desenlace valida el artefacto por cuenta y día.
    const replayEnqueue = await request.post(
      new URL("/api/auto/ops-jobs", baseURL).toString(),
      {
        headers,
        data: { kind: "dia_d_replay", day },
      },
    );
    expect(replayEnqueue.ok()).toBe(true);
    const replayJob = await body<{ id: string }>(replayEnqueue);
    const replayFinal = await settle(replayJob.id);
    annotatePending("dia_d_replay", replayFinal);

    const artifactRes = await request.get(
      new URL(
        `/api/auto/dia-d-replay/${encodeURIComponent(day)}`,
        baseURL,
      ).toString(),
      { headers },
    );
    expect(artifactRes.ok()).toBe(true);
    const artifact = await body<{
      available: boolean;
      day?: string;
      meta?: { account?: string | null };
    }>(artifactRes);
    if (artifact.available) {
      // Un artefacto de OTRA cuenta/día nunca se acepta como evidencia.
      expect(artifact.day).toBe(day);
      expect(artifact.meta?.account).toBe(accountId);
    } else {
      // `completed` exige exit 0 + artefacto validado: sin artefacto no puede estar completed.
      expect(replayFinal.status).not.toBe("completed");
    }
  });

  test("GP-V288-S5-06: la UI diaria encola el job durable y no vende un dry-run como orden (P5)", async ({
    page,
    request,
    baseURL,
  }) => {
    const accountId = state.accountId;
    if (!accountId) throw new Error("fixture required");
    if (!baseURL) throw new Error("baseURL required");
    const headers = { "X-Account-Id": accountId };

    // Falsable: si el panel volviera a sondear el monitor oculto, esta lista no estaría vacía.
    const monitorCalls: string[] = [];
    page.on("request", (req) => {
      try {
        if (new URL(req.url()).pathname === MONITOR_PATH)
          monitorCalls.push(req.url());
      } catch {
        /* URL no parseable: no es una petición del monitor */
      }
    });

    await seedHoyBrowserState(page, { accountId });
    await page.goto("/auto-monitor?mode=daily");
    await expect(page.getByTestId("estudio-daily-ops-panel")).toBeVisible({
      timeout: 20_000,
    });

    // Semántica: el estado `ok` del parte es un PLAN PROPUESTO (dry-run), nunca «disparado».
    await expect(page.getByTestId("estudio-daily-legend")).toContainText(
      "Decisión propuesta",
    );
    await expect(page.getByTestId("estudio-daily-legend")).toContainText(
      "no es una orden",
    );
    await expect(page.getByText(/Plan disparado/i)).toHaveCount(0);

    // El «Actualizar» global no existe en `daily`: refrescaría el monitor oculto.
    await expect(page.getByTestId("auto-monitor-refresh")).toHaveCount(0);

    // Día fijo: no compite con el job de S5-05 (hoy) ni con el artefacto del día.
    const asOf = "2026-01-02";
    await page.getByTestId("estudio-daily-asof").fill(asOf);
    const runButton = page.getByTestId("estudio-daily-run");
    await expect(runButton).toBeEnabled();
    await runButton.click();
    await expect(page.getByTestId("estudio-daily-job-status")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("estudio-daily-job-status")).toContainText(
      asOf,
    );

    // El botón de la UI encola EL MISMO job de la cola durable: se lee por la ruta real.
    const jobsRes = await request.get(
      new URL(
        `${OPS_JOBS_PATH}?kind=estudio_daily&day=${encodeURIComponent(asOf)}&limit=5`,
        baseURL,
      ).toString(),
      { headers },
    );
    expect(jobsRes.ok()).toBe(true);
    const jobs = await body<{
      jobs: Array<{
        id: string;
        kind: string;
        day: string | null;
        status: string;
      }>;
    }>(jobsRes);
    const observed = jobs.jobs.find(
      (job) => job.kind === "estudio_daily" && job.day === asOf,
    );
    expect(
      observed,
      "la UI debe encolar un job estudio_daily del día pedido",
    ).toBeTruthy();

    // «Actualizar» del panel refresca lo VISIBLE y no toca el monitor desactivado.
    monitorCalls.length = 0;
    await page.getByTestId("estudio-daily-refresh").click();
    await expect(page.getByTestId("estudio-daily-refresh")).toBeEnabled({
      timeout: 15_000,
    });
    expect(monitorCalls).toHaveLength(0);

    // El refresco es asíncrono: se sondea el enlace contextual (hasta 20 s) en lugar de
    // decidir sobre una lectura transitoria del parte.
    const contextLink = page.getByTestId("estudio-daily-value-dia-d").first();
    let hasContextLink = false;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      if ((await contextLink.count()) > 0) {
        hasContextLink = true;
        break;
      }
      await page.waitForTimeout(500);
    }

    // Si el parte trae valores, la ficha enlaza a DÍA-D con contexto DECLARADO (global).
    if (hasContextLink) {
      // La evidencia durable (cadena, selector y DÍA-D del valor) es DETALLE TÉCNICO: vive
      // tras el desplegable único de la casa. Se abre para poder leerla (la vista inicial
      // sólo responde a las cuatro preguntas).
      const card = contextLink.locator("xpath=ancestor::li[1]");
      // `first()`: el disclosure RAÍZ de la ficha (dentro vive otro disclosure técnico del
      // selector con su propio testid; ambos comparten el rótulo único de la casa).
      await card
        .getByTestId("estudio-daily-value-technical")
        .locator("summary")
        .first()
        .click();
      await expect(card.getByTestId("estudio-daily-value-chain")).toBeVisible({
        timeout: 20_000,
      });
      await expect(card.getByTestId("estudio-chain-attribution")).toContainText(
        "Cadena histórica del valor",
      );
      await expect(
        card.getByTestId("estudio-chain-dia-d-verify"),
      ).toBeVisible();

      await contextLink.click();
      await expect(page).toHaveURL(/mode=dia-d/, { timeout: 20_000 });
      const url = new URL(page.url());
      expect(url.searchParams.get("symbol")).toBeTruthy();
      expect(url.searchParams.get("day")).toBe(asOf);
      await expect(page.getByTestId("dia-d-auto-symbol-context")).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.getByTestId("dia-d-auto-symbol-context")).toContainText(
        "global del día",
      );
      await expect(page.getByTestId("dia-d-auto-provenance")).toBeVisible();
    } else {
      // Sin valores no hay ficha que enlazar: se exige un estado DECLARADO (parte ausente,
      // parte vacío o hueco de universo), nunca un panel en blanco.
      const declaredAbsence = page
        .locator(
          '[data-testid="estudio-daily-empty"],' +
            '[data-testid="estudio-daily-no-values"],' +
            '[data-testid="estudio-daily-universe-gap"]',
        )
        .first();
      await expect(declaredAbsence).toBeVisible({ timeout: 20_000 });
      test.info().annotations.push({
        type: "hueco-entorno",
        description:
          "Sin valores en el parte (worker no arrancado, sin barras o universo vacío): el panel declara el hueco y no hay ficha para el enlace contextual.",
      });
    }
  });

  test("GP-V288-S5-07: el artefacto DÍA-D de una cuenta NO se sirve a otra (P0)", async ({
    request,
    baseURL,
  }) => {
    const accountA = state.accountId;
    if (!accountA) throw new Error("fixture required");
    if (!baseURL) throw new Error("baseURL required");
    const day = new Date().toISOString().slice(0, 10);

    // C no encola nada: es el CONTROL NEGATIVO del aislamiento.
    const accountB = await createEphemeralAccount(request, baseURL, "iso-b");
    const accountC = await createEphemeralAccount(request, baseURL, "iso-c");

    const replayJobs: Array<{ accountId: string; jobId: string }> = [];
    for (const accountId of [accountA, accountB]) {
      const res = await request.post(
        new URL(OPS_JOBS_PATH, baseURL).toString(),
        {
          headers: { "X-Account-Id": accountId },
          data: { kind: "dia_d_replay", day },
        },
      );
      expect(res.ok()).toBe(true);
      const job = await body<{ id: string }>(res);
      replayJobs.push({ accountId, jobId: job.id });
    }

    // Desenlace ACOTADO del replay: sin worker el job queda en cola y se declara (no se finge
    // el artefacto). El aislamiento de ficheros ya lo mide la prueba integrada de Python.
    const settleReplay = async (
      jobId: string,
      accountId: string,
    ): Promise<string> => {
      const deadline = Date.now() + 10_000;
      let status = "queued";
      for (;;) {
        const res = await request.get(
          new URL(`${OPS_JOBS_PATH}/${jobId}`, baseURL).toString(),
          { headers: { "X-Account-Id": accountId } },
        );
        if (!res.ok()) break;
        const job = await body<{ status: string; error?: string | null }>(res);
        status = job.status;
        if (status !== "queued" && status !== "running") break;
        if (Date.now() >= deadline) break;
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      return status;
    };
    const replayOutcomes = await Promise.all(
      replayJobs.map(({ jobId, accountId }) => settleReplay(jobId, accountId)),
    );

    const a = await readDiaDArtifact(request, baseURL, accountA, day);
    const b = await readDiaDArtifact(request, baseURL, accountB, day);
    const c = await readDiaDArtifact(request, baseURL, accountC, day);

    // Cada artefacto declara SU cuenta y SU día; uno ajeno es indistinguible de inexistente.
    for (const [account, artifact] of [
      [accountA, a],
      [accountB, b],
    ] as const) {
      if (!artifact.available) continue;
      expect(artifact.day).toBe(day);
      expect(artifact.meta?.account).toBe(account);
    }

    // Control negativo: C nunca encoló el día ⇒ no ve artefacto NI lo lista.
    expect(c.available).toBe(false);
    expect(c.notes ?? []).not.toContain("legacy_artifact");
    const cListRes = await request.get(
      new URL(DIA_D_REPLAY_PATH, baseURL).toString(),
      { headers: { "X-Account-Id": accountC } },
    );
    expect(cListRes.ok()).toBe(true);
    const cList = await body<{ days: string[] }>(cListRes);
    expect(cList.days).not.toContain(day);

    // Si A y B produjeron artefacto, son DOS artefactos: la cuenta sellada difiere
    // (una colisión de fichero devolvería el mismo `meta.account` a las dos).
    if (a.available && b.available) {
      expect(a.meta?.account).toBe(accountA);
      expect(b.meta?.account).toBe(accountB);
      expect(a.meta?.account).not.toBe(b.meta?.account);
    } else {
      test.info().annotations.push({
        type: "hueco-entorno",
        description: `Sin dos artefactos DÍA-D que comparar (replay: ${replayOutcomes.join(", ")}); el aislamiento de ficheros ya lo mide la prueba integrada de Python.`,
      });
    }
  });

  test("GP-V288-S5-08: evidencia por valor y DÍA-D del valor no heredan el artefacto del día", async ({
    request,
    baseURL,
  }) => {
    const accountA = state.accountId;
    if (!accountA) throw new Error("fixture required");
    if (!baseURL) throw new Error("baseURL required");
    const day = new Date().toISOString().slice(0, 10);
    const headersA = { "X-Account-Id": accountA };

    const catalogRes = await request.get(
      new URL("/api/instruments", baseURL).toString(),
    );
    expect(catalogRes.ok()).toBe(true);
    const catalog = await body<{ data: Array<{ id: string; symbol: string }> }>(
      catalogRes,
    );
    const target = (catalog.data ?? [])[0] ?? null;
    if (!target) {
      declareGap(NO_CATALOG_REASON);
      return;
    }
    const symbol = target.symbol.trim().toUpperCase();

    // 1) La cadena es read-only y NO emite CONFIRMED (eso es OPERACIÓN, no software).
    const chainRes = await request.get(
      new URL("/api/auto/estudio-chain?limit=200", baseURL).toString(),
      { headers: headersA },
    );
    expect(chainRes.ok()).toBe(true);
    const chainA = await body<{
      available: boolean;
      readOnly: boolean;
      summary: { cycles: number; values: number } | null;
      values: Array<{ cycles: unknown[] }>;
      notes: string[];
      limits: string[];
    }>(chainRes);
    expect(chainA.readOnly).toBe(true);
    expect(JSON.stringify(chainA)).not.toContain("CONFIRMED");

    // 2) Aislamiento por cuenta: C no ve el ciclo durable de A (ni al revés está obligado).
    const accountC = await createEphemeralAccount(
      request,
      baseURL,
      "iso-chain",
    );
    const chainCRes = await request.get(
      new URL("/api/auto/estudio-chain?limit=200", baseURL).toString(),
      { headers: { "X-Account-Id": accountC } },
    );
    expect(chainCRes.ok()).toBe(true);
    const chainC = await body<{
      available: boolean;
      summary: { cycles: number } | null;
      values: Array<{ cycles: unknown[] }>;
    }>(chainCRes);
    if ((chainA.summary?.cycles ?? 0) > 0) {
      expect(chainC.summary?.cycles ?? 0).toBe(0);
      expect(chainC.values.every((value) => value.cycles.length === 0)).toBe(
        true,
      );
    } else {
      test.info().annotations.push({
        type: "hueco-entorno",
        description:
          "La cuenta A no declara ciclos durables (worker del motor no arrancado): el aislamiento positivo de ciclos no se puede medir aquí.",
      });
    }

    // 3) El job por valor exige símbolo (fail-closed) y lo normaliza en el payload.
    const missing = await request.post(
      new URL(OPS_JOBS_PATH, baseURL).toString(),
      { headers: headersA, data: { kind: "dia_d_value_replay", day } },
    );
    expect([400, 422]).toContain(missing.status());

    const created = await request.post(
      new URL(OPS_JOBS_PATH, baseURL).toString(),
      {
        headers: headersA,
        data: {
          kind: "dia_d_value_replay",
          day,
          payload: { symbol: symbol.toLowerCase() },
        },
      },
    );
    expect(created.ok()).toBe(true);
    const valueJob = await body<{
      id: string;
      kind: string;
      day: string;
      payload: { symbol?: string };
    }>(created);
    expect(valueJob.kind).toBe("dia_d_value_replay");
    expect(valueJob.payload.symbol).toBe(symbol);

    // Serialización declarada del hueco (kind, cuenta, día): otro símbolo del mismo día
    // devuelve el job ACTIVO del primero (o uno nuevo si ya terminó, que se declara).
    const other = await request.post(
      new URL(OPS_JOBS_PATH, baseURL).toString(),
      {
        headers: headersA,
        data: {
          kind: "dia_d_value_replay",
          day,
          payload: { symbol: "ZZE2E" },
        },
      },
    );
    expect(other.ok()).toBe(true);
    const otherJob = await body<{ id: string; payload: { symbol?: string } }>(
      other,
    );
    if (otherJob.id === valueJob.id) {
      expect(otherJob.payload.symbol).toBe(symbol);
    } else {
      test.info().annotations.push({
        type: "hueco-entorno",
        description:
          "El replay del primer valor ya había terminado: el segundo símbolo obtuvo su propio job (no hay serialización que observar).",
      });
    }

    // 4) NUNCA se rellena la verificación del valor con el artefacto del día completo.
    const dayArtifact = await readDiaDArtifact(request, baseURL, accountA, day);
    const valueRes = await request.get(
      new URL(
        `${DIA_D_REPLAY_PATH}/${encodeURIComponent(day)}/value/${encodeURIComponent(symbol)}`,
        baseURL,
      ).toString(),
      { headers: headersA },
    );
    expect(valueRes.ok()).toBe(true);
    const valueArtifact = await body<{
      available: boolean;
      symbol: string | null;
      meta: { account?: string | null; watch?: string[] };
      notes: string[];
    }>(valueRes);
    if (valueArtifact.available) {
      // Si existe, es SUYO: declara el símbolo y un watch de exactamente ese valor.
      expect(valueArtifact.symbol).toBe(symbol);
      expect(valueArtifact.meta.account).toBe(accountA);
      expect(valueArtifact.meta.watch).toEqual([symbol]);
    } else {
      expect(valueArtifact.notes).toContain("artifact_not_found");
      if (dayArtifact.available) {
        // Con el artefacto del día DISPONIBLE, la ruta por valor sigue en hueco: no hay fallback.
        test.info().annotations.push({
          type: "no-fallback",
          description:
            "El artefacto del día existe y la verificación del valor sigue ausente: la ruta por valor no hereda la evidencia del watch completo.",
        });
      }
    }
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
