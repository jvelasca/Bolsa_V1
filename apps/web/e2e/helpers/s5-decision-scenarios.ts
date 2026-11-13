/**
 * S5 · Escenarios de producto del rediseño S1–S4.
 *
 * Un escenario = una foto determinista de las tres fuentes que el usuario ve en la
 * ventana maximizada de DECISIÓN: el dictamen (S1), la cartera medida (S3) y las
 * compuertas de entrada (kill switch / incidentes / modo). El fixture NO decide
 * nada: solo sirve los datos que la UI debe clasificar y ordenar.
 *
 * Los seis escenarios son los que exige la certificación S5:
 *   1. recomendación favorable sin posición
 *   2. posición abierta con respaldo
 *   3. posición sin respaldo
 *   4. sin datos suficientes (cartera no medida)
 *   5. entrada bloqueada
 *   6. salida permitida con entradas bloqueadas
 *
 * @see docs/engineering/certificacion-s5-rediseno-2026-11-12.md
 */

import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import type { Page, Route } from "@playwright/test";
import { E2E_ACCOUNT_ID, E2E_INSTRUMENT_ID, E2E_SYMBOL } from "./ids";
import { installMercadoApiMocks } from "./e2e-mock-installers";
import { mercadoOpenPosition, seedMercadoBrowserState } from "./mercado";

export type S5ScenarioId =
  | "favorable_sin_posicion"
  | "posicion_con_respaldo"
  | "posicion_sin_respaldo"
  | "sin_datos"
  | "entrada_bloqueada"
  | "salida_con_entradas_bloqueadas";

export type S5Scenario = {
  id: S5ScenarioId;
  title: string;
  /** Postura del dictamen; `null` = sin dictamen (hueco declarado). */
  stance: "buy" | "hold_watch" | "overbought" | null;
  ioScore: number | null;
  hasPosition: boolean;
  /** `false` → `GET /api/portfolio` falla: la cartera no se midió. */
  portfolioMeasured: boolean;
  entriesBlocked: boolean;
  expect: {
    /** `data-state` del hero (categoría S3). */
    state: string;
    stateLabel: string;
    /** `data-action-hint` del hero (vía de actuación S4). */
    actionHint: string;
    actionLabel: string;
    blockedReason: string | null;
    /** Etiqueta S1 visible en el dictamen; `null` = sin dictamen. */
    stanceLabel: string | null;
    /** `data-phase` del cockpit operativo (ACCIÓN). */
    cockpitPhase: string;
    /** El CTA de preparar existe y está habilitado. */
    proposeEnabled: boolean;
  };
};

const BASE_OPINION = {
  id: "op-s5",
  instrumentId: E2E_INSTRUMENT_ID,
  asOfBarDate: "2026-11-12",
  dictamenStars: 4,
  distress: false,
  reasons: [] as string[],
  source: "eod_batch",
  engineVersion: "opinion_v1",
  idempotencyKey: "s5-idempotency",
  computedAt: "2026-11-12T18:00:00.000Z",
  createdAt: "2026-11-12T18:00:00.000Z",
  updatedAt: "2026-11-12T18:00:00.000Z",
};

