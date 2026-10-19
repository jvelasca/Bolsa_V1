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
  buildLifecycleSnapshotFromEvents,
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
  emitE2eMockLifecycleEvent,
  getE2eMockRuntime,
  getMercadoMockWorkspaceDocument,
} from "./e2e-mock-runtime";
import type { LifecycleStoreEventKind } from "./lifecycle-events";

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

/**
 * V1.85 — map lifecycle POST error codes to HTTP status (fail-closed).
 * Other routes keep default 200 with `{ error }` body for compatibility.
 */
export function statusForRouteBody(
  path: string,
  method: string,
  body: Record<string, unknown>,
): number {
  if (path === "/api/e2e/lifecycle/events" && method === "POST") {
    const err = body.error as { code?: string } | undefined;
    if (!err?.code) return 200;
    if (
      err.code === "invalid_json" ||
      err.code === "invalid_kind" ||
      err.code === "invalid_timestamp"
    ) {
      return 400;
    }
    return 409;
  }
  return 200;
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
  /**
   * Confirm LIVE VIRTUAL smoke — venue=live (simulado) + cola F3 mínima.
   * ≠ flip capital / ≠ Accept LIVE / ≠ PAPER_D_EXECUTE.
   */
  liveVenue?: boolean;
  /**
   * V2.88.56 — espacio AUTO (`/auto/*`): monitor operativo + artefactos DÍA-D de
   * feedback, para certificar la navegación `Operación → detalle técnico/DÍA-D`.
   */
  auto?: boolean;
  /**
   * E5 — recorrido completo de la operativa diaria: parte con valores, job manual y
   * un artefacto DÍA-D disponible para lanzar/observar el replay desde la UI.
   */
  autoDaily?: boolean;
  /**
   * S5/H6 — `presetKey` que DECLARA el ciclo AUTO del mock. Por defecto
   * `E2E_AUTO_PRESET_KEY` (casa con el `strategyType` del TOP ⇒ CTA habilitado). Un valor que
   * NO esté en el TOP ejercita el fail-closed de H6 (CTA deshabilitado + hueco declarado).
   */
  autoCyclePresetKey?: string | null;
};

/** Ciclo AUTO mínimo y determinista para el mock de navegación UI 2.1. */
const E2E_AUTO_CYCLE_A = "e2e-cycle-aaa";
const E2E_AUTO_CYCLE_B = "e2e-cycle-bbb";
const E2E_AUTO_SYMBOL = "AAA";
const E2E_AUTO_WINDOW = "2026-09-29_2026-09-30";
/** S5 — UUID determinista del valor para el puente AUTO → estrategia (UI-only, mock). */
const E2E_AUTO_INSTRUMENT_ID = "inst-e2e-aaa";
const E2E_AUTO_STRATEGY_ID = "def-e2e-1";
/**
 * S5 — `presetKey` que DECLARA el ciclo AUTO del mock: la identidad EXACTA (`H6`) que el CTA
 * «Verificar D→hoy» resuelve contra el TOP del valor (`strategyType` del slot #1). Casa con
 * `autoStrategyTopMock()` ⇒ camino habilitado (`data-verify-target="executed"`). Un valor que no
 * esté en el TOP ejercita el fail-closed (CTA deshabilitado + hueco declarado).
 */
const E2E_AUTO_PRESET_KEY = "sma_crossover";

function autoMonitorCycle(
  cycleId: string,
  instrumentId: string,
  closed: boolean,
  strategyPresetKey: string | null,
) {
  return {
    cycleId,
    instrumentId,
    strategyVersion: "sv-e2e",
    // H6 — identidad EXACTA declarada por el ciclo (`presetKey`): es la base de la resolución de
    // la estrategia EJECUTADA. `null` = el ciclo no la declara (hueco honesto, CTA inhabilitado).
    strategyPresetKey,
    direction: "long",
    closed,
    closedMeasurement: "COMPLETE",
    steps: [
      {
        id: "SIGNAL",
        state: "reached",
        at: "2026-09-29T20:00:00Z",
        measurement: "COMPLETE",
        facts: [{ key: "rank", value: 1, measurement: "COMPLETE" }],
        note: null,
      },
      {
        id: "TOP_N",
        state: "reached",
        at: "2026-09-29T20:00:01Z",
        measurement: "COMPLETE",
        facts: [],
        note: null,
      },
      {
        id: "FILL",
        state: "reached",
        at: "2026-09-30T09:00:00Z",
        measurement: "COMPLETE",
        facts: [],
        note: null,
      },
    ],
    result: { pnl: 250, closedAt: "2026-09-30T15:00:00Z" },
    notes: [],
  };
}

