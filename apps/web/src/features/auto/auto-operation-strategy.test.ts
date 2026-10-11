/**
 * Puente operación → estrategia ganadora (P3/P4): composición pura y fail-closed.
 *
 * Se comprueba que la cadena estrategia → indicadores → razón se copia del TOP sin recalcular,
 * que el emparejamiento con la clave EXACTA del ciclo (`presetKey`) es una igualdad honesta
 * (nunca «coincide» sin igualdad exacta) y que un hueco se declara («Sin dato todavía») en vez de
 * fabricar una estrategia.
 */

import { describe, expect, it } from "vitest";
import type {
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
} from "@bolsa/shared";
import {
  AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL,
  AUTO_OPERATION_STRATEGY_DECLARED_LABEL,
  AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT,
  AUTO_OPERATION_STRATEGY_NO_DATA,
  buildAutoOperationStrategyView,
  resolveAutoOperationStrategyMatch,
} from "@/features/auto/auto-operation-strategy";
import { ABSENT_DATA_NOT_AVAILABLE } from "@/components/absent-data";

function slot(
  partial: Partial<InstrumentStrategyTopSlotV1> = {},
): InstrumentStrategyTopSlotV1 {
  return {
    rank: 1,
    label: "SMA cross",
    stars: 3,
    score: 70,
    source: "coach",
    strategyDefinitionId: "def-1",
    strategyType: "sma_crossover",
    ...partial,
  };
}

function top(
  partial: Partial<InstrumentStrategyTopV1> = {},
): InstrumentStrategyTopV1 {
  return {
    id: "top-1",
    instrumentId: "uuid-1",
    timeframe: "1d",
    status: "active",
    version: 1,
    evidenceLevel: "lab_validated",
    slots: [slot()],
    coachFacts: {
      recommendations: [{ rank: 1, reasons: ["Estrellas 3/5", "DD -12%"] }],
    },
    createdAt: "2026-10-01T00:00:00Z",
    updatedAt: "2026-10-01T00:00:00Z",
    ...partial,
  };
}

const definition = {
  indicatorSpecs: [{ definitionId: "rsi", parameters: { period: 14 } }],
  presetKey: "sma_crossover" as const,
};

