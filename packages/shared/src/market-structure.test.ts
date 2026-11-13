import { describe, expect, it } from "vitest";
import type { OhlcvBarDto } from "./types.js";
import {
  MARKET_STRUCTURE_DEFAULTS,
  MARKET_STRUCTURE_METHOD_ID,
  buildMarketLevel,
  computeMarketStructure,
  computeWilderAtr,
  describeMarketStructure,
  detectSwings,
  groupPivotsByAtr,
  marketLevelIsDrawable,
  marketStructureLevels,
  type MarketPivotTypeV1,
  type MarketPivotV1,
} from "./market-structure.js";

const START = Date.UTC(2026, 0, 1);
const DAY = 86_400_000;

function iso(index: number): string {
  return new Date(START + index * DAY).toISOString();
}

function bar(
  index: number,
  high: number,
  low: number,
  close = (high + low) / 2,
): OhlcvBarDto {
  return {
    timestamp: iso(index),
    open: close,
    high,
    low,
    close,
    volume: 1_000,
    adjClose: null,
    source: "yahoo",
  };
}

/** Zigzag con patas lineales: produce pivotes limpios en cada giro. */
function zigzag(
  points: readonly number[],
  legBars = 10,
  halfRange = 0.15,
): OhlcvBarDto[] {
  const bars: OhlcvBarDto[] = [];
  let index = 0;
  for (let p = 0; p < points.length - 1; p += 1) {
    const from = points[p]!;
    const to = points[p + 1]!;
    for (let k = 0; k < legBars; k += 1) {
      const price = from + ((to - from) * k) / legBars;
      bars.push(bar(index, price + halfRange, price - halfRange, price));
      index += 1;
    }
  }
  const last = points[points.length - 1]!;
  bars.push(bar(index, last + halfRange, last - halfRange, last));
  return bars;
}

function pivot(
  index: number,
  price: number,
  type: MarketPivotTypeV1,
): MarketPivotV1 {
  return { index, timestamp: iso(index), price, type };
}

/** Fixture estable: soporte y resistencia con varios toques, cierre lejos. */
function twoTouchFixture(): OhlcvBarDto[] {
  return zigzag([
    11.5, 10.0, 11.55, 10.05, 11.5, 10.0, 11.55, 10.05, 10.8,
  ]);
}

describe("market-structure · pivotes", () => {
  it("confirma un swing high cuando supera estrictamente N velas a cada lado", () => {
    const highs = [10, 11, 12, 13, 12.5, 11.5, 11, 10.5, 10];
    const lows = [9, 9.5, 10, 10.5, 11, 10.5, 10, 9.5, 9];
    const bars = highs.map((high, i) => bar(i, high, lows[i]!));
    const result = detectSwings(bars, 3);
    expect(result.highs.map((p) => p.index)).toEqual([3]);
    expect(result.lows).toEqual([]);
    expect(result.highs[0]!.price).toBe(13);
  });

  it("un empate no genera pivote (nunca dos gemelos del mismo techo)", () => {
    const bars = [
      bar(0, 10, 9),
      bar(1, 12, 9.5),
      bar(2, 12, 9.5),
      bar(3, 10, 9),
    ];
    const result = detectSwings(bars, 1);
    expect(result.highs).toEqual([]);
    expect(result.lows).toEqual([]);
  });

  it("la última vela nunca confirma pivote", () => {
    const bars = [
      bar(0, 10, 9),
      bar(1, 11, 9.5),
      bar(2, 12, 10),
      bar(3, 13, 10.5),
      bar(4, 14, 11),
    ];
    const result = detectSwings(bars, 2);
    expect(result.highs).toEqual([]);
  });

  it("una serie demasiado corta no produce pivotes", () => {
    expect(detectSwings([bar(0, 10, 9)], 3)).toEqual({ highs: [], lows: [] });
  });
});