/** S5 — catálogo resoluble por símbolo (`AAA` → UUID) para el puente operación → estrategia. */
function autoStrategyInstrumentCatalog() {
  return {
    data: [
      { id: E2E_AUTO_INSTRUMENT_ID, symbol: E2E_AUTO_SYMBOL, name: "AAA E2E" },
    ],
  };
}

/** S5 — TOP de Finalistas del valor: #1 con definición + razones del coach (sin recalcular). */
function autoStrategyTopMock() {
  return {
    data: {
      id: "top-e2e-aaa",
      instrumentId: E2E_AUTO_INSTRUMENT_ID,
      symbol: E2E_AUTO_SYMBOL,
      timeframe: "1d",
      status: "active",
      version: 1,
      evidenceLevel: "lab_validated",
      slots: [
        {
          rank: 1,
          label: "SMA cross",
          stars: 3,
          score: 70,
          source: "coach",
          strategyDefinitionId: E2E_AUTO_STRATEGY_ID,
          strategyType: "sma_crossover",
        },
      ],
      coachFacts: {
        recommendations: [{ rank: 1, reasons: ["Estrellas 3/5", "DD -12%"] }],
      },
      createdAt: "2026-10-01T00:00:00Z",
      updatedAt: "2026-10-01T00:00:00Z",
    },
  };
}

/** S5 — definición de la estrategia #1 (fuente de los indicadores que la sustentan). */
function autoStrategyDefinitionMock() {
  return {
    data: {
      definition: {
        indicatorSpecs: [{ definitionId: "rsi", parameters: { period: 14 } }],
        presetKey: "sma_crossover",
      },
    },
  };
}

function autoOperationalMonitorMock(cyclePresetKey: string | null) {
  return {
    key: "auto_operational_monitor_v1",
    readOnly: true,
    accountId: E2E_ACCOUNT_ID,
    asOf: "2026-10-01T00:00:00Z",
    header: {
      engineId: "auto-e2e",
      state: "RUNNING",
      venue: "paper",
      granularity: { decision: "1d", execution: "signal_bar" },
      decisionClock: "CLOSED BAR",
      executionDeclared: "next_bar_open",
      executionEnabled: false,
      protectionModel: "bar_ohlc",
      heartbeatSeconds: 60,
      graceSeconds: 61,
      lastHeartbeatAt: "2026-10-01T09:00:00Z",
      lastHeartbeatMeasurement: "COMPLETE",
      lastDecisionAt: "2026-09-30T23:00:00Z",
      lastDecisionMeasurement: "COMPLETE",
      nextDecisionAt: "2026-10-01T00:01:00Z",
      currentActivity: null,
      currentActivityMeasurement: "UNKNOWN",
      realPriceEnabled: false,
      heartbeatsPersisted: 42,
      asOf: "2026-10-01T00:00:00Z",
    },
    cycles: [
      autoMonitorCycle(E2E_AUTO_CYCLE_A, E2E_AUTO_SYMBOL, true, cyclePresetKey),
      // El ciclo B NO declara `presetKey`: es el hueco honesto del contrato H6 (no se rellena).
      autoMonitorCycle(E2E_AUTO_CYCLE_B, "BBB", false, null),
    ],
    reservations: [],
    concurrency: {
      activeSessions: 0,
      activeSessionsMeasurement: "COMPLETE",
      heartbeatsPersisted: 42,
      claimAttempts: 0,
      claimAttemptsMeasurement: "COMPLETE",
      successfulClaims: 0,
      successfulClaimsMeasurement: "COMPLETE",
      lostClaims: 0,
      lostClaimsMeasurement: "COMPLETE",
      raceConflicts: 0,
      raceConflictsMeasurement: "COMPLETE",
      reconciliations: 0,
      reconciliationsMeasurement: "COMPLETE",
      graceWindowKeeps: 0,
      graceWindowKeepsMeasurement: "COMPLETE",
      forcedReleases: 0,
      forcedReleasesMeasurement: "COMPLETE",
      lastConflict: null,
      lastConflictMeasurement: "COMPLETE",
    },
    notes: [],
  };
}

/**
 * AUTO · Operativa diaria por valor — parte durable de un día (mock E2E).
 *
 * Cuatro estados con un valor completo (`ok` + plan `TRIGGERED`), uno sin plan
 * (`whyNot`) y los huecos explícitos: ningún `0` de relleno.
 */
