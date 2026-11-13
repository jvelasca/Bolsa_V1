import { describe, expect, it } from "vitest";
import {
  INSTRUMENT_DAILY_OPINION_REASON_CODES,
  INSTRUMENT_DAILY_OPINION_STANCES,
} from "./instrument-daily-opinion.js";
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  MARKET_LEVEL_KIND_LABELS,
  MARKET_LEVEL_KIND_SHORT_LABELS,
  MARKET_LEVEL_REASONS,
  MARKET_LEVEL_REASON_LABELS,
  MARKET_LEVEL_STATES,
  MARKET_LEVEL_STATE_LABELS,
  MARKET_REASON_LABELS,
  MARKET_STANCE_DEFINITIONS,
  MARKET_STRUCTURE_TREND_IDS,
  MARKET_STRUCTURE_TREND_LABELS,
  MARKET_TREND_DEFINITIONS,
  MARKET_VOCABULARY_RETIRED_TERMS,
  THERMOMETER_NEAR_ENTRY_PCT,
  THERMOMETER_SOURCE,
  THERMOMETER_STATES,
  formatConfidence,
  formatDictamenStars,
  formatDistanceToEntry,
  formatEntryAbove,
  formatInvalidationBelow,
  formatLevel,
  marketLevelReasonLabel,
  marketLevelStateLabel,
  marketStanceLabel,
  marketStructureTrendLabel,
  marketTrendLabel,
  marketTrendTone,
  resolveThermometer,
  visibleLevelReasons,
  visibleReasons,
} from "./market-vocabulary.js";

/** Clave interna: minúsculas con guion bajo (`gate_veto`, `hold_watch`). */
const INTERNAL_KEY = /^[a-z]+(_[a-z]+)+$/;

describe("market-vocabulary · las 7 recomendaciones", () => {
  it("cada postura del motor tiene denominación visible y familia", () => {
    for (const stance of INSTRUMENT_DAILY_OPINION_STANCES) {
      const definition = MARKET_STANCE_DEFINITIONS[stance];
      expect(definition, stance).toBeTruthy();
      expect(definition.stance).toBe(stance);
      expect(definition.label.length).toBeGreaterThan(0);
      expect(INSTRUMENT_DAILY_OPINION_STANCE_LABELS[stance]).toBe(
        definition.label,
      );
      expect(["alcista", "neutral", "bajista", "sin_senal"]).toContain(
        definition.family,
      );
    }
  });

  it("ninguna etiqueta es la clave interna ni contiene snake_case", () => {
    for (const stance of INSTRUMENT_DAILY_OPINION_STANCES) {
      const label = INSTRUMENT_DAILY_OPINION_STANCE_LABELS[stance];
      expect(label).not.toBe(stance);
      expect(label).not.toMatch(INTERNAL_KEY);
    }
  });

  it("la tabla cerrada es exactamente la aprobada", () => {
    expect(INSTRUMENT_DAILY_OPINION_STANCE_LABELS).toEqual({
      buy: "Comprar",
      hold_watch: "Mantener",
      overbought: "Sin respaldo",
      reduce: "Reducir",
      sell_exit: "Vender",
      no_trade: "No operar",
      review_strategy: "Revisar estrategia",
    });
  });

  it("«Vigilar» no vuelve como postura", () => {
    const labels = Object.values(INSTRUMENT_DAILY_OPINION_STANCE_LABELS);
    expect(labels).not.toContain("Vigilar");
  });

  it("overbought significa «sin respaldo», nunca sobrecompra", () => {
    const definition = MARKET_STANCE_DEFINITIONS.overbought;
    expect(definition.label).toBe("Sin respaldo");
    // La justificación visible no usa el término; el significado solo lo desmiente.
    expect(definition.label.toLowerCase()).not.toContain("sobrecompra");
    expect(
      MARKET_REASON_LABELS.overbought_or_exit.toLowerCase(),
    ).not.toContain("sobrecompra");
    expect(definition.meaning.toLowerCase()).toContain("no es sobrecompra");
  });

  it("Comprar exige el respaldo del Lab, no solo las ★ del dictamen", () => {
    const definition = MARKET_STANCE_DEFINITIONS.buy;
    expect(definition.trigger.toLowerCase()).toContain("lab");
    expect(definition.meaning.toLowerCase()).toContain("no es una orden");
  });

  it("hold_watch se llama «Mantener» y declara el matiz con/sin posición", () => {
    const definition = MARKET_STANCE_DEFINITIONS.hold_watch;
    expect(definition.label).toBe("Mantener");
    expect(definition.meaning).toMatch(/posición/i);
  });

  it("review_strategy revisa la estrategia del Lab, no la tesis", () => {
    const definition = MARKET_STANCE_DEFINITIONS.review_strategy;
    expect(definition.label).toBe("Revisar estrategia");
    expect(definition.meaning).toContain("tesis");
    expect(definition.meaning).toContain("no");
  });
});

