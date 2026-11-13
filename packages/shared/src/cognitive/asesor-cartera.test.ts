/**
 * S3 · Cartera del Asesor — regresiones del modelo puro.
 *
 * Lo que estos tests protegen (y debe morder de verdad):
 *   - la lista NO recomienda: contexto alcista completo + `hold_watch` sigue en
 *     «Sin oportunidad»; `buy` con contexto flojo sigue «Recomendación favorable»;
 *   - cartera no medida NUNCA se pinta como «sin posición»;
 *   - `overbought` con posición es «Posición sin respaldo», no sobrecompra;
 *   - solo los niveles `detectado` producen S/R; los huecos se declaran;
 *   - el termómetro respeta su precedencia y no se inventa una entrada;
 *   - ninguna etiqueta visible filtra una clave `snake_case`.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import type { InstrumentDailyOpinionV1 } from "../instrument-daily-opinion.js";
import {
  MARKET_STRUCTURE_DEFAULTS,
  MARKET_STRUCTURE_METHOD_ID,
  MARKET_STRUCTURE_METHOD_VERSION,
  type MarketLevelV1,
  type MarketStructureResultV1,
} from "../market-structure.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { OperationalPlanViewV1 } from "./operational-plan-view.js";
import {
  ASESOR_CARTERA_STATE_IDS,
  DEFAULT_ASESOR_CARTERA_FILTER,
  asesorCarteraStateDefinition,
  asesorCarteraStateLabel,
  buildAsesorCarteraRow,
  classifyAsesorCarteraState,
  filterAsesorCarteraRows,
  sortAsesorCarteraRows,
  summarizeAsesorCartera,
  type AsesorCarteraRowV1,
  type BuildAsesorCarteraRowInput,
} from "./asesor-cartera.js";

const INTERNAL_KEY = /[a-z]+_[a-z]+/;

// ── Fixtures ────────────────────────────────────────────────────────────────

function opinion(
  stance: InstrumentDailyOpinionV1["stance"],
  overrides: Partial<InstrumentDailyOpinionV1> = {},
): InstrumentDailyOpinionV1 {
  return {
    id: "op-1",
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance,
    dictamenStars: 4,
    ioScore: 72,
    distress: false,
    reasons: [],
    source: "eod_batch",
    engineVersion: "opinion_v1",
    idempotencyKey: "k",
    computedAt: "2026-11-12T18:00:00.000Z",
    createdAt: "2026-11-12T18:00:00.000Z",
    updatedAt: "2026-11-12T18:00:00.000Z",
    ...overrides,
  };
}

function position(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "pos-1",
    instrumentId: "inst-1",
    symbol: "AAA",
    name: "AAA SA",
    quantity: 100,
    avgCost: 10,
    lastPrice: 10.5,
    marketValue: 1050,
    unrealizedPnl: 50,
    unrealizedPnlPct: 5,
    ...overrides,
  };
}

function study(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "s-1",
    decisionId: "d-1",
    instrumentId: "inst-1",
    symbol: "AAA",
    name: "AAA SA",
    studiedAt: "2026-11-12T18:00:00.000Z",
    ageMs: 3_600_000,
    period: "daily",
    timeframe: "1d",
    opinion: "bullish",
    status: "neutral",
    strength: 7.5,
    strengthBand: "strong",
    vigencia: "current",
    entry: null,
    stop: null,
    target1: null,
    target2: null,
    expectedRR: null,
    riskAmount: null,
    quantity: null,
    initialRiskR: null,
    positionValue: null,
    direction: "long",
    hasOperationalPlan: false,
    userThesis: null,
    decisionSummary: null,
    analysisNotes: [],
    trends: [
      {
        key: "short_term",
        label: "Corto plazo",
        value: "bullish",
        display: "Alcista",
      },
    ],
    consensus: { bullish: 0, bearish: 0, neutral: 0, total: 0 },
    indicators: { primary: "ADX 28", confirmation: "SMA 20/50" },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: null,
    action: null,
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

function level(
  kind: MarketLevelV1["kind"],
  price: number,
  state: MarketLevelV1["state"],
  touches = 3,
): MarketLevelV1 {
  return {
    kind,
    price,
    zoneLow: price - 0.05,
    zoneHigh: price + 0.05,
    touches,
    state,
    reasons: state === "detectado" ? [] : ["nivel_roto"],
    pivots: [
      {
        index: 10,
        timestamp: "2026-10-01T00:00:00.000Z",
        price,
        type: kind === "support" ? "low" : "high",
      },
    ],
    lastTouchAt: "2026-11-01T00:00:00.000Z",
    distancePct: 1,
    distanceAtr: 0.5,
  };
}

function structure(
  overrides: Partial<MarketStructureResultV1> = {},
): MarketStructureResultV1 {
  return {
    methodId: MARKET_STRUCTURE_METHOD_ID,
    methodVersion: MARKET_STRUCTURE_METHOD_VERSION,
    params: { ...MARKET_STRUCTURE_DEFAULTS },
    window: {
      from: "2026-01-01T00:00:00.000Z",
      to: "2026-11-12T00:00:00.000Z",
      bars: 220,
      timeframe: "1d",
    },
    inputSignature: "deadbeef",
    status: "ok",
    reasons: [],
    atrRef: 0.4,
    close: 10.5,
    supports: [],
    resistances: [],
    structure: { id: "ascendente", tolerance: 0.2, highs: [], lows: [] },
    lastBarMayBeOpen: true,
    ...overrides,
  };
}

function plan(
  overrides: Partial<OperationalPlanViewV1> = {},
): OperationalPlanViewV1 {
  return {
    phase: "none",
    phaseLabel: "Sin plan",
    direction: "long",
    entry: null,
    stopVigente: null,
    stopInicial: null,
    target1: null,
    target2: null,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: null,
    riskR: null,
    currentPrice: null,
    unrealizedR: null,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: false,
    emptyCopy: "No existe todavía un plan operativo.",
    ...overrides,
  };
}

function rowInput(
  overrides: Partial<BuildAsesorCarteraRowInput> = {},
): BuildAsesorCarteraRowInput {
  return {
    instrumentId: "inst-1",
    symbol: "AAA",
    name: "AAA SA",
    quote: { price: 10.5, changePct: 1.2 },
    opinion: opinion("hold_watch"),
    study: study(),
    structure: structure(),
    phase: "vigilar",
    plan: plan(),
    position: null,
    portfolioMeasured: true,
    markPrice: 10.5,
    ...overrides,
  };
}

// ── 1 · Clasificador ────────────────────────────────────────────────────────

describe("classifyAsesorCarteraState · cinco estados y precedencia", () => {
  const measured = { measured: true, hasOpenPosition: false };
  const open = { measured: true, hasOpenPosition: true };
  const unmeasured = { measured: false, hasOpenPosition: false };

  it("cartera no medida gana a cualquier dictamen y no escribe «sin posición»", () => {
    const state = classifyAsesorCarteraState({
      opinion: opinion("buy"),
      position: unmeasured,
    });
    expect(state.id).toBe("sin_datos");
    expect(state.gaps).toContain("Cartera sin medir");
    expect(state.label).not.toContain("Sin posición");
  });

  it("sin dictamen declara el hueco", () => {
    const state = classifyAsesorCarteraState({
      opinion: null,
      position: measured,
    });
    expect(state.id).toBe("sin_datos");
    expect(state.gaps).toContain("Sin dictamen");
  });

  it("position_unmeasured en no_trade no se colapsa a «sin oportunidad»", () => {
    const state = classifyAsesorCarteraState({
      opinion: opinion("no_trade", {
        reasons: ["position_unmeasured", "io_medium"],
        ioScore: null,
      }),
      position: measured,
    });
    expect(state.id).toBe("sin_datos");
    expect(state.gaps).toContain("Cartera sin medir");
  });

  it("io_unmeasured y eod_data_stale también son huecos", () => {
    expect(
      classifyAsesorCarteraState({
        opinion: opinion("no_trade", { reasons: ["io_unmeasured"] }),
        position: measured,
      }).gaps,
    ).toContain("Calidad de señal sin medir");
    expect(
      classifyAsesorCarteraState({
        opinion: opinion("no_trade", { reasons: ["eod_data_stale"] }),
        position: measured,
      }).gaps,
    ).toContain("Sin cierre de sesión");
  });

  it("overbought con posición es «Posición sin respaldo», no sobrecompra", () => {
    const state = classifyAsesorCarteraState({
      opinion: opinion("overbought", { reasons: ["top_low"] }),
      position: open,
    });
    expect(state.id).toBe("posicion_sin_respaldo");
    expect(state.label).toBe("Posición sin respaldo");
    expect(JSON.stringify(state).toLowerCase()).not.toContain("sobrecompr");
  });

  it("review_strategy con posición es «Posición sin respaldo»", () => {
    const state = classifyAsesorCarteraState({
      opinion: opinion("review_strategy", { reasons: ["stale_top"] }),
      position: open,
    });
    expect(state.id).toBe("posicion_sin_respaldo");
  });

  it("posiciones evaluadas (incluida buy) con posición son «Posición abierta»", () => {
    for (const stance of [
      "reduce",
      "sell_exit",
      "hold_watch",
      "buy",
    ] as const) {
      expect(
        classifyAsesorCarteraState({
          opinion: opinion(stance),
          position: open,
        }).id,
      ).toBe("posicion_abierta");
    }
  });

  it("el texto de «Posición abierta» no niega las posturas que clasifica", () => {
    const definition = asesorCarteraStateDefinition("posicion_abierta");
    expect(definition.meaning).toBe(
      "Hay posición abierta; la recomendación del dictamen conserva su propio nombre.",
    );
    expect(definition.meaning.toLowerCase()).not.toContain("no pide salir");
  });

  it("buy sin posición es «Recomendación favorable»", () => {
    expect(
      classifyAsesorCarteraState({
        opinion: opinion("buy"),
        position: measured,
      }).id,
    ).toBe("recomendacion_favorable");
  });

  it("hold_watch/no_trade/review_strategy sin posición son «Sin oportunidad»", () => {
    for (const stance of ["hold_watch", "no_trade", "review_strategy"] as const) {
      expect(
        classifyAsesorCarteraState({
          opinion: opinion(stance),
          position: measured,
        }).id,
      ).toBe("evaluado_sin_oportunidad");
    }
  });

  it("una postura de salida sin posición medida se declara, no se inventa", () => {
    for (const stance of ["reduce", "sell_exit"] as const) {
      const state = classifyAsesorCarteraState({
        opinion: opinion(stance),
        position: measured,
      });
      expect(state.id).toBe("sin_datos");
      expect(state.gaps).toContain("Dictamen de salida sin posición medida");
    }
  });

  it("cada estado tiene etiqueta visible sin clave interna", () => {
    for (const id of ASESOR_CARTERA_STATE_IDS) {
      const label = asesorCarteraStateLabel(id);
      expect(label).not.toMatch(INTERNAL_KEY);
      expect(label.trim().length).toBeGreaterThan(0);
    }
  });
});

// ── 2 · La lista no recomienda ──────────────────────────────────────────────

describe("buildAsesorCarteraRow · no agregación de señales", () => {
  it("contexto alcista completo con hold_watch sigue «Sin oportunidad»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("hold_watch", { ioScore: 78 }),
        study: study({
          strength: 9,
          strengthBand: "very_strong",
          trends: [
            {
              key: "short_term",
              label: "Corto plazo",
              value: "strong_bullish",
              display: "Alcista fuerte",
            },
          ],
        }),
        structure: structure({
          supports: [level("support", 10.4, "detectado")],
          resistances: [level("resistance", 11.2, "detectado")],
        }),
        phase: "preparada",
        plan: plan({ hasPlan: true, entry: 10.6, stopVigente: 10.1 }),
        markPrice: 10.55,
      }),
    );
    expect(row.state.id).toBe("evaluado_sin_oportunidad");
    expect(row.recommendation.label).toBe("Mantener");
    // El contexto se muestra, pero no se convierte en recomendación.
    expect(row.trend.label).toBe("Alcista fuerte");
    expect(row.strength.measured).toBe(true);
    expect(row.levels.support).toBe(10.4);
  });

  it("buy con contexto flojo sigue «Recomendación favorable»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("buy", { ioScore: 82 }),
        study: study({
          strength: 1.2,
          strengthBand: "very_weak",
          trends: [
            {
              key: "short_term",
              label: "Corto plazo",
              value: "bearish",
              display: "Bajista",
            },
          ],
        }),
        structure: structure({
          supports: [level("support", 10.45, "no_fiable")],
          resistances: [],
        }),
      }),
    );
    expect(row.state.id).toBe("recomendacion_favorable");
    expect(row.levels.measured).toBe(false);
  });

  it("la recomendación es siempre la del dictamen y no se duplica", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ opinion: opinion("buy", { ioScore: 85 }) }),
    );
    expect(row.recommendation.stance).toBe("buy");
    expect(row.recommendation.label).toBe("Comprar");
    expect(row.recommendation.confidence).toBe(85);
    expect(row.recommendation.confidenceLabel).toBe("85 / 100");
  });
});

// ── 3 · Niveles ─────────────────────────────────────────────────────────────

describe("buildAsesorCarteraRow · soportes y resistencias", () => {
  it("solo los `detectado` producen nivel", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        structure: structure({
          supports: [
            level("support", 10.1, "roto"),
            level("support", 10.3, "detectado"),
            level("support", 10.45, "no_fiable"),
          ],
          resistances: [level("resistance", 10.8, "en_precio")],
        }),
      }),
    );
    expect(row.levels.support).toBe(10.3);
    expect(row.levels.resistance).toBeNull();
    expect(row.levels.supportLabel).toBe("S·calc 10,30");
    expect(row.levels.resistanceLabel).toBe("Sin nivel fiable");
  });

  it("histórico insuficiente se declara con las velas medidas", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        structure: structure({
          status: "insufficient_history",
          reasons: ["historico_insuficiente"],
          window: {
            from: "2026-10-01T00:00:00.000Z",
            to: "2026-11-12T00:00:00.000Z",
            bars: 79,
            timeframe: "1d",
          },
        }),
      }),
    );
    expect(row.levels.measured).toBe(false);
    expect(row.levels.detail).toContain("79 velas");
    expect(row.levels.detail).toContain("80");
    expect(row.gaps).toContain("Histórico insuficiente");
  });

  it("sin estructura no se pinta 0 como nivel", () => {
    const row = buildAsesorCarteraRow(rowInput({ structure: null }));
    expect(row.levels.support).toBeNull();
    expect(row.levels.resistance).toBeNull();
    expect(row.levels.detail).toBe("Sin medición de estructura");
  });
});

// ── 4 · Tendencia, fuerza y momento ────────────────────────────────────────

describe("buildAsesorCarteraRow · tendencia y fuerza", () => {
  it("sin parte diario declara el hueco en tendencia y fuerza", () => {
    const row = buildAsesorCarteraRow(rowInput({ study: null }));
    expect(row.trend.label).toBe("Sin dato de tendencia");
    expect(row.trend.tone).toBe("unknown");
    expect(row.strength.label).toBe("Sin dato de fuerza");
    expect(row.gaps).toContain("Sin parte diario");
  });

  it("la fuerza se copia del estudio, no se infiere de la tendencia", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ study: study({ strength: 6.4, strengthBand: "strong" }) }),
    );
    expect(row.strength.measured).toBe(true);
    expect(row.strength.label).toBe("Fuerza 6,4 / 10 · Fuerte");
  });

  it("parte caducado se declara sin cambiar la tendencia", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ study: study({ vigencia: "expired" }) }),
    );
    expect(row.trend.measured).toBe(true);
    expect(row.gaps).toContain("Parte diario caducado");
  });
});

describe("buildAsesorCarteraRow · momento", () => {
  it("sin entrada publicada el termómetro es «Sin entrada»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ plan: plan({ hasPlan: false, entry: null }) }),
    );
    expect(row.moment.thermometer?.state).toBe("sin_entrada");
    expect(row.moment.gaps).toContain("Sin entrada publicada");
  });

  it("precio por encima del Objetivo 1 es «Extendido»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        plan: plan({ hasPlan: true, entry: 10, stopVigente: 9.4, target1: 10.2 }),
        markPrice: 10.4,
      }),
    );
    expect(row.moment.thermometer?.state).toBe("extendido");
  });

  it("en la zona de activación es «Caliente»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        plan: plan({ hasPlan: true, entry: 10, stopVigente: 9.4, target1: 11 }),
        markPrice: 10.05,
      }),
    );
    expect(row.moment.thermometer?.state).toBe("caliente");
  });

  it("±3 % de la entrada es «Templado» y lejos es «Frío»", () => {
    const templado = buildAsesorCarteraRow(
      rowInput({
        plan: plan({ hasPlan: true, entry: 10, stopVigente: 9.4, target1: 11 }),
        markPrice: 9.8,
      }),
    );
    expect(templado.moment.thermometer?.state).toBe("templado");
    const frio = buildAsesorCarteraRow(
      rowInput({
        plan: plan({ hasPlan: true, entry: 10, stopVigente: 9.4, target1: 11 }),
        markPrice: 9,
      }),
    );
    expect(frio.moment.thermometer?.state).toBe("frio");
  });

  it("con posición el momento es la geometría de salida, no un termómetro", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("hold_watch"),
        position: position(),
        phase: "posicion",
        plan: plan({
          hasPlan: true,
          phase: "position",
          entry: 10,
          stopVigente: 9.5,
          target1: 11.2,
          target2: 12,
        }),
      }),
    );
    expect(row.moment.kind).toBe("posicion");
    expect(row.moment.thermometer).toBeNull();
    expect(row.moment.detail).toContain("Stop 9,50");
    expect(row.moment.detail).toContain("T1 11,20");
  });

  it("posición sin geometría publicada declara el hueco", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        position: position(),
        phase: "posicion",
        plan: plan({ hasPlan: false }),
      }),
    );
    expect(row.moment.detail).toBeNull();
    expect(row.moment.gaps).toContain("Sin geometría de salida publicada");
  });
});

// ── 5 · Posición, filtro, orden y resumen ──────────────────────────────────

describe("buildAsesorCarteraRow · valores publicados por el backend", () => {
  it("declara el cierre y la frescura, sin inventar cuando no llegan", () => {
    const stale = buildAsesorCarteraRow(
      rowInput({
        quote: {
          price: 10.5,
          changePct: 1.2,
          lastBarDate: "2026-11-11",
          expectedLastBarDate: "2026-11-12",
          freshness: "stale",
        },
      }),
    );
    expect(stale.quote.lastBarDate).toBe("2026-11-11");
    expect(stale.quote.expectedLastBarDate).toBe("2026-11-12");
    expect(stale.quote.freshness).toBe("stale");
    expect(stale.quote.stale).toBe(true);
    expect(stale.quote.staleLabel).toContain("desactualizado");

    const unmeasured = buildAsesorCarteraRow(
      rowInput({ quote: { price: 10.5, changePct: 1.2 } }),
    );
    expect(unmeasured.quote.lastBarDate).toBeNull();
    expect(unmeasured.quote.freshness).toBeNull();
    expect(unmeasured.quote.stale).toBe(false);
    expect(unmeasured.quote.staleLabel).toBeNull();
  });

  it("copia estrellas, scores y veredicto del dictamen sin cambiar la etiqueta", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("buy", {
          ioScore: 84,
          dictamenStars: 5,
          faScore: 70,
          taScore: 88,
          gateStatus: "VETO",
          distress: true,
          engineVersion: "opinion_v2",
          computedAt: "2026-11-12T19:00:00.000Z",
        }),
      }),
    );

    expect(row.recommendation.label).toBe("Comprar");
    expect(row.recommendation.dictamenStars).toBe(5);
    expect(row.recommendation.faScore).toBe(70);
    expect(row.recommendation.taScore).toBe(88);
    expect(row.recommendation.gateStatus).toBe("VETO");
    expect(row.recommendation.distress).toBe(true);
    expect(row.recommendation.engineVersion).toBe("opinion_v2");
    expect(row.recommendation.computedAt).toBe("2026-11-12T19:00:00.000Z");
  });

  it("una opinión sin scores declara el hueco y no fabrica ★", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("hold_watch", {
          ioScore: null,
          dictamenStars: 4,
          faScore: null,
          taScore: null,
        }),
      }),
    );
    expect(row.recommendation.dictamenStars).toBeNull();
    expect(row.recommendation.faScore).toBeNull();
    expect(row.recommendation.starsLabel).toBe("Sin medir");
    // R-02: el hueco del score se declara en la fila, no se omite.
    expect(row.recommendation.gaps).toContain("Calidad de señal sin medir");
    expect(row.gaps).toContain("Calidad de señal sin medir");
  });

  it("distingue la tendencia de corto plazo de la de fondo", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        study: study({
          trends: [
            {
              key: "short_term",
              label: "Corto plazo",
              value: "bullish",
              display: "Alcista",
            },
            {
              key: "background",
              label: "Fondo",
              value: "bearish",
              display: "Bajista",
            },
          ],
          indicators: { primary: "ADX 28", confirmation: "RSI 55" },
        }),
      }),
    );

    expect(row.trend.shortTermLabel).toBe("Alcista");
    expect(row.trend.backgroundLabel).toBe("Bajista");
    expect(row.trend.confirmation).toBe("RSI 55");
    expect(row.trend.basis).toBe("ADX 28");
  });

  it("publica la distancia con signo de cada nivel y la estructura", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        structure: structure({
          supports: [
            { ...level("support", 9.8, "detectado"), distancePct: -6.7 },
          ],
          resistances: [
            { ...level("resistance", 11.2, "detectado"), distancePct: 6.7 },
          ],
        }),
      }),
    );

    expect(row.levels.supportDistancePct).toBe(-6.7);
    expect(row.levels.resistanceDistancePct).toBe(6.7);
    expect(row.levels.supportDistanceLabel).toBe("-6,70 %");
    expect(row.levels.resistanceDistanceLabel).toBe("+6,70 %");
    expect(row.levels.structureId).toBe("ascendente");
    expect(row.levels.structureLabel).toBe("Estructura ascendente");
    expect(row.levels.close).toBe(10.5);
    expect(row.levels.atrRef).toBe(0.4);
    expect(row.levels.stateSummary.detectado).toBe(2);
  });

  it("sin nivel dibujable declara el estado del más cercano", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        structure: structure({
          supports: [level("support", 9.8, "roto")],
        }),
      }),
    );

    expect(row.levels.measured).toBe(false);
    expect(row.levels.nearestStateLabel).toBe("Roto");
    expect(row.levels.detail).toContain("roto");
    expect(row.levels.stateSummary.roto).toBe(1);
  });

  it("publica la geometría del momento también con posición", () => {
    const values = plan({
      entry: 10.6,
      stopVigente: 10.1,
      target1: 11.2,
      target2: 12,
      hasPlan: true,
    });
    const entrada = buildAsesorCarteraRow(rowInput({ plan: values }));
    expect(entrada.moment.entry).toBe(10.6);
    expect(entrada.moment.invalidation).toBe(10.1);
    expect(entrada.moment.geometryLabel).toBe(
      "E 10,60 · S 10,10 · T1 11,20 · T2 12,00",
    );

    const salida = buildAsesorCarteraRow(
      rowInput({ plan: values, position: position(), phase: "posicion" }),
    );
    expect(salida.moment.kind).toBe("posicion");
    expect(salida.moment.geometryLabel).toBe(
      "E 10,60 · S 10,10 · T1 11,20 · T2 12,00",
    );
  });

  it("copia consenso, invalidantes y revisión del parte al detalle", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        study: study({
          consensus: { bullish: 4, bearish: 1, neutral: 2, total: 7 },
          invalidation: ["Cierre bajo 9,80"],
          nextReviewAt: "2026-11-13T08:00:00.000Z",
        }),
      }),
    );

    expect(row.studyDetail?.consensus?.bullish).toBe(4);
    expect(row.studyDetail?.invalidation).toEqual(["Cierre bajo 9,80"]);
    expect(row.studyDetail?.nextReviewAt).toBe("2026-11-13T08:00:00.000Z");
  });

  it("la ampliación no agrega señales: el estado sigue siendo solo el dictamen", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("hold_watch", { ioScore: 55 }),
        study: study({
          trends: [
            {
              key: "short_term",
              label: "Corto plazo",
              value: "bullish",
              display: "Alcista",
            },
            {
              key: "background",
              label: "Fondo",
              value: "bullish",
              display: "Alcista",
            },
          ],
          strength: 9,
          strengthBand: "strong",
        }),
        structure: structure({
          supports: [level("support", 9.8, "detectado")],
          resistances: [level("resistance", 11.2, "detectado")],
        }),
      }),
    );

    expect(row.state.id).toBe("evaluado_sin_oportunidad");
    expect(row.recommendation.label).toBe("Mantener");
  });
});

describe("buildAsesorCarteraRow · posición", () => {
  it("cartera medida sin posición dice «Sin posición»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ position: null, portfolioMeasured: true }),
    );
    expect(row.position.label).toBe("Sin posición");
    expect(row.position.measured).toBe(true);
  });

  it("cartera no medida dice «Cartera sin medir», nunca «Sin posición»", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ position: null, portfolioMeasured: false }),
    );
    expect(row.position.label).toBe("Cartera sin medir");
    expect(row.position.measured).toBe(false);
  });

  it("con posición publica cantidad, coste y P&L", () => {
    const row = buildAsesorCarteraRow(
      rowInput({ position: position(), phase: "posicion" }),
    );
    expect(row.position.hasOpenPosition).toBe(true);
    expect(row.position.quantity).toBe(100);
    expect(row.position.detail).toContain("100 uds");
    expect(row.position.detail).toContain("P&L +5,00 %");
  });
});

describe("filtrar, ordenar y resumir", () => {
  function row(
    symbol: string,
    stance: InstrumentDailyOpinionV1["stance"],
    positionDto: PositionDto | null,
    confidence = 70,
  ): AsesorCarteraRowV1 {
    return buildAsesorCarteraRow(
      rowInput({
        instrumentId: `inst-${symbol}`,
        symbol,
        opinion: opinion(stance, { ioScore: confidence }),
        position: positionDto,
        phase: positionDto ? "posicion" : "vigilar",
      }),
    );
  }

  const rows = [
    row("CCC", "hold_watch", null, 40),
    row("AAA", "buy", null, 90),
    row("BBB", "overbought", position({ symbol: "BBB", instrumentId: "inst-BBB" })),
  ];

  it("filtra por estado y por «solo con posición»", () => {
    expect(
      filterAsesorCarteraRows(rows, {
        state: "recomendacion_favorable",
        onlyWithPosition: false,
      }).map((r) => r.symbol),
    ).toEqual(["AAA"]);
    expect(
      filterAsesorCarteraRows(rows, {
        state: "todos",
        onlyWithPosition: true,
      }).map((r) => r.symbol),
    ).toEqual(["BBB"]);
    expect(filterAsesorCarteraRows(rows, DEFAULT_ASESOR_CARTERA_FILTER)).toHaveLength(
      3,
    );
  });

  it("ordena por categoría y luego por confianza, no por indicadores", () => {
    expect(sortAsesorCarteraRows(rows).map((r) => r.symbol)).toEqual([
      "BBB",
      "AAA",
      "CCC",
    ]);
  });

  it("el resumen cuenta estados y huecos", () => {
    const summary = summarizeAsesorCartera(rows);
    expect(summary.total).toBe(3);
    expect(summary.withPosition).toBe(1);
    expect(summary.byState.posicion_sin_respaldo).toBe(1);
    expect(summary.byState.recomendacion_favorable).toBe(1);
    expect(summary.byState.evaluado_sin_oportunidad).toBe(1);
    expect(summary.unmeasured).toBe(0);
  });
});

// ── 6 · Guarda de vocabulario ──────────────────────────────────────────────

describe("etiquetas visibles", () => {
  it("ninguna etiqueta renderizable filtra una clave snake_case", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("buy", {
          ioScore: 85,
          reasons: ["strong_buy_signal", "top_high", "io_high", "top_medium"],
        }),
        study: study(),
        structure: structure({
          supports: [level("support", 10.4, "detectado")],
          resistances: [level("resistance", 11.2, "detectado")],
        }),
        plan: plan({ hasPlan: true, entry: 10.6, stopVigente: 10.1 }),
      }),
    );
    const visible = [
      row.state.label,
      row.recommendation.label,
      row.recommendation.detail ?? "",
      ...row.recommendation.reasons,
      row.recommendation.reasonsTooltip ?? "",
      row.trend.label,
      row.strength.label,
      row.levels.detail,
      row.levels.supportLabel,
      row.levels.resistanceLabel,
      row.moment.phaseLabel,
      row.moment.detail ?? "",
      row.position.label,
      row.position.detail ?? "",
      ...row.gaps,
    ];
    for (const text of visible) {
      expect(text).not.toMatch(INTERNAL_KEY);
    }
  });

  it("un IO sin medir no pinta ★ fabricadas", () => {
    const row = buildAsesorCarteraRow(
      rowInput({
        opinion: opinion("hold_watch", { ioScore: null, dictamenStars: 3 }),
      }),
    );
    expect(row.recommendation.confidenceLabel).toBe("Sin medir");
    expect(row.recommendation.starsLabel).toBe("Sin medir");
    expect(row.recommendation.starsLabel).not.toContain("★★★★");
  });
});