function autoEstudioDailyMock(asOf: string) {
  return {
    asOf,
    accountId: E2E_ACCOUNT_ID,
    job: null,
    latestJob: null,
    report: {
      asOf,
      accountId: E2E_ACCOUNT_ID,
      status: "ok",
      scannedCount: 2,
      counts: { ok: 1, no_signal: 0, no_plan: 1, error: 0 },
      values: [
        {
          instrumentId: E2E_INSTRUMENT_ID,
          symbol: E2E_SYMBOL,
          status: "ok",
          reason: null,
          asOfBarDate: asOf,
          computedAt: `${asOf}T20:00:00+00:00`,
          opinion: {
            stance: "buy",
            dictamenStars: 4,
            channel: "alarma",
            autoSource: "estudio",
            reasons: ["momentum", "tendencia"],
            gateStatus: "PASS",
            engineVersion: "opinion_e2e",
          },
          indicators: {
            io: 72,
            fa: 55,
            ta: 61,
            confidence: "HIGH",
            regime: "neutral",
          },
          plan: {
            status: "TRIGGERED",
            direction: "long",
            entry: 192.4,
            structuralStop: 191.4,
            target1: 194,
            target2: null,
            riskAmount: 25,
            expectedRR: 2,
            whyNot: [],
          },
          whyNot: [],
          strategy: {
            presetKey: E2E_AUTO_PRESET_KEY,
            strategyDefinitionId: null,
            strategyVersion: 1,
            planId: "plan-e2e-1",
          },
        },
        {
          instrumentId: "e2e-estudio-gap",
          symbol: "GAP",
          status: "no_plan",
          reason: "no_tradeplan",
          asOfBarDate: asOf,
          computedAt: `${asOf}T20:00:00+00:00`,
          opinion: {
            stance: "hold_watch",
            dictamenStars: 2,
            channel: "none",
            autoSource: "estudio",
            reasons: [],
            gateStatus: "PASS",
            engineVersion: "opinion_e2e",
          },
          indicators: {
            io: 51,
            fa: null,
            ta: null,
            confidence: null,
            regime: null,
          },
          plan: null,
          whyNot: ["gap_risk", "liquidity"],
          strategy: null,
        },
      ],
      notes: [],
      generatedAt: `${asOf}T20:00:01+00:00`,
      truncated: false,
      countsConsistent: true,
    },
    notes: [],
  };
}

/** Auditoría por valor (ventana con artefacto) — valida el valor `E2E_SYMBOL`. */
function autoEstudioAuditMock() {
  return {
    available: true,
    readOnly: true,
    serving: "PRECOMPUTED_ARTIFACT",
    window: "D0_D1",
    audit: {
      kind: "estudio_audit_v1",
      readOnly: true,
      pointCitable: false,
      pointCitableReason: "paper_window_not_closed",
      summary: {
        values: 1,
        measured: 1,
        unmeasured: 0,
        withPresetKey: 1,
        withoutPresetKey: 0,
      },
      values: [
        {
          symbol: E2E_SYMBOL,
          strategy: { presetKey: E2E_AUTO_PRESET_KEY, version: "1" },
          why: { indicatorSpecs: null, recommendations: null },
          signal: {
            cycles: 1,
            linkedCycles: 1,
            unlinkedCycles: 0,
            duplicateCycles: 0,
            measuredCycles: 1,
            daysCovered: 1,
          },
          cycles: [
            {
              cycleId: E2E_AUTO_CYCLE_A,
              entryDay: "2026-09-29",
              exitDay: "2026-09-30",
              strategyPresetKey: E2E_AUTO_PRESET_KEY,
              strategyVersion: "1",
              realizedR: 0.4,
            },
          ],
          resultR: {
            verdict: "MIXED",
            verdictReason: null,
            evidenceQuality: "INSUFFICIENT_SAMPLE",
            expectancyR: 0.4,
            hitRate: 0.6,
            realizedRTotal: 0.4,
            measuredCycles: 8,
            daysCovered: 4,
            measured: true,
            sampleFloor: 10,
          },
          money: {
            trades: 1,
            netReturnPct: 2.5,
            netReturnPctAtStress: null,
            maxDrawdownPct: 3,
            hitRate: 0.6,
            committedCapital: null,
            measured: true,
            sampleFloor: 10,
          },
          measured: true,
          unmeasured: [],
        },
      ],
      notes: [],
    },
    notes: [],
  };
}

/**
 * Cadena durable por valor (`GET /api/auto/estudio-chain`) — el valor del parte tiene un ciclo
 * completo; el segundo valor del parte declara su hueco (`no_cycles_for_value`), no un cero.
 */