describe("market-vocabulary · no_trade por causa", () => {
  it("cartera sin medir → No evaluable, jamás «sin posición» ni «No operar»", () => {
    const result = marketStanceLabel({
      stance: "no_trade",
      reasons: ["position_unmeasured"],
    });
    expect(result.label).toBe("No evaluable");
    expect(result.detail).toBe("Cartera sin medir");
    expect(result.label).not.toBe("No operar");
    expect(`${result.label} ${result.detail}`.toLowerCase()).not.toContain(
      "sin posición",
    );
  });

  it("«No evaluable» gana a «No operar» cuando conviven causas", () => {
    const result = marketStanceLabel({
      stance: "no_trade",
      reasons: ["eod_data_stale", "position_unmeasured"],
    });
    expect(result.label).toBe("No evaluable");
  });

  it("sin cierre de sesión y distress sí son «No operar»", () => {
    expect(
      marketStanceLabel({ stance: "no_trade", reasons: ["eod_data_stale"] })
        .label,
    ).toBe("No operar");
    expect(
      marketStanceLabel({ stance: "no_trade", reasons: ["fa_distress"] }),
    ).toMatchObject({ label: "No operar", detail: "Alerta fundamental" });
  });

  it("gate_veto queda en diagnóstico y no se pinta como postura", () => {
    const result = marketStanceLabel({
      stance: "no_trade",
      reasons: ["gate_veto"],
    });
    expect(result.diagnosticOnly).toBe(true);
    expect(result.label).toBe("Operativa bloqueada");
  });

  it("position_closed no afirma «sin posición»", () => {
    const result = marketStanceLabel({
      stance: "no_trade",
      reasons: ["position_closed"],
    });
    expect(result.label).toBe("No evaluable");
  });

  it("una postura distinta de no_trade no se afina por causa", () => {
    const result = marketStanceLabel({
      stance: "buy",
      reasons: ["strong_buy_signal", "position_unmeasured"],
    });
    expect(result).toMatchObject({
      label: "Comprar",
      detail: null,
      diagnosticOnly: false,
    });
  });
});

describe("market-vocabulary · los 19 motivos", () => {
  it("todo código del contrato tiene etiqueta legible", () => {
    for (const reason of INSTRUMENT_DAILY_OPINION_REASON_CODES) {
      const label = MARKET_REASON_LABELS[reason];
      expect(label, reason).toBeTruthy();
      expect(label).not.toBe(reason);
      expect(label).not.toMatch(INTERNAL_KEY);
    }
  });

  it("gate_veto nunca entra en la lista visible", () => {
    const result = visibleReasons(["gate_veto", "io_low"]);
    expect(result.visible).toEqual(["Calidad de señal baja"]);
    expect(result.visible.join(" ")).not.toContain("gate_veto");
  });

  it("io_medium se calla con señal alta o sin medir", () => {
    expect(
      visibleReasons(["io_medium"], { ioScore: 85 }).visible,
    ).toEqual([]);
    expect(
      visibleReasons(["io_medium"], { ioScore: null }).visible,
    ).toEqual([]);
    expect(
      visibleReasons(["io_medium"], { ioScore: 55 }).visible,
    ).toEqual(["Calidad de señal sin señal de compra"]);
  });

  it("position_open no repite lo que ya dice holding_position", () => {
    const result = visibleReasons(["position_open", "holding_position"]);
    expect(result.visible).toEqual(["Posición abierta: se mantiene"]);
  });

  it("máximo 3 visibles, el resto al tooltip", () => {
    const result = visibleReasons(
      ["strong_buy_signal", "top_high", "io_high", "top_medium"],
      { ioScore: 85 },
    );
    expect(result.visible).toHaveLength(3);
    expect(result.hidden).toEqual(["Estrategia del Lab con respaldo suficiente"]);
    expect(result.hiddenCount).toBe(1);
  });

  it("no duplica etiquetas repetidas", () => {
    const result = visibleReasons(["io_low", "io_low"]);
    expect(result.visible).toEqual(["Calidad de señal baja"]);
  });
});