describe("buildAutoOperationStrategyView", () => {
  it("compone la cadena estrategia → indicadores → razón desde el TOP ya producido", () => {
    const view = buildAutoOperationStrategyView({
      cycle: {
        instrumentId: "AAPL",
        strategyPresetKey: "sma_crossover",
        strategyVersion: "sv-1",
      },
      instrumentId: "uuid-1",
      top: top(),
      definition,
    });
    expect(view).not.toBeNull();
    expect(view?.symbol).toBe("AAPL");
    expect(view?.instrumentId).toBe("uuid-1");
    expect(view?.strategyDefinitionId).toBe("def-1");
    expect(view?.strategyLabel).toBe("SMA cross");
    expect(view?.rank).toBe(1);
    expect(view?.indicators).toEqual(["RSI"]);
    expect(view?.reasons).toEqual(["Estrellas 3/5", "DD -12%"]);
    expect(view?.match).toBe("same");
    // La clave EXACTA y el sello opaco se copian por separado, tal cual los declara el ciclo.
    expect(view?.declaredCyclePresetKey).toBe("sma_crossover");
    expect(view?.declaredCycleStrategyVersion).toBe("sv-1");
    expect(view?.gapReason).toBeNull();
    expect(view?.verifyHref).toContain("/backtests?");
    expect(view?.verifyHref).toContain("instrumentId=uuid-1");
  });

  it("sin ciclo no hay vista (nada que enlazar)", () => {
    expect(
      buildAutoOperationStrategyView({
        cycle: null,
        instrumentId: "uuid-1",
        top: top(),
        definition,
      }),
    ).toBeNull();
  });

  it("sin UUID resuelto declara el hueco y no ofrece verificación", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL", strategyVersion: "sv-1" },
      instrumentId: null,
      top: null,
      definition: null,
    });
    expect(view?.instrumentId).toBeNull();
    expect(view?.strategyDefinitionId).toBeNull();
    expect(view?.indicators).toEqual([]);
    expect(view?.verifyHref).toBeNull();
    expect(view?.gapReason).toContain("no se pudo resolver el instrumento");
  });

  it("con lectura EN VUELO no declara ausencia (hueco transitorio = carga)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL", strategyVersion: "sv-1" },
      instrumentId: null,
      top: null,
      definition: null,
      loading: true,
    });
    expect(view?.loading).toBe(true);
    // El hueco es transitorio: NO se declara «Sin dato todavía».
    expect(view?.gapReason).toBeNull();
    // Sigue fail-closed: sin instrumento no hay verificación ofrecida.
    expect(view?.verifyHref).toBeNull();
  });

  it("un FALLO declarado manda sobre la carga (sigue «No disponible»)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: "uuid-1",
      top: null,
      topError: true,
      definition: null,
      loading: true,
    });
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
  });

  it("sin TOP declara el hueco (no fabrica estrategia)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: "uuid-1",
      top: null,
      definition: null,
    });
    expect(view?.strategyDefinitionId).toBeNull();
    expect(view?.strategyLabel).toBe(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.verifyHref).toBeNull();
    expect(view?.gapReason).toContain("no hay Finalistas");
  });

  it("un #1 sin definición guardada declara el hueco", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: "uuid-1",
      top: top({ slots: [slot({ strategyDefinitionId: null })] }),
      definition: null,
    });
    expect(view?.strategyDefinitionId).toBeNull();
    expect(view?.verifyHref).toBeNull();
    expect(view?.gapReason).toContain("no tiene definición guardada");
  });

  it("un FALLO de lectura del TOP declara «No disponible» (no una ausencia) y cierra el CTA", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: "uuid-1",
      top: null,
      topError: true,
      definition: null,
    });
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).toContain("no se pudo leer el TOP de Finalistas");
    // No se describe como ausencia ni se colapsa a 0.
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.verifyHref).toBeNull();
  });

  it("un FALLO de lectura de la definición declara «No disponible» y cierra el CTA", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL", strategyVersion: "sma_crossover" },
      instrumentId: "uuid-1",
      top: top(),
      definitionError: true,
      definition: null,
    });
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).toContain(
      "no se pudo leer la definición de la estrategia #1",
    );
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    // Aunque el #1 tenga `strategyDefinitionId`, sin su definición fiable no se verifica.
    expect(view?.verifyHref).toBeNull();
  });

  it("un TOP nulo EXITOSO sigue siendo «Sin dato todavía» (no un error)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: "uuid-1",
      top: null,
      topError: false,
      definition: null,
    });
    expect(view?.gapReason).toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.gapReason).toContain("no hay Finalistas");
    expect(view?.gapReason).not.toContain(ABSENT_DATA_NOT_AVAILABLE);
  });

  it("un FALLO del catálogo de instrumentos declara «No disponible» (no una ausencia) y cierra el CTA", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: null,
      top: null,
      instrumentError: true,
      definition: null,
    });
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).toContain("no se pudo leer el catálogo");
    // No se describe como ausencia ni se colapsa a un hueco de instrumento.
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.verifyHref).toBeNull();
  });

  it("un FALLO del catálogo manda aunque el UUID esté resuelto: «No disponible», sin verificación", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL", strategyVersion: "sma_crossover" },
      instrumentId: "uuid-1",
      top: top(),
      instrumentError: true,
      definition,
    });
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).toContain("no se pudo leer el catálogo");
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.verifyHref).toBeNull();
  });

  it("un FALLO del catálogo manda sobre la carga (sigue «No disponible», no carga)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: null,
      top: null,
      instrumentError: true,
      definition: null,
      loading: true,
    });
    expect(view?.gapReason).not.toBeNull();
    expect(view?.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
    expect(view?.gapReason).not.toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
    expect(view?.verifyHref).toBeNull();
  });

  it("un ciclo SELECCIONADO sin instrumentId declara el hueco y no oculta la tarjeta", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: null, strategyVersion: "sv-1" },
      instrumentId: null,
      top: null,
      definition: null,
    });
    // El ciclo EXISTE ⇒ siempre hay vista (la tarjeta no desaparece silenciosamente).
    expect(view).not.toBeNull();
    expect(view?.gapReason).toContain(
      "no se pudo resolver el instrumento de la operación",
    );
    expect(view?.verifyHref).toBeNull();
  });

  it("fallback a preset cuando no hay definición (indicadores por strategyType)", () => {
    const view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL", strategyVersion: "sma_crossover" },
      instrumentId: "uuid-1",
      top: top(),
      definition: null,
    });
    expect(view?.indicators.length).toBeGreaterThan(0);
  });
});