function autoEstudioChainMock(asOf: string) {
  return {
    available: true,
    readOnly: true,
    accountId: E2E_ACCOUNT_ID,
    asOf,
    engineId: "auto-sim-e2e",
    estudio: { status: "ok", values: 2 },
    summary: {
      values: 2,
      measured: 1,
      complete: 1,
      cycles: 1,
      cyclesComplete: 1,
      bestScoredPresent: true,
    },
    bestScored: {
      asOf,
      rows: [
        { rank: 1, assetId: E2E_INSTRUMENT_ID, combined: 72.5 },
        { rank: 2, assetId: "e2e-estudio-gap", combined: 51 },
      ],
    },
    values: [
      {
        instrumentId: E2E_INSTRUMENT_ID,
        measured: true,
        complete: true,
        unmeasured: [],
        strategy: {
          presetKey: E2E_AUTO_PRESET_KEY,
          version: "1",
          presetKeyAmbiguous: false,
          versionAmbiguous: false,
        },
        strategyDiaD: {
          presetKey: E2E_AUTO_PRESET_KEY,
          version: "1",
          presetKeyAmbiguous: false,
          versionAmbiguous: false,
        },
        cycles: [
          {
            cycleId: E2E_AUTO_CYCLE_A,
            instrumentId: E2E_INSTRUMENT_ID,
            direction: "long",
            closed: true,
            opportunityId: "e2e-opportunity-1",
            entryDay: "2026-09-29",
            exitDay: "2026-09-30",
            executed: {
              strategyPresetKey: E2E_AUTO_PRESET_KEY,
              strategyVersion: "1",
              rank: 1,
              score: 72.5,
              measurement: "COMPLETE",
            },
            bestScored: { rank: 1, assetId: E2E_INSTRUMENT_ID },
            executedVsBest: {
              executedIsTopRanked: true,
              executedIsBestScoredAsset: true,
              executedRank: 1,
              bestScoredAssetId: E2E_INSTRUMENT_ID,
              bestScoredPresetKey: null,
              presetMatch: null,
              measurement: "COMPLETE",
            },
            steps: {
              SIGNAL: 1,
              TOP_N: 1,
              RISK: 1,
              RESERVATION: 1,
              ORDER: 1,
              FILL: 1,
              PROTECTION: 1,
              SETTLEMENT: 1,
              CYCLE_CLOSED: 1,
            },
            chain: {
              reached: [
                "SIGNAL",
                "TOP_N",
                "RISK",
                "RESERVATION",
                "ORDER",
                "FILL",
                "PROTECTION",
                "SETTLEMENT",
                "CYCLE_CLOSED",
              ],
              notReached: {},
              complete: true,
              steps: 9,
            },
            pnl: {
              cycleClosedPnl: "12.40",
              settlementPnl: "12.40",
              reconciled: true,
              measurement: "COMPLETE",
            },
            diaD: { verdict: "PARTIAL" },
            executedVsDiaD: {
              matches: true,
              cyclePresetKey: E2E_AUTO_PRESET_KEY,
              diaDPresetKey: E2E_AUTO_PRESET_KEY,
              measurement: "COMPLETE",
            },
            diaDLink: { linkable: true, draft: null, measurement: "COMPLETE" },
            result: { realizedR: 0.4 },
            notes: [],
          },
        ],
      },
      {
        instrumentId: "e2e-estudio-gap",
        measured: false,
        complete: false,
        unmeasured: ["no_cycles_for_value"],
        strategy: {
          presetKey: null,
          version: null,
          presetKeyAmbiguous: false,
          versionAmbiguous: false,
        },
        strategyDiaD: {
          presetKey: null,
          version: null,
          presetKeyAmbiguous: false,
          versionAmbiguous: false,
        },
        cycles: [],
      },
    ],
    cyclesOutsideEstudio: [],
    meta: { schema: "auto-estudio-chain-v1", watch: [] },
    limits: ["Una verificación DÍA-D por valor a la vez por (cuenta, día)."],
    notes: [],
    error: null,
  };
}

