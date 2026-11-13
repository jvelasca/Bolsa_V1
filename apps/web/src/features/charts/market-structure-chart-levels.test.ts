import { describe, expect, it } from "vitest";
import {
  MARKET_STRUCTURE_DEFAULTS,
  type MarketLevelV1,
  type MarketStructureResultV1,
} from "@bolsa/shared";
import {
  MARKET_STRUCTURE_LEVEL_ID_PREFIX,
  buildMarketStructureChartLevels,
  describeMarketStructureLevels,
  marketStructureChartLevelsSignature,
} from "@/features/charts/market-structure-chart-levels";
import { SR_PRESETS } from "@/features/charts/chart-sr-presets";

function level(
  partial: Partial<MarketLevelV1> & Pick<MarketLevelV1, "kind">,
): MarketLevelV1 {
  return {
    price: 10,
    zoneLow: 10,
    zoneHigh: 10,
    touches: 2,
    state: "detectado",
    reasons: [],
    pivots: [],
    lastTouchAt: null,
    distancePct: 0,
    distanceAtr: 0,
    ...partial,
  };
}

function result(
  partial: Partial<MarketStructureResultV1> = {},
): MarketStructureResultV1 {
  return {
    methodId: "swing-atr-v1",
    methodVersion: 1,
    params: { ...MARKET_STRUCTURE_DEFAULTS },
    window: { from: null, to: null, bars: 120, timeframe: "1d" },
    inputSignature: "firma",
    status: "ok",
    reasons: [],
    atrRef: 0.2,
    close: 10.5,
    supports: [],
    resistances: [],
    structure: { id: "sin_estructura", tolerance: null, highs: [], lows: [] },
    lastBarMayBeOpen: false,
    ...partial,
  };
}

describe("buildMarketStructureChartLevels", () => {
  it("solo los niveles detectados producen línea", () => {
    const levels = buildMarketStructureChartLevels({
      result: result({
        supports: [
          level({ kind: "support", price: 9.5 }),
          level({ kind: "support", price: 9.8, state: "no_fiable", reasons: ["un_solo_toque"] }),
          level({ kind: "support", price: 9.2, state: "roto", reasons: ["nivel_roto"] }),
        ],
        resistances: [
          level({ kind: "resistance", price: 11, state: "en_precio", reasons: ["precio_en_nivel"] }),
          level({ kind: "resistance", price: 12 }),
        ],
      }),
    });
    expect(levels.map((line) => line.kind)).toEqual(["support", "resistance"]);
    expect(levels.map((line) => line.price)).toEqual([9.5, 12]);
  });

  it("sin medición no dibuja nada", () => {
    expect(
      buildMarketStructureChartLevels({
        result: result({ status: "insufficient_history" }),
      }),
    ).toEqual([]);
    expect(buildMarketStructureChartLevels({ result: null })).toEqual([]);
    expect(buildMarketStructureChartLevels({ result: undefined })).toEqual([]);
  });

  it("un nivel no disponible tampoco se pinta", () => {
    const levels = buildMarketStructureChartLevels({
      result: result({
        supports: [level({ kind: "support", state: "no_disponible" })],
      }),
    });
    expect(levels).toEqual([]);
  });

  it("el estilo no se confunde con el preset manual", () => {
    const manualColors = new Set(SR_PRESETS.map((preset) => preset.color));
    const manualLabels = new Set(SR_PRESETS.map((preset) => preset.label));
    const levels = buildMarketStructureChartLevels({
      result: result({
        supports: [level({ kind: "support", price: 9.7 })],
        resistances: [level({ kind: "resistance", price: 11.3 })],
      }),
    });
    for (const line of levels) {
      expect(line.style).toBe("dashed");
      expect(line.width).toBe(1);
      expect(manualColors.has(line.color)).toBe(false);
      expect(manualLabels.has(line.title)).toBe(false);
    }
    expect(levels[0]!.title).toBe("S·calc 9,70");
    expect(levels[1]!.title).toBe("R·calc 11,30");
  });

  it("declara la coincidencia con el plan operativo sin apropiarse de ella", () => {
    const levels = buildMarketStructureChartLevels({
      result: result({ supports: [level({ kind: "support", price: 10 })] }),
      planLevels: [
        { price: 10.02, title: "Entrada" },
        { price: 12, title: "T2" },
      ],
    });
    expect(levels[0]!.collidesWith).toBe("Entrada");
    expect(levels[0]!.title).toContain("coincide con Entrada");
  });

  it("ids estables por lado y posición", () => {
    const levels = buildMarketStructureChartLevels({
      result: result({
        supports: [level({ kind: "support", price: 9.7 })],
        resistances: [level({ kind: "resistance", price: 11.3 })],
      }),
    });
    expect(levels[0]!.id).toBe(`${MARKET_STRUCTURE_LEVEL_ID_PREFIX}:support:0`);
    expect(levels[1]!.id).toBe(`${MARKET_STRUCTURE_LEVEL_ID_PREFIX}:resistance:0`);
  });

  it("la firma cambia cuando cambia el precio dibujado", () => {
    const a = buildMarketStructureChartLevels({
      result: result({ supports: [level({ kind: "support", price: 9.7 })] }),
    });
    const b = buildMarketStructureChartLevels({
      result: result({ supports: [level({ kind: "support", price: 9.8 })] }),
    });
    expect(marketStructureChartLevelsSignature(a)).not.toBe(
      marketStructureChartLevelsSignature(b),
    );
    expect(marketStructureChartLevelsSignature(a)).toBe(
      marketStructureChartLevelsSignature(a),
    );
  });
});

describe("describeMarketStructureLevels", () => {
  it("declara el hueco por histórico insuficiente", () => {
    const summary = describeMarketStructureLevels(
      result({ status: "insufficient_history" }),
    );
    expect(summary.measured).toBe(false);
    expect(summary.detail).toBe("Histórico insuficiente");
  });

  it("declara «sin niveles fiables» cuando se midió pero nada pasó el filtro", () => {
    const summary = describeMarketStructureLevels(
      result({ supports: [level({ kind: "support", state: "no_fiable" })] }),
    );
    expect(summary.measured).toBe(true);
    expect(summary.supports).toBe(0);
    expect(summary.detail).toBe("Sin niveles fiables en la ventana");
  });

  it("cuenta solo los dibujables", () => {
    const summary = describeMarketStructureLevels(
      result({
        supports: [level({ kind: "support" })],
        resistances: [
          level({ kind: "resistance", price: 11 }),
          level({ kind: "resistance", price: 12 }),
        ],
      }),
    );
    expect(summary.supports).toBe(1);
    expect(summary.resistances).toBe(2);
    expect(summary.detail).toBe("1 soporte · 2 resistencias");
  });
});