describe("resolveAutoOperationStrategyMatch", () => {
  it("declara coincidencia SOLO con igualdad EXACTA de la clave declarada", () => {
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", slot(), definition),
    ).toBe("same");
  });

  it("empareja por el `strategyType` que declara el #1", () => {
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", slot(), null),
    ).toBe("same");
  });

  it("empareja por el `presetKey` que declara la definición del #1", () => {
    const sinTipo = slot({ strategyType: null });
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", sinTipo, definition),
    ).toBe("same");
  });

  it("declara divergencia cuando la clave declarada no es igual (contenido distinto)", () => {
    expect(
      resolveAutoOperationStrategyMatch("trend_v3", slot(), definition),
    ).toBe("differs");
  });

  it("NO empareja por contención ni por etiqueta: solo identidad EXACTA", () => {
    // Antes «SMA cross» (etiqueta) emparejaba por token; ahora NO: solo la clave exacta.
    expect(
      resolveAutoOperationStrategyMatch("SMA cross", slot(), definition),
    ).toBe("differs");
    // «sma» ⊂ «sma_crossover»: sin contención, no coincide.
    expect(resolveAutoOperationStrategyMatch("sma", slot(), definition)).toBe(
      "differs",
    );
  });

  it("sin clave declarada, clave en blanco o sin #1 ⇒ «sin dato» (no se inventa)", () => {
    expect(resolveAutoOperationStrategyMatch(null, slot(), definition)).toBe(
      "unknown",
    );
    expect(
      resolveAutoOperationStrategyMatch(undefined, slot(), definition),
    ).toBe("unknown");
    expect(resolveAutoOperationStrategyMatch("   ", slot(), definition)).toBe(
      "unknown",
    );
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", null, definition),
    ).toBe("unknown");
  });

  it("#1 SIN identidad declarada ⇒ «sin dato», NUNCA «difiere» (no se afirma sin término)", () => {
    // `strategyType` y `presetKey` son opcionales: el #1 puede no declarar NINGUNA identidad.
    const sinIdentidad = slot({ strategyType: null });
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", sinIdentidad, null),
    ).toBe("unknown");
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", sinIdentidad),
    ).toBe("unknown");
    // Una definición sin `presetKey` tampoco aporta identidad: sigue siendo hueco, no divergencia.
    expect(
      resolveAutoOperationStrategyMatch("sma_crossover", sinIdentidad, {}),
    ).toBe("unknown");
  });

  it("recorta los espacios de la clave declarada y de las identidades antes de comparar", () => {
    expect(
      resolveAutoOperationStrategyMatch(
        "  sma_crossover  ",
        slot(),
        definition,
      ),
    ).toBe("same");
  });
});

describe("copy de identidad (separación mejor-disponible vs ejecutada)", () => {
  it("nombra los dos bloques de forma INEQUÍVOCA", () => {
    // (a) Mejor DISPONIBLE del valor = TOP #1 de Finalistas.
    expect(AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL).toContain(
      "Mejor estrategia del valor",
    );
    expect(AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL).toContain(
      "Finalistas",
    );
    // (b) EJECUTADA declarada por el ciclo (identidad publicada por el motor).
    expect(AUTO_OPERATION_STRATEGY_DECLARED_LABEL).toContain("ejecutada");
    expect(AUTO_OPERATION_STRATEGY_DECLARED_LABEL).toContain("ciclo");
    // Son rótulos DISTINTOS: no se pueden confundir en la superficie.
    expect(AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL).not.toBe(
      AUTO_OPERATION_STRATEGY_DECLARED_LABEL,
    );
  });

  it("declara la identidad EXACTA (`presetKey`) y la ausencia honesta del dato", () => {
    expect(AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT).toContain(
      "identidad EXACTA",
    );
    expect(AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT).toContain("presetKey");
    // Cuando el ciclo no declara su clave, se rotula la ausencia y no se afirma coincidencia.
    expect(AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT).toContain(
      "Sin dato todavía",
    );
    expect(AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT).not.toContain("Coincide");
  });
});