/** DÍA-D propio del valor (`GET /api/auto/dia-d-replay/{day}/value/{symbol}`). */
function autoDiaDReplayValueMock(day: string, symbol: string) {
  const normalized = symbol.trim().toUpperCase();
  if (normalized !== E2E_SYMBOL) {
    return {
      available: false,
      readOnly: true,
      day,
      symbol: normalized,
      artifactModifiedAt: null,
      schemaVersion: null,
      summary: null,
      steps: [],
      oos: null,
      meta: {},
      limits: [],
      executedDetail: {},
      notes: ["artifact_not_found"],
    };
  }
  return {
    available: true,
    readOnly: true,
    day,
    symbol: normalized,
    artifactModifiedAt: `${day}T21:00:00+00:00`,
    schemaVersion: "dia-d-auto-v2",
    summary: {
      verdict: "PARTIAL",
      match: 1,
      divergent: 0,
      notMeasured: 0,
      steps: 1,
    },
    steps: [
      {
        step: "signal",
        declared: "buy",
        executed: "buy",
        verdict: "MATCH",
        measurement: "COMPLETE",
      },
    ],
    oos: null,
    meta: { account: E2E_ACCOUNT_ID, watch: [normalized] },
    limits: [],
    executedDetail: {},
    notes: [],
  };
}

/** Job operativo de la cola durable — encolado y progreso observables. */
function autoOpsJobMock(input: {
  id: string;
  kind: string;
  day: string;
  status: string;
  phase?: string;
  percent?: number;
  payload?: Record<string, unknown>;
}) {
  return {
    id: input.id,
    kind: input.kind,
    status: input.status,
    day: input.day,
    accountId: E2E_ACCOUNT_ID,
    payload: input.payload ?? {},
    progress:
      input.phase === undefined
        ? {}
        : {
            phase: input.phase,
            done: 1,
            total: 2,
            percent: input.percent ?? 50,
          },
    result: {},
    error: null,
    attempt: 1,
    createdAt: `${input.day}T20:00:00+00:00`,
    startedAt: `${input.day}T20:00:01+00:00`,
    finishedAt: null,
    heartbeatAt: `${input.day}T20:00:02+00:00`,
  };
}

/** Artefacto DÍA-D mínimo y determinista para el recorrido manual del mock. */
function autoDiaDReplayArtifactMock(day: string) {
  return {
    available: true,
    readOnly: true,
    day,
    summary: { verdict: "PARTIAL", match: 1, divergent: 0, notMeasured: 0 },
    steps: [
      {
        step: "signal",
        declared: "buy",
        executed: "buy",
        verdict: "MATCH",
        measurement: "COMPLETE",
      },
    ],
    oos: null,
    meta: {
      account: E2E_ACCOUNT_ID,
      versionA: "e2e",
      replayStart: day,
      replayEnd: day,
    },
    limits: [],
    notes: [],
  };
}

function autoDiaDFeedbackArtifact() {
  return {
    available: true,
    readOnly: true,
    matrixBasis: "entryDay",
    window: {
      from: "2026-09-29",
      to: "2026-09-30",
      days: ["2026-09-29", "2026-09-30"],
    },
    values: [
      {
        symbol: E2E_AUTO_SYMBOL,
        verdict: "OOS_SUPPORTED",
        verdictReason: "positive_expectancy",
        evidenceQuality: "PRELIMINARY",
        expectancyR: 0.5,
        hitRate: 0.67,
        measuredCycles: 6,
        daysCovered: 1,
        windowDays: 2,
        errorTotal: 0,
      },
      {
        symbol: "BBB",
        verdict: "MIXED",
        verdictReason: "mixed_evidence",
        evidenceQuality: "PRELIMINARY",
        expectancyR: -0.1,
        hitRate: 0.5,
        measuredCycles: 5,
        daysCovered: 1,
        windowDays: 2,
        errorTotal: 1,
      },
    ],
    matrix: [],
    errors: [],
    limits: [],
    gate: { verdict: "GREEN", days: 2, episodes: 2, cycles: 4 },
    summary: {
      measuredValues: 2,
      mixed: 1,
      notMeasured: 0,
      oosSupported: 1,
      refuted: 0,
      byEvidenceQuality: { PRELIMINARY: 2 },
      errors: { SOFTWARE: 0, OPERATIONAL: 0, DATA: 0 },
    },
  };
}

function autoDiaDFeedbackListMock() {
  return {
    readOnly: true,
    windows: [E2E_AUTO_WINDOW],
    latest: E2E_AUTO_WINDOW,
    artifact: autoDiaDFeedbackArtifact(),
    notes: [],
  };
}

/**
 * Informe fiscal (`GET /api/accounts/{id}/tax-report`) — shape mínimo del `TaxReportSummaryDto`.
 *
 * Sin esta rama, `routeBody` cae al default `{ data: [] }`: `TaxReportPage` hace
 * `report.realizedLines.length` sobre un ARRAY y revienta en el error boundary, así que el
 * barrido axe de `/fiscal` nunca llegaba a ver su jerarquía real.
 */