export const S5_SCENARIOS: readonly S5Scenario[] = [
  {
    id: "favorable_sin_posicion",
    title: "Recomendación favorable sin posición",
    stance: "buy",
    ioScore: 85,
    hasPosition: false,
    portfolioMeasured: true,
    entriesBlocked: false,
    expect: {
      state: "recomendacion_favorable",
      stateLabel: "Recomendación favorable",
      actionHint: "entrada_disponible",
      actionLabel: "Entrada disponible",
      blockedReason: null,
      stanceLabel: "Comprar",
      cockpitPhase: "preparada",
      proposeEnabled: true,
    },
  },
  {
    id: "posicion_con_respaldo",
    title: "Posición abierta con respaldo",
    stance: "hold_watch",
    ioScore: 72,
    hasPosition: true,
    portfolioMeasured: true,
    entriesBlocked: false,
    expect: {
      state: "posicion_abierta",
      stateLabel: "Posición abierta",
      actionHint: "salida_en_accion",
      actionLabel: "Salida en ACCIÓN",
      blockedReason: null,
      stanceLabel: "Mantener",
      cockpitPhase: "posicion",
      proposeEnabled: false,
    },
  },
  {
    id: "posicion_sin_respaldo",
    title: "Posición sin respaldo",
    stance: "overbought",
    ioScore: 61,
    hasPosition: true,
    portfolioMeasured: true,
    entriesBlocked: false,
    expect: {
      state: "posicion_sin_respaldo",
      stateLabel: "Posición sin respaldo",
      actionHint: "salida_en_accion",
      actionLabel: "Salida en ACCIÓN",
      blockedReason: null,
      stanceLabel: "Sin respaldo",
      cockpitPhase: "posicion",
      proposeEnabled: false,
    },
  },
  {
    id: "sin_datos",
    title: "Sin datos suficientes",
    stance: "buy",
    ioScore: 85,
    hasPosition: false,
    portfolioMeasured: false,
    entriesBlocked: false,
    expect: {
      state: "sin_datos",
      stateLabel: "Sin datos suficientes",
      actionHint: "sin_actuacion",
      actionLabel: "Sin actuación",
      blockedReason: null,
      stanceLabel: "Comprar",
      // Sin cartera medida no se construye verdad de entrada: la fase se queda en
      // el plan leído, pero el CTA de preparar no se habilita.
      cockpitPhase: "preparada",
      proposeEnabled: false,
    },
  },
  {
    id: "entrada_bloqueada",
    title: "Entrada bloqueada",
    stance: "buy",
    ioScore: 85,
    hasPosition: false,
    portfolioMeasured: true,
    entriesBlocked: true,
    expect: {
      state: "recomendacion_favorable",
      stateLabel: "Recomendación favorable",
      actionHint: "entrada_bloqueada",
      actionLabel: "Entrada bloqueada",
      blockedReason: "entradas_bloqueadas",
      stanceLabel: "Comprar",
      cockpitPhase: "preparada",
      proposeEnabled: false,
    },
  },
  {
    id: "salida_con_entradas_bloqueadas",
    title: "Salida permitida con entradas bloqueadas",
    stance: "hold_watch",
    ioScore: 72,
    hasPosition: true,
    portfolioMeasured: true,
    entriesBlocked: true,
    expect: {
      state: "posicion_abierta",
      stateLabel: "Posición abierta",
      actionHint: "salida_en_accion",
      actionLabel: "Salida en ACCIÓN",
      blockedReason: null,
      stanceLabel: "Mantener",
      cockpitPhase: "posicion",
      proposeEnabled: false,
    },
  },
];

export function s5Scenario(id: S5ScenarioId): S5Scenario {
  const found = S5_SCENARIOS.find((scenario) => scenario.id === id);
  if (!found) throw new Error(`Escenario S5 desconocido: ${id}`);
  return found;
}

function opinionBody(scenario: S5Scenario) {
  if (scenario.stance == null) return { data: [] };
  return {
    data: [
      {
        ...BASE_OPINION,
        stance: scenario.stance,
        ioScore: scenario.ioScore,
      },
    ],
  };
}

function portfolioBody(scenario: S5Scenario) {
  const positions = scenario.hasPosition
    ? [mercadoOpenPosition({ id: "pos-s5-1", tradePlanId: "tp-s5-1" })]
    : [];
  return {
    data: {
      accountId: E2E_ACCOUNT_ID,
      portfolio: { cash: 100_000, totalEquity: 101_020 },
      positions,
    },
  };
}

function killSwitchBody(scenario: S5Scenario) {
  return {
    effective: scenario.entriesBlocked,
    env: scenario.entriesBlocked,
    runtimeMemory: false,
    redis: null,
    paperDExecuteEnv: false,
    brokerVenue: "paper",
  };
}

