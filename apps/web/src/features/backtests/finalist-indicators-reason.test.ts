/**
 * S3 — cadena Estrategia → indicadores que la sustentan → razón.
 * Indicadores desde la definición/preset (no el catálogo del gráfico);
 * razones desde `coachFacts.recommendations[].reasons`.
 */

import { describe, expect, it } from "vitest";
import { strategySlotToIndicatorLabels } from "@bolsa/shared";
import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";
import {
  buildStrategyDefinitionRefMap,
  readRecommendationReasons,
} from "@/features/backtests/instrument-strategy-top-panel";

function slot(
  partial: Partial<InstrumentStrategyTopSlotV1> = {},
): InstrumentStrategyTopSlotV1 {
  return {
    rank: 1,
    label: "SMA cross",
    stars: 3,
    score: 70,
    source: "coach",
    ...partial,
  };
}

describe("strategySlotToIndicatorLabels (S3)", () => {
  it("resuelve indicadores del preset de la estrategia (nombres legibles)", () => {
    const res = strategySlotToIndicatorLabels({
      slot: slot({ strategyType: "sma_crossover" }),
    });
    expect(res.source).toBe("preset");
    expect(res.labels.length).toBeGreaterThan(0);
    expect(res.labels.every((l) => l.trim().length > 0)).toBe(true);
  });

  it("prefiere definition.indicatorSpecs cuando está disponible", () => {
    const res = strategySlotToIndicatorLabels({
      slot: slot(),
      definition: {
        indicatorSpecs: [{ definitionId: "rsi", parameters: { period: 14 } }],
      },
    });
    expect(res.source).toBe("definition");
    expect(res.labels).toEqual(["RSI"]);
  });

  it("sin fuente fiable declara vacío (no deduce del catálogo del gráfico)", () => {
    const res = strategySlotToIndicatorLabels({
      slot: slot({ strategyType: null }),
    });
    expect(res.labels).toEqual([]);
    expect(res.source).toBe("empty");
  });
});

describe("readRecommendationReasons (S3)", () => {
  it("devuelve las razones del rank correspondiente", () => {
    const facts = {
      recommendations: [
        { rank: 1, reasons: ["Estrellas 3/5", "DD -12%"] },
        { rank: 2, reasons: ["ventana reciente débil"] },
      ],
    };
    expect(readRecommendationReasons(facts, 1)).toEqual([
      "Estrellas 3/5",
      "DD -12%",
    ]);
    expect(readRecommendationReasons(facts, 2)).toEqual([
      "ventana reciente débil",
    ]);
  });

  it("sin razones persistidas devuelve vacío (se declara, no se inventa)", () => {
    expect(readRecommendationReasons(null, 1)).toEqual([]);
    expect(readRecommendationReasons({}, 1)).toEqual([]);
    expect(
      readRecommendationReasons({ recommendations: [{ rank: 1 }] }, 1),
    ).toEqual([]);
  });
});

describe("buildStrategyDefinitionRefMap (S3 — el detalle manda sobre el summary)", () => {
  it("usa los indicatorSpecs del detalle y resuelve indicadores (definition)", () => {
    const map = buildStrategyDefinitionRefMap({
      summaries: [{ id: "s1", presetKey: "sma_crossover" }],
      details: [
        {
          id: "s1",
          definition: {
            indicatorSpecs: [
              { definitionId: "rsi", parameters: { period: 14 } },
            ],
            presetKey: "sma_crossover",
          },
        },
      ],
    });
    const ref = map.get("s1");
    expect(ref?.indicatorSpecs).toEqual([
      { definitionId: "rsi", parameters: { period: 14 } },
    ]);
    const resolved = strategySlotToIndicatorLabels({
      slot: slot({ strategyType: "sma_crossover" }),
      definition: ref ?? null,
    });
    expect(resolved.source).toBe("definition");
    expect(resolved.labels).toEqual(["RSI"]);
  });

  it("sin detalle conserva el presetKey del summary (fallback a preset)", () => {
    const map = buildStrategyDefinitionRefMap({
      summaries: [{ id: "s2", presetKey: "sma_crossover" }],
      details: [null, undefined],
    });
    expect(map.get("s2")).toEqual({
      indicatorSpecs: [],
      presetKey: "sma_crossover",
    });
    const resolved = strategySlotToIndicatorLabels({
      slot: slot({ strategyType: "sma_crossover" }),
      definition: map.get("s2") ?? null,
    });
    expect(resolved.source).toBe("preset");
  });
});