describe("market-structure · ATR", () => {
  it("con rango constante el ATR de Wilder es ese rango", () => {
    const bars = Array.from({ length: 20 }, (_, i) => bar(i, 10, 9, 9.5));
    const atr = computeWilderAtr(bars, 14);
    expect(atr.slice(0, 13).every((value) => value == null)).toBe(true);
    expect(atr[13]).toBeCloseTo(1, 10);
    expect(atr[19]).toBeCloseTo(1, 10);
  });

  it("serie vacía o periodo inválido devuelve vacío", () => {
    expect(computeWilderAtr([], 14)).toEqual([]);
    expect(computeWilderAtr([bar(0, 10, 9)], 0)).toEqual([]);
  });
});

describe("market-structure · agrupación por ATR", () => {
  const pivots = [pivot(1, 10, "low"), pivot(2, 10.05, "low"), pivot(3, 10.3, "low")];

  it("agrupa dentro de la tolerancia y separa fuera", () => {
    const tight = groupPivotsByAtr(pivots, 0.15);
    expect(tight).toHaveLength(2);
    expect(tight[0]!.pivots).toHaveLength(2);
    expect(tight[0]!.price).toBeCloseTo(10.025, 10);
    expect(tight[0]!.zoneLow).toBe(10);
    expect(tight[0]!.zoneHigh).toBeCloseTo(10.05, 10);

    const wide = groupPivotsByAtr(pivots, 0.4);
    expect(wide).toHaveLength(1);
    expect(wide[0]!.pivots).toHaveLength(3);
    expect(wide[0]!.zoneLow).toBe(10);
    expect(wide[0]!.zoneHigh).toBe(10.3);
  });

  it("mide contra el centro del grupo, no contra el último pivote", () => {
    // 10, 10.2 y 10.4 encadenados por 0,2: contra el centro (10,2) el tercero queda fuera.
    const chained = [
      pivot(1, 10, "low"),
      pivot(2, 10.2, "low"),
      pivot(3, 10.4, "low"),
    ];
    const groups = groupPivotsByAtr(chained, 0.25);
    expect(groups).toHaveLength(2);
  });
});

describe("market-structure · estado de un nivel", () => {
  const recentTwo = [pivot(80, 10, "low"), pivot(90, 10.05, "low")];

  it("un solo toque es no fiable y lo declara", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: [pivot(90, 10, "low")],
      close: 12,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("no_fiable");
    expect(level.reasons).toEqual(["un_solo_toque"]);
  });

  it("dos toques recientes son un nivel detectado", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: recentTwo,
      close: 12,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("detectado");
    expect(level.reasons).toEqual([]);
    expect(level.touches).toBe(2);
  });

  it("dos toques antiguos no son estructura vigente", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: [pivot(10, 10, "low"), pivot(20, 10.05, "low")],
      close: 12,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("no_fiable");
    expect(level.reasons).toEqual(["sin_toque_reciente"]);
  });

  it("tres toques antiguos siguen siendo un nivel", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: [
        pivot(10, 10, "low"),
        pivot(20, 10.05, "low"),
        pivot(30, 10.02, "low"),
      ],
      close: 12,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("detectado");
  });

  it("el precio dentro de 0,25 ATR deja el nivel en precio", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: recentTwo,
      close: 10.03,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("en_precio");
    expect(level.reasons).toEqual(["precio_en_nivel"]);
  });

  it("un soporte perdido se declara roto", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: recentTwo,
      close: 9.5,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("roto");
    expect(level.reasons).toEqual(["nivel_roto"]);
  });

  it("una resistencia superada se declara rota", () => {
    const level = buildMarketLevel({
      kind: "resistance",
      pivots: [pivot(80, 10, "high"), pivot(90, 10.05, "high")],
      close: 10.5,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("roto");
  });

  it("la fiabilidad manda: un pivote aislado no puede estar en precio ni roto", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: [pivot(90, 10, "low")],
      close: 9.4,
      atrRef: 0.2,
      barsCount: 100,
    });
    expect(level.state).toBe("no_fiable");
    expect(level.reasons).toEqual(["un_solo_toque"]);
  });

  it("declara distancias y conserva la procedencia", () => {
    const level = buildMarketLevel({
      kind: "support",
      pivots: recentTwo,
      close: 10.5,
      atrRef: 0.5,
      barsCount: 100,
    });
    expect(level.price).toBeCloseTo(10.025, 10);
    expect(level.distancePct).toBeCloseTo(((10.025 - 10.5) / 10.5) * 100, 10);
    expect(level.distanceAtr).toBeCloseTo((10.025 - 10.5) / 0.5, 10);
    expect(level.pivots.map((p) => p.index)).toEqual([80, 90]);
    expect(level.lastTouchAt).toBe(iso(90));
  });
});