function taxReportMock(year = new Date().getFullYear()) {
  return {
    data: {
      accountId: E2E_ACCOUNT_ID,
      currency: "EUR",
      method: "fifo",
      jurisdiction: "ES",
      year,
      periodLabel: `Ejercicio ${year}`,
      realizedLines: [
        {
          id: "e2e-tax-line-1",
          instrumentId: E2E_INSTRUMENT_ID,
          symbol: E2E_SYMBOL,
          sellTransactionId: "e2e-tax-tx-1",
          executedAt: "2026-03-04T10:00:00.000Z",
          quantity: 10,
          sellPrice: 110,
          proceeds: 1100,
          costBasis: 1000,
          realizedGain: 100,
          method: "fifo",
          acquisitionDates: ["2026-01-15T10:00:00.000Z"],
        },
      ],
      totalGains: 100,
      totalLosses: 0,
      netRealizedGain: 100,
      estimatedTaxLiability: null,
      unrealizedLines: [
        {
          instrumentId: E2E_INSTRUMENT_ID,
          symbol: E2E_SYMBOL,
          quantity: 10,
          avgCost: 100,
          marketPrice: 102,
          costBasis: 1000,
          marketValue: 1020,
          unrealizedGain: 20,
        },
      ],
      totalUnrealizedGain: 20,
      feesPaidTotal: 5,
      dividendWithholdingPct: 19,
      openPositionCount: 1,
    },
  };
}

/** Cola mínima para hidratar SupervisedF3 en smoke LIVE VIRTUAL. */
function liveVirtualSupervisedF3Bundle() {
  const itemId = "e2e-live-virtual-f3-1";
  return {
    accountId: E2E_ACCOUNT_ID,
    activeId: itemId,
    updatedAt: "2026-09-07T12:00:00.000Z",
    items: [
      {
        id: itemId,
        enqueuedAt: "2026-09-07T12:00:00.000Z",
        symbol: E2E_SYMBOL,
        origin: "manual",
        payload: {
          artifactType: "ART-RECOMMENDATION",
          schemaVersion: "1.0.0",
          recommendationId: "REC-E2E-LIVE-VIRTUAL",
          decisionId: "DEC-E2E-LIVE-VIRTUAL",
          instrumentId: E2E_INSTRUMENT_ID,
          symbol: E2E_SYMBOL,
          action: "recommend_long",
          // TradePlan TRIGGERED = única autoridad de sizing en Confirm (V1.25).
          // Sin él, evaluateRiskSignature ⇒ no_tradeplan ⇒ CTA deshabilitado. Con
          // geometría long válida (stop < entry < t1 < t2) y qty == plan.quantity,
          // el riesgo firma `allowed` sin override → CTA ejecutable en el sandbox.
          tradePlan: {
            decisionId: "DEC-E2E-LIVE-VIRTUAL",
            instrumentId: E2E_INSTRUMENT_ID,
            direction: "long",
            status: "TRIGGERED",
            entry: 192.4,
            structuralStop: 191.4,
            target1: 194,
            target2: 195.5,
            quantity: 10,
            riskPct: 1,
            riskAmount: 25,
            initialRiskR: 1,
            whyNot: [],
            executionAllowed: true,
          },
          suggestedQuantity: 10,
          suggestedPrice: 192.4,
          metrics: {
            confidence: 0.5,
            consensus: 0.5,
            evidenceStrength: 0.5,
            stability: 0.5,
            conviction: 0.5,
          },
          status: "awaiting_human",
          createdAt: "2026-09-07T12:00:00.000Z",
          source: "manual",
          lastClose: 192.4,
        },
      },
    ],
  };
}