describe("market-vocabulary · tendencia", () => {
  it("Lateral es rango y Mixta es desacuerdo de medias", () => {
    expect(marketTrendTone("weak")).toBe("range");
    expect(marketTrendTone("mixed")).toBe("mixed");
    expect(marketTrendLabel({ value: "weak" })).toBe("Lateral");
    expect(marketTrendLabel({ value: "mixed" })).toBe("Mixta");
    expect(marketTrendTone("mixed")).not.toBe("range");
    expect(MARKET_TREND_DEFINITIONS.mixed?.basis).toContain("No implica rango");
  });

  it("Neutra no es rango ni mixta", () => {
    expect(marketTrendTone("neutral")).toBe("neutral");
    expect(marketTrendLabel({ value: "neutral" })).toBe("Neutra");
  });

  it("el display del parte manda sobre la tabla", () => {
    expect(
      marketTrendLabel({ value: "weak", display: "Neutra / rango" }),
    ).toBe("Neutra / rango");
  });

  it("un valor desconocido declara el hueco, no se pinta en crudo", () => {
    expect(marketTrendLabel({ value: "weird_internal_value" })).toBe(
      "Sin dato de tendencia",
    );
    expect(marketTrendTone("weird_internal_value")).toBe("unknown");
  });
});

describe("market-vocabulary · termómetro (display)", () => {
  it("declara sus estados y su precedencia sin huecos", () => {
    expect(THERMOMETER_STATES.map((s) => s.label)).toEqual([
      "Sin entrada",
      "Extendido",
      "Caliente",
      "Templado",
      "Frío",
    ]);
    expect(THERMOMETER_STATES.map((s) => s.precedence)).toEqual([
      0, 1, 2, 3, 4,
    ]);
  });

  it("sin entrada o sin precio no inventa temperatura", () => {
    expect(
      resolveThermometer({ markPrice: 10, entry: null }).state,
    ).toBe("sin_entrada");
    expect(
      resolveThermometer({ markPrice: null, entry: 10 }).state,
    ).toBe("sin_entrada");
  });

  it("por encima de la entrada es caliente; en la banda es templado", () => {
    expect(resolveThermometer({ markPrice: 10.01, entry: 10 }).state).toBe(
      "caliente",
    );
    expect(resolveThermometer({ markPrice: 9.8, entry: 10 }).state).toBe(
      "templado",
    );
    expect(resolveThermometer({ markPrice: 9.5, entry: 10 }).state).toBe("frio");
  });

  it("en o por encima del Objetivo 1 es extendido (precedencia sobre caliente)", () => {
    expect(
      resolveThermometer({ markPrice: 12, entry: 10, target1: 11.5 }).state,
    ).toBe("extendido");
  });

  it("por debajo de la invalidación se declara, no se cambia de estado", () => {
    const result = resolveThermometer({
      markPrice: 9,
      entry: 10,
      invalidacion: 9.2,
    });
    expect(result.state).toBe("frio");
    expect(result.detail).toContain("invalidación");
  });

  it("siempre se declara como display y nunca como orden", () => {
    const result = resolveThermometer({ markPrice: 10, entry: 10 });
    expect(result.source).toBe(THERMOMETER_SOURCE);
    expect(result.detail?.toLowerCase() ?? "").not.toContain("orden");
    expect(THERMOMETER_NEAR_ENTRY_PCT).toBe(3);
  });
});