describe("market-structure · estructura de tendencia", () => {
  const p = (index: number, price: number, type: MarketPivotTypeV1) =>
    pivot(index, price, type);

  it("máximos y mínimos crecientes ⇒ estructura ascendente", () => {
    const structure = describeMarketStructure({
      highs: [p(1, 10, "high"), p(2, 11, "high"), p(3, 12, "high")],
      lows: [p(1, 9, "low"), p(2, 9.5, "low"), p(3, 10, "low")],
      atrRef: 0.5,
    });
    expect(structure.id).toBe("ascendente");
    expect(structure.tolerance).toBeCloseTo(
      0.5 * MARKET_STRUCTURE_DEFAULTS.structureToleranceAtr,
      10,
    );
  });

  it("máximos y mínimos decrecientes ⇒ estructura descendente", () => {
    const structure = describeMarketStructure({
      highs: [p(1, 12, "high"), p(2, 11, "high"), p(3, 10, "high")],
      lows: [p(1, 10, "low"), p(2, 9.5, "low"), p(3, 9, "low")],
      atrRef: 0.5,
    });
    expect(structure.id).toBe("descendente");
  });

  it("extremos dentro de tolerancia ⇒ estructura en rango (no «Lateral»)", () => {
    const structure = describeMarketStructure({
      highs: [p(1, 10, "high"), p(2, 10.05, "high"), p(3, 10.1, "high")],
      lows: [p(1, 9, "low"), p(2, 9.05, "low"), p(3, 9.1, "low")],
      atrRef: 0.5,
    });
    expect(structure.id).toBe("en_rango");
  });

  it("señales contradictorias ⇒ sin estructura", () => {
    const structure = describeMarketStructure({
      highs: [p(1, 10, "high"), p(2, 11, "high"), p(3, 12, "high")],
      lows: [p(1, 10, "low"), p(2, 9.5, "low"), p(3, 9, "low")],
      atrRef: 0.5,
    });
    expect(structure.id).toBe("sin_estructura");
  });

  it("menos de tres pivotes por lado ⇒ sin estructura", () => {
    const structure = describeMarketStructure({
      highs: [p(1, 10, "high"), p(2, 11, "high")],
      lows: [p(1, 9, "low"), p(2, 9.5, "low")],
      atrRef: 0.5,
    });
    expect(structure.id).toBe("sin_estructura");
  });
});