export function routeBody(
  route: Route,
  opts?: E2eMockRouteOpts,
): Record<string, unknown> {
  const e2eMockRuntime = getE2eMockRuntime();
  const path = apiPath(route.request().url());
  const method = route.request().method().toUpperCase();
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

  /** V1.84 — event log SoT when non-empty; else V1.83 stage projection. */
  const resolveLifecycleSnap = () => {
    if (!lifecycleDesk) return null;
    if (e2eMockRuntime.lifecycleEvents.length > 0) {
      return buildLifecycleSnapshotFromEvents(e2eMockRuntime.lifecycleEvents);
    }
    return buildLifecycleSnapshot({
      stage: e2eMockRuntime.positionStage,
      lineagePath: e2eMockRuntime.lineagePath,
    });
  };

  // V1.84/V1.85 — test-only mock: POST validate → append lifecycle events.
  if (path === "/api/e2e/lifecycle/events" && method === "POST") {
    if (!lifecycleDesk) {
      return {
        error: {
          code: "lifecycle_desk_required",
          message: "Emit requires deskMode lifecycle",
        },
      };
    }
    let body: Record<string, unknown> = {};
    try {
      const raw = route.request().postData();
      body = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
    } catch {
      return {
        error: { code: "invalid_json", message: "Expected JSON body" },
      };
    }
    const kind = body.kind as LifecycleStoreEventKind | undefined;
    const allowed: LifecycleStoreEventKind[] = [
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
      "POSITION_CLOSED",
    ];
    if (!kind || !allowed.includes(kind)) {
      return {
        error: {
          code: "invalid_kind",
          message: `kind must be one of ${allowed.join("|")}`,
        },
      };
    }
    const result = emitE2eMockLifecycleEvent({
      kind,
      at: typeof body.at === "string" ? body.at : undefined,
      eventId: typeof body.eventId === "string" ? body.eventId : undefined,
      positionId:
        typeof body.positionId === "string" ? body.positionId : undefined,
      fillId: typeof body.fillId === "string" ? body.fillId : undefined,
      quantity: typeof body.quantity === "number" ? body.quantity : undefined,
      price: typeof body.price === "number" ? body.price : undefined,
      fees: typeof body.fees === "number" ? body.fees : undefined,
      venue: typeof body.venue === "string" ? body.venue : undefined,
      venueOrderId:
        typeof body.venueOrderId === "string" ? body.venueOrderId : undefined,
      currency: typeof body.currency === "string" ? body.currency : undefined,
      previousStop:
        typeof body.previousStop === "number" ? body.previousStop : undefined,
      newStop: typeof body.newStop === "number" ? body.newStop : undefined,
      reason: typeof body.reason === "string" ? body.reason : undefined,
      revisionId:
        typeof body.revisionId === "string" ? body.revisionId : undefined,
    });
    if (!result.ok) {
      return { error: result.error };
    }
    return {
      data: {
        ok: true,
        event: result.event,
        idempotent: result.idempotent,
        stage: result.stage,
        lineagePath: result.lineagePath,
        count: result.count,
      },
    };
  }

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
  // V2.88.56 — espacio AUTO: monitor operativo + artefactos DÍA-D de feedback.
  if (opts?.auto === true) {
    if (path === "/api/auto/operational-monitor") {
      return autoOperationalMonitorMock(
        opts.autoCyclePresetKey === undefined
          ? E2E_AUTO_PRESET_KEY
          : opts.autoCyclePresetKey,
      );
    }
    if (path === "/api/auto/dia-d-feedback") {
      return autoDiaDFeedbackListMock();
    }
    if (path.startsWith("/api/auto/dia-d-feedback/")) {
      return autoDiaDFeedbackArtifact();
    }
    if (path === "/api/auto/dia-d-replay") {
      return {
        readOnly: true,
        days: opts.autoDaily === true ? ["2026-09-30"] : [],
        notes: [],
      };
    }
    // Evidencia durable por valor (cadena de 9 etapas) — una lectura por informe.
    if (path === "/api/auto/estudio-chain") {
      const asOf =
        new URL(route.request().url()).searchParams.get("asOf") ?? "2026-10-18";
      return autoEstudioChainMock(asOf);
    }
    // Artefacto DÍA-D PROPIO del valor: nunca se rellena desde el del día completo.
    const diaDValueMatch =
      /^\/api\/auto\/dia-d-replay\/([^/]+)\/value\/([^/]+)$/.exec(path);
    if (diaDValueMatch) {
      return autoDiaDReplayValueMock(
        diaDValueMatch[1] as string,
        decodeURIComponent(diaDValueMatch[2] as string),
      );
    }
    if (path.startsWith("/api/auto/dia-d-replay/")) {
      if (opts.autoDaily === true) {
        return autoDiaDReplayArtifactMock(
          path.split("/").pop() ?? "2026-09-30",
        );
      }
      return { available: false, notes: ["artifact_not_found"] };
    }
    // E4/E5 — operativa diaria por valor + cola durable de jobs (mismo contrato que la API).
    if (path === "/api/auto/estudio-daily") {
      const asOf =
        new URL(route.request().url()).searchParams.get("asOf") ?? "2026-10-18";
      return autoEstudioDailyMock(asOf);
    }
    if (path === "/api/auto/estudio-audit") {
      return autoEstudioAuditMock();
    }
    if (path === "/api/auto/ops-jobs") {
      let body: Record<string, unknown> = {};
      try {
        const raw = route.request().postData();
        body = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      } catch {
        body = {};
      }
      const kind = typeof body.kind === "string" ? body.kind : "estudio_daily";
      const day =
        typeof body.day === "string" && body.day ? body.day : "2026-10-18";
      const payload =
        body.payload && typeof body.payload === "object"
          ? (body.payload as Record<string, unknown>)
          : {};
      return autoOpsJobMock({
        id:
          kind === "dia_d_replay"
            ? "e2e-dia-d-job"
            : kind === "dia_d_value_replay"
              ? "e2e-dia-d-value-job"
              : "e2e-estudio-daily-job",
        kind,
        day,
        status: "running",
        phase:
          kind === "dia_d_replay" || kind === "dia_d_value_replay"
            ? "replay"
            : "opinions",
        percent: 40,
        payload,
      });
    }
    if (path.startsWith("/api/auto/ops-jobs/")) {
      const id = path.split("/").pop() ?? "e2e-job";
      return autoOpsJobMock({
        id,
        kind: id.includes("dia-d") ? "dia_d_replay" : "estudio_daily",
        day: "2026-10-18",
        status: "completed",
      });
    }
    // S5 — puente operación → estrategia/indicadores → verificación DÍA-D (UI-only).
    if (path === "/api/instruments") {
      return autoStrategyInstrumentCatalog();
    }
    if (path.endsWith("/strategy-top")) {
      return autoStrategyTopMock();
    }
    if (path.startsWith("/api/strategies/")) {
      return autoStrategyDefinitionMock();
    }
  }
  if (path === "/api/portfolio") {
    const lifecycleSnap = resolveLifecycleSnap();
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
      const snap = resolveLifecycleSnap()!;
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
    const lifecycleSnap = resolveLifecycleSnap();
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
  if (path.endsWith("/tax-report")) {
    return taxReportMock();
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
    // Shape = BrokerVenueResponse (top-level); mock antiguo `{ venue }` era noop → paper.
    const venue = opts?.liveVenue ? "live" : "paper";
    return {
      brokerVenue: venue,
      env: venue,
      runtimeMemory: null,
      redis: null,
    };
  }
  if (path.match(/^\/api\/accounts\/[^/]+\/broker-venue$/)) {
    const venue = opts?.liveVenue ? "live" : "paper";
    const accountId = path.split("/")[3] ?? E2E_ACCOUNT_ID;
    return {
      accountId,
      preference: opts?.liveVenue ? venue : null,
      effective: venue,
    };
  }
  if (path.match(/^\/api\/accounts\/[^/]+\/supervised-f3-queue$/)) {
    if (opts?.liveVenue) {
      return { data: liveVirtualSupervisedF3Bundle() };
    }
    return {
      data: {
        accountId: path.split("/")[3] ?? E2E_ACCOUNT_ID,
        items: [],
        activeId: null,
        updatedAt: null,
      },
    };
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
  if (path === "/api/ai/intents/confirm" && opts?.liveVenue) {
    // VIRTUAL sandbox: Confirm firma OK · money path bloqueado (≠ POST bridge).
    return {
      data: {
        intent: {
          status: "authorized",
          contract: "ok",
        },
        trade: {
          status: "skipped",
          reason: "live_virtual_sandbox",
        },
        brokerAdapter: {
          venue: "LIVE",
          adapter: "xtb",
          fillStatus: "not_wired",
        },
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
      // `InstrumentDetailResponseDto` exige `meta` (`priceSummary`/`lastSync`): sin él la
      // ficha `/instruments/:id` revienta en el error boundary ("Cannot read properties of
      // undefined (reading 'priceSummary')") y el barrido axe nunca ve su jerarquía real.
      meta: {
        lastSync: {
          lastSyncAt: "2026-08-30T00:00:00.000Z",
          status: "success",
          barCount: 30,
        },
        priceSummary: {
          lastClose: 102,
          changePct: 2,
          barCount: 30,
          lastBarDate: "2026-08-30",
        },
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

  // `FundamentalCardDto` es un OBJETO con `facts`/`derived`/`metadata` REQUERIDOS: el fallback
  // genérico `[]` (una lista) hace que el panel FA reviente en el error boundary
  // ("Cannot read properties of undefined (reading 'forwardPe')") y tumba toda la página, lo que
  // a su vez impide montar el verificador DÍA-D. Aquí se declara la AUSENCIA de snapshot como
  // `null` (estado «Sin datos FA»), que es lo que el cliente ya tipa (`data: FundamentalCardDto
  // | null`), nunca como lista.
  if (/\/api\/instruments\/[^/]+\/fundamentals$/.test(path)) {
    return { data: null };
  }

  return { data: [] };
}