describe("market-vocabulary · formateadores", () => {
  it("formatea niveles en es-ES y declara la ausencia", () => {
    expect(formatLevel(9.7)).toBe("9,70");
    expect(formatLevel(null)).toBe("Sin nivel medido");
    expect(formatEntryAbove(9.72)).toBe("Comprar por encima de 9,72");
    expect(formatEntryAbove(null)).toBe("Sin entrada publicada");
    expect(formatInvalidationBelow(9.38)).toBe("Vender por debajo de 9,38");
  });

  it("la distancia a la entrada dice el sentido, no un signo suelto", () => {
    expect(formatDistanceToEntry(-3.5)).toBe(
      "un 3,5 % por debajo de la entrada",
    );
    expect(formatDistanceToEntry(1.2)).toBe(
      "un 1,2 % por encima de la entrada",
    );
    expect(formatDistanceToEntry(0)).toBe("en la entrada");
    expect(formatDistanceToEntry(null)).toBe("sin distancia medida");
  });

  it("un IO sin medir no se pinta como cero", () => {
    expect(formatConfidence(68)).toBe("68 / 100");
    expect(formatConfidence(null)).toBe("Sin medir");
  });

  it("unas ★ sin medir no se pintan como un 3 fabricado", () => {
    expect(formatDictamenStars(4)).toBe("★★★★☆");
    expect(formatDictamenStars(null)).toBe("Sin medir");
    expect(formatDictamenStars(undefined)).toBe("Sin medir");
  });

  it("los términos retirados quedan declarados para la guarda", () => {
    expect(MARKET_VOCABULARY_RETIRED_TERMS).toContain("Postura sugerida hoy");
    expect(MARKET_VOCABULARY_RETIRED_TERMS).toContain("Sobrecomprado");
    expect(MARKET_VOCABULARY_RETIRED_TERMS).toContain("Thaw");
  });
});

describe("market-vocabulary · niveles calculados y estructura (S2)", () => {
  it("todo estado de nivel tiene etiqueta visible y ninguna es una clave interna", () => {
    for (const state of MARKET_LEVEL_STATES) {
      const label = MARKET_LEVEL_STATE_LABELS[state];
      expect(label, state).toBeTruthy();
      expect(label).not.toMatch(INTERNAL_KEY);
      expect(marketLevelStateLabel(state)).toBe(label);
    }
  });

  it("todo motivo de nivel se traduce y un código desconocido devuelve null", () => {
    for (const reason of MARKET_LEVEL_REASONS) {
      const label = MARKET_LEVEL_REASON_LABELS[reason];
      expect(label, reason).toBeTruthy();
      expect(label).not.toMatch(INTERNAL_KEY);
    }
    expect(marketLevelReasonLabel("motivo_inventado")).toBeNull();
    expect(marketLevelStateLabel("estado_inventado")).toBeNull();
  });

  it("los niveles calculados no se confunden con los presets manuales", () => {
    expect(MARKET_LEVEL_KIND_LABELS.support).toBe("Soporte calculado");
    expect(MARKET_LEVEL_KIND_LABELS.resistance).toBe("Resistencia calculada");
    expect(MARKET_LEVEL_KIND_SHORT_LABELS.support).toBe("S·calc");
    expect(MARKET_LEVEL_KIND_SHORT_LABELS.resistance).toBe("R·calc");
    for (const label of Object.values(MARKET_LEVEL_KIND_LABELS)) {
      expect(label).not.toBe("Soporte");
      expect(label).not.toBe("Resistencia");
    }
  });

  it("la estructura de pivotes usa su propio vocabulario, jamás «Lateral»", () => {
    for (const id of MARKET_STRUCTURE_TREND_IDS) {
      const label = MARKET_STRUCTURE_TREND_LABELS[id];
      expect(label, id).toBeTruthy();
      expect(label.toLowerCase()).not.toContain("lateral");
      expect(label).not.toMatch(INTERNAL_KEY);
    }
    expect(marketStructureTrendLabel("en_rango")).toBe("Estructura en rango");
    expect(marketStructureTrendLabel("otro")).toBeNull();
    expect(marketStructureTrendLabel(null)).toBeNull();
  });

  it("visibleLevelReasons traduce, deduplica y no pinta códigos crudos", () => {
    const result = visibleLevelReasons(
      ["un_solo_toque", "un_solo_toque", "motivo_inventado", "nivel_roto"],
      { maxVisible: 1 },
    );
    expect(result.visible).toEqual(["Un solo toque"]);
    expect(result.hidden).toEqual(["Nivel roto por el precio"]);
    expect(result.hiddenCount).toBe(1);
  });
});