function decisionStudiesBody() {
  return {
    data: {
      accountId: E2E_ACCOUNT_ID,
      studies: [
        {
          decisionId: "dec-s5-1",
          instrumentId: E2E_INSTRUMENT_ID,
          symbol: E2E_SYMBOL,
          hasOperationalPlan: true,
          tradePlanStatus: "ARMED",
          studiedAt: "2026-11-12T09:00:00.000Z",
          entry: 100,
          stop: 95,
          target1: 105,
          target2: 110,
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    },
  };
}

const estudioList = {
  id: "estudio",
  name: "Estudio",
  description: "Universo S5",
  kind: "estudio",
  instrumentIds: [E2E_INSTRUMENT_ID],
};

/**
 * Serie diaria determinista con pivotes: 140 velas bastan para que S2 declare
 * estructura `ok` (la ventana mínima es 80) y para que el gráfico pinte.
 */
export function s5DailyBars(count = 140) {
  const bars = [];
  const start = Date.UTC(2026, 0, 5);
  let previousClose = 100;
  for (let index = 0; index < count; index += 1) {
    const timestamp = new Date(start + index * 86_400_000).toISOString();
    const close =
      100 + Math.sin(index / 6) * 8 + Math.sin(index / 23) * 4 + index * 0.02;
    const open = previousClose + Math.sin(index / 2.7) * 0.35;
    const high = Math.max(open, close) + 0.6 + Math.abs(Math.cos(index / 3)) * 0.5;
    const low = Math.min(open, close) - 0.6 - Math.abs(Math.sin(index / 4)) * 0.5;
    previousClose = close;
    bars.push({
      timestamp,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: 1_000_000 + index * 1_000,
      adjClose: Number(close.toFixed(2)),
      source: "s5-e2e",
    });
  }
  return bars;
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/**
 * Instala los mocks de Mercado y superpone el escenario. Debe llamarse ANTES de
 * navegar. Las rutas específicas se registran después del catch-all, así que
 * Playwright las evalúa primero.
 */
export async function installS5Scenario(
  page: Page,
  scenario: S5Scenario,
): Promise<void> {
  await installMercadoApiMocks(page);

  await page.route("**/api/instrument-daily-opinions/query", (route) =>
    fulfillJson(route, opinionBody(scenario)),
  );
  await page.route("**/api/portfolio", async (route) => {
    if (!scenario.portfolioMeasured) {
      await fulfillJson(route, { detail: "portfolio unavailable (S5)" }, 500);
      return;
    }
    await fulfillJson(route, portfolioBody(scenario));
  });
  await page.route("**/api/risk/kill-switch", (route) =>
    fulfillJson(route, killSwitchBody(scenario)),
  );
  await page.route("**/api/accounts/*/decision-studies*", (route) =>
    fulfillJson(route, decisionStudiesBody()),
  );
  await page.route("**/api/lists", (route) =>
    fulfillJson(route, { data: [estudioList] }),
  );
  await page.route("**/api/lists/estudio", (route) =>
    fulfillJson(route, { data: estudioList }),
  );
  await page.route("**/api/lists/memberships", (route) =>
    fulfillJson(route, { data: { estudio: [E2E_INSTRUMENT_ID] } }),
  );
  await page.route("**/api/instruments/*/ohlcv*", (route) => {
    const bars = s5DailyBars();
    return fulfillJson(route, {
      data: bars,
      meta: { timeframe: "1d", count: bars.length },
    });
  });
}

/**
 * Siembra el workspace + layout y abre DECISIÓN maximizada. Devuelve el panel.
 */
export async function openS5MaximizedDecision(page: Page): Promise<void> {
  await seedMercadoBrowserState(page, { operativaMaximized: true });
  await page.goto("/trading");
  await expectCockpit(page);
  await page
    .getByTestId("operativa-recomendacion-principal")
    .waitFor({ state: "visible", timeout: 25_000 });
}

async function expectCockpit(page: Page) {
  await page
    .getByTestId("operativa-cockpit")
    .waitFor({ state: "visible", timeout: 25_000 });
}

/** Raíz del repositorio: Playwright corre con cwd = apps/web. */
function repoRoot(): string {
  const cwd = process.cwd();
  return /apps[\\/]web$/.test(cwd) ? resolve(cwd, "../..") : cwd;
}

export const S5_EVIDENCE_DIR = resolve(
  repoRoot(),
  "docs/engineering/evidence/s5-rediseno-2026-11-12",
);

/** Captura de pantalla en el expediente S5 (no es un baseline de `toHaveScreenshot`). */
export async function saveS5Screenshot(
  page: Page,
  name: string,
): Promise<string> {
  mkdirSync(S5_EVIDENCE_DIR, { recursive: true });
  const file = resolve(S5_EVIDENCE_DIR, name);
  await page.screenshot({ path: file, fullPage: false });
  return file;
}