describe("market-structure · resultado completo", () => {
  it("sin velas declara el hueco y no inventa niveles", () => {
    const result = computeMarketStructure({ bars: [] });
    expect(result.status).toBe("no_disponible");
    expect(result.reasons).toEqual(["sin_velas"]);
    expect(marketStructureLevels(result)).toEqual([]);
  });

  it("por debajo del mínimo declara histórico insuficiente", () => {
    const bars = twoTouchFixture().slice(0, 79);
    const result = computeMarketStructure({ bars });
    expect(result.status).toBe("insufficient_history");
    expect(result.reasons).toEqual(["historico_insuficiente"]);
    expect(result.window.bars).toBe(79);
    expect(marketStructureLevels(result)).toEqual([]);
  });

  it("con el mínimo exacto ya calcula", () => {
    const bars = twoTouchFixture().slice(0, 80);
    const result = computeMarketStructure({ bars });
    expect(result.status).not.toBe("insufficient_history");
    expect(result.window.bars).toBe(80);
  });

  it("una barra inválida invalida el cálculo en vez de recortarse en silencio", () => {
    const bars = twoTouchFixture();
    bars[5] = { ...bars[5]!, high: 1, low: 9 };
    const result = computeMarketStructure({ bars });
    expect(result.status).toBe("no_disponible");
    expect(result.reasons).toEqual(["velas_invalidas"]);
  });

  it("una serie plana no tiene pivotes y lo declara", () => {
    const bars = Array.from({ length: 100 }, (_, i) => bar(i, 10, 9, 9.5));
    const result = computeMarketStructure({ bars });
    expect(result.status).toBe("no_disponible");
    expect(result.reasons).toEqual(["sin_pivotes"]);
    expect(result.atrRef).toBeCloseTo(1, 10);
  });

  it("detecta soporte y resistencia con varios toques y los marca dibujables", () => {
    const result = computeMarketStructure({ bars: twoTouchFixture() });
    expect(result.status).toBe("ok");
    expect(result.supports.length).toBeGreaterThan(0);
    expect(result.resistances.length).toBeGreaterThan(0);
    const drawable = marketStructureLevels(result).filter(marketLevelIsDrawable);
    expect(drawable.length).toBeGreaterThanOrEqual(2);
    for (const level of drawable) {
      expect(level.state).toBe("detectado");
      expect(level.touches).toBeGreaterThanOrEqual(2);
    }
  });

  it("nunca conserva más de tres niveles por lado", () => {
    const result = computeMarketStructure({
      bars: twoTouchFixture(),
      params: { maxLevelsPerSide: 1 },
    });
    expect(result.supports.length).toBeLessThanOrEqual(1);
    expect(result.resistances.length).toBeLessThanOrEqual(1);
  });

  it("absorbe el nivel débil dentro de la tolerancia y lo declara", () => {
    const bars = zigzag(
      [11.5, 10.0, 11.8, 10.3, 11.5, 10.3, 11.8, 11.0],
      12,
    );
    const result = computeMarketStructure({
      bars,
      params: { absorbAtrMultiple: 2 },
    });
    const absorbedSupports = result.supports.filter((level) =>
      level.reasons.includes("absorbido_por_nivel_mas_fuerte"),
    );
    expect(absorbedSupports).toHaveLength(1);
    expect(absorbedSupports[0]!.state).toBe("no_fiable");
    expect(absorbedSupports[0]!.touches).toBe(1);
    const survivor = result.supports.find(
      (level) => !level.reasons.includes("absorbido_por_nivel_mas_fuerte"),
    );
    expect(survivor?.touches).toBeGreaterThanOrEqual(2);
  });

  it("declara método, versión, parámetros y ventana", () => {
    const result = computeMarketStructure({
      bars: twoTouchFixture(),
      timeframe: "1d",
    });
    expect(result.methodId).toBe(MARKET_STRUCTURE_METHOD_ID);
    expect(result.methodVersion).toBe(1);
    expect(result.params).toEqual({ ...MARKET_STRUCTURE_DEFAULTS });
    expect(result.window.timeframe).toBe("1d");
    expect(result.window.from).toBe(iso(0));
    expect(result.window.bars).toBe(81);
  });

  it("la firma es estable con el mismo input y cambia con otra ventana", () => {
    const bars = twoTouchFixture();
    const a = computeMarketStructure({ bars, timeframe: "1d" });
    const b = computeMarketStructure({ bars, timeframe: "1d" });
    expect(a.inputSignature).toBe(b.inputSignature);

    const longer = computeMarketStructure({
      bars: [...bars, bar(bars.length, 10.9, 10.6, 10.75)],
      timeframe: "1d",
    });
    expect(longer.inputSignature).not.toBe(a.inputSignature);
  });

  it("no muta las velas de entrada", () => {
    const bars = twoTouchFixture();
    const before = JSON.stringify(bars);
    computeMarketStructure({ bars });
    expect(JSON.stringify(bars)).toBe(before);
  });

  it("normaliza el orden temporal antes de calcular", () => {
    const bars = twoTouchFixture();
    const reversed = [...bars].reverse();
    const ordered = computeMarketStructure({ bars });
    const normalized = computeMarketStructure({ bars: reversed });
    expect(normalized.window.from).toBe(ordered.window.from);
    expect(normalized.window.to).toBe(ordered.window.to);
    expect(normalized.close).toBe(ordered.close);
    expect(normalized.status).toBe(ordered.status);
    expect(normalized.inputSignature).toBe(ordered.inputSignature);
    expect(normalized.supports.map((level) => level.price)).toEqual(
      ordered.supports.map((level) => level.price),
    );
  });
});
