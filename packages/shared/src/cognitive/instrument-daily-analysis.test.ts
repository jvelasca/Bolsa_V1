import { describe, expect, it } from "vitest";
import {
  buildInstrumentDailyAnalysis,
  dailyTrendTone,
  type BuildInstrumentDailyAnalysisInput,
} from "./instrument-daily-analysis.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type {
  MercadoTrailingCopyV1,
  MercadoCockpitPhase,
} from "./mercado-cockpit-phase.js";
import type { OperationalPlanViewV1 } from "./operational-plan-view.js";
import type { InstrumentStrategyTopSlotV1 } from "../instrument-strategy-top.js";

const EMPTY_TRAILING: MercadoTrailingCopyV1 = {
  show: false,
  stopVigente: null,
  stopSugerido: null,
  applied: false,
  label: "↗ Trailing sugerido",
  stopVigenteLabel: "Stop operativo",
  stopSugeridoLabel: "Stop sugerido",
  statusLabel: null,
};

function study(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    studiedAt: "2026-11-10T08:00:00.000Z",
    ageMs: 3_600_000,
    vigencia: "current",
    indicators: { primary: "ADX + DI", confirmation: "SMA" },
    trends: [
      {
        key: "short_term",
        label: "Corto plazo",
        value: "bullish",
        display: "Alcista",
      },
      {
        key: "background",
        label: "De fondo",
        value: "bullish_stack",
        display: "Alcista",
      },
    ],
    invalidation: ["Cierre diario bajo la SMA 50"],
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

function plan(
  overrides: Partial<OperationalPlanViewV1> = {},
): OperationalPlanViewV1 {
  return {
    phase: "prepared",
    phaseLabel: "Preparada",
    direction: "long",
    entry: 100,
    stopVigente: 94,
    stopInicial: 94,
    target1: 112,
    target2: 124,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: 2,
    riskR: 6,
    currentPrice: 101,
    unrealizedR: null,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: true,
    emptyCopy: "Sin plan operativo",
    ...overrides,
  } as OperationalPlanViewV1;
}

function slot(
  overrides: Partial<InstrumentStrategyTopSlotV1> = {},
): InstrumentStrategyTopSlotV1 {
  return {
    rank: 1,
    label: "Cruce SMA 20/50",
    strategyType: "sma_crossover",
    stars: 4,
    score: 82,
    source: "coach",
    ...overrides,
  } as InstrumentStrategyTopSlotV1;
}

function input(
  overrides: Partial<BuildInstrumentDailyAnalysisInput> = {},
): BuildInstrumentDailyAnalysisInput {
  return {
    instrumentId: "inst-1",
    inEstudio: true,
    study: study(),
    phase: "preparada" as MercadoCockpitPhase,
    showsPlanLevels: true,
    plan: plan(),
    trailing: EMPTY_TRAILING,
    markPrice: 101,
    slot: slot(),
    definition: null,
    reasons: ["Cruce limpio con ADX > 25"],
    evidenceLevel: "lab_validated",
    stabilityLabel: "OOS estable",
    ...overrides,
  };
}

describe("instrument-daily-analysis", () => {
  it("copia la tendencia canónica del estudio y deriva el tono", () => {
    const analysis = buildInstrumentDailyAnalysis(input());
    expect(analysis.measured).toBe(true);
    expect(analysis.trends).toEqual([
      {
        key: "short_term",
        label: "Corto plazo",
        value: "bullish",
        display: "Alcista",
        tone: "bullish",
        basis: "ADX + DI",
      },
      {
        key: "background",
        label: "De fondo",
        value: "bullish_stack",
        display: "Alcista",
        tone: "bullish",
        basis: "SMA",
      },
    ]);
    expect(analysis.studyMeta?.vigencia).toBe("current");
    expect(analysis.studyMeta?.indicators.primary).toBe("ADX + DI");
  });

  it("sin parte diario declara el hueco y no inventa tendencia", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({ study: null, slot: null, reasons: [] }),
    );
    expect(analysis.measured).toBe(false);
    expect(analysis.trends).toEqual([]);
    expect(analysis.studyMeta).toBeNull();
    expect(analysis.gaps).toContain("Sin análisis diario todavía");
  });

  it("vigilar no expone niveles aunque el plan los tenga", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({ phase: "vigilar", showsPlanLevels: false }),
    );
    expect(analysis.entry).not.toBeNull();
    expect(analysis.entry?.entry).toBeNull();
    expect(analysis.entry?.stop).toBeNull();
    expect(analysis.entry?.stateLabel).toBe("En estudio");
    expect(analysis.entry?.missing).toContain("Esperando disparador");
    expect(analysis.exit).toBeNull();
  });

  it("preparada expone entrada/stop/T1/T2 y el disparador pendiente", () => {
    const analysis = buildInstrumentDailyAnalysis(input());
    expect(analysis.entry).toEqual({
      state: "preparada",
      stateLabel: "Preparada",
      entry: 100,
      stop: 94,
      target1: 112,
      target2: 124,
      expectedRR: 2,
      distancePct: 1,
      missing: "Disparador pendiente",
    });
  });

  it("propuesta sin geometría declara el estado, no un «plan sin niveles» genérico", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({
        phase: "propuesta",
        showsPlanLevels: true,
        plan: plan({
          hasPlan: false,
          entry: null,
          stopVigente: null,
          target1: null,
          target2: null,
        }),
      }),
    );
    expect(analysis.entry?.stateLabel).toBe("Propuesta");
    expect(analysis.entry?.entry).toBeNull();
    expect(analysis.entry?.missing).toBe(
      "Propuesta en cola · sin geometría publicada",
    );
  });

  it("posicion expone la salida con trailing no aplicado y T1 gestionado", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({
        phase: "posicion",
        plan: plan({
          stopVigente: 100,
          target1Touched: true,
          target1Managed: true,
          unrealizedR: 1.4,
        }),
        trailing: {
          show: true,
          stopVigente: 100,
          stopSugerido: 103,
          applied: false,
          label: "↗ Trailing sugerido",
          stopVigenteLabel: "Stop operativo",
          stopSugeridoLabel: "Stop sugerido",
          statusLabel: "No aplicado · requiere Confirm",
        },
      }),
    );
    expect(analysis.entry).toBeNull();
    expect(analysis.exit).toEqual({
      stop: 100,
      target1Hint: "✓ gestionado",
      target2Hint: "○ pendiente",
      trailingLabel: "No aplicado · requiere Confirm",
      unrealizedR: 1.4,
      invalidation: "Cierre diario bajo la SMA 50",
    });
  });

  it("fuera de Estudio declara el hueco y no da seguimiento", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({ inEstudio: false, slot: null, reasons: [] }),
    );
    expect(analysis.tracking.gap).toBe("Fuera de Estudio");
    expect(analysis.tracking.indicators).toEqual([]);
    expect(analysis.gaps).toContain("Fuera de Estudio");
  });

  it("parte caducado y estrategia sin indicadores se declaran", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({
        study: study({ vigencia: "expired" }),
        slot: slot({ strategyType: null }),
      }),
    );
    expect(analysis.gaps).toContain("Parte diario caducado");
    expect(analysis.gaps).toContain("Estrategia sin indicadores declarados");
  });

  it("reutiliza los indicadores de la definición con parámetros", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({
        definition: {
          indicatorSpecs: [
            { definitionId: "sma", parameters: { period: 20 } },
            { definitionId: "sma", parameters: { period: 50 } },
            { definitionId: "rsi", parameters: { period: 14 } },
          ],
        },
      }),
    );
    expect(analysis.tracking.indicators.map((item) => item.display)).toEqual([
      "SMA 20/50",
      "RSI 14",
    ]);
    expect(analysis.tracking.reason).toBe("Cruce limpio con ADX > 25");
    expect(analysis.tracking.evidenceLevel).toBe("lab_validated");
  });

  it("tono desconocido cuando el estudio no trae valor", () => {
    expect(dailyTrendTone(null)).toBe("unknown");
    expect(dailyTrendTone("weak")).toBe("range");
    expect(dailyTrendTone("strong_bearish")).toBe("bearish");
  });

  it("rango, mixta y neutra son tres tonos distintos", () => {
    expect(dailyTrendTone("weak")).toBe("range");
    expect(dailyTrendTone("mixed")).toBe("mixed");
    expect(dailyTrendTone("neutral")).toBe("neutral");
  });

  it("un valor canónico sin display se traduce, nunca se pinta en crudo", () => {
    const analysis = buildInstrumentDailyAnalysis(
      input({
        study: study({
          trends: [
            { key: "short_term", label: "Corto plazo", value: "weak", display: null },
          ],
        }),
      }),
    );
    expect(analysis.trends[0]?.display).toBe("Lateral");
    expect(analysis.trends[0]?.value).toBe("weak");
    expect(analysis.trends[0]?.tone).toBe("range");
  });
});
