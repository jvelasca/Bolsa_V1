/**
 * Puente operación → estrategia ganadora (P3/P4): composición pura y fail-closed.
 *
 * Se comprueba que la cadena estrategia → indicadores → razón se copia del TOP sin recalcular,
 * que el emparejamiento con el sello del ciclo es honesto (nunca «coincide» sin match real) y que
 * un hueco se declara («Sin dato todavía») en vez de fabricar una estrategia.
 */

import { describe, expect, it } from "vitest";
import type {
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
} from "@bolsa/shared";
import {
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
      cycle: { instrumentId: "AAPL", strategyVersion: "sma_crossover" },
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
  it("coincide por id, etiqueta o tipo (normalizado)", () => {
    expect(resolveAutoOperationStrategyMatch("def-1", slot())).toBe("same");
    expect(resolveAutoOperationStrategyMatch("SMA cross", slot())).toBe("same");
    expect(resolveAutoOperationStrategyMatch("sma_crossover", slot())).toBe(
      "same",
    );
  });

  it("declara divergencia cuando el sello no empareja con la identidad del #1", () => {
    expect(resolveAutoOperationStrategyMatch("trend-v3", slot())).toBe(
      "differs",
    );
  });

  it("no confunde por contención: «ma» NO coincide con «smacrossover»", () => {
    const smac = slot({
      strategyDefinitionId: "smacrossover",
      label: "smacrossover",
      strategyType: "smacrossover",
    });
    // Token completo: «ma» ≠ «smacrossover» (antes habría dado un falso «same»).
    expect(resolveAutoOperationStrategyMatch("ma", smac)).toBe("differs");
  });

  it("sin sello, sin #1 o sello trivial ⇒ «sin dato» (no se inventa)", () => {
    expect(resolveAutoOperationStrategyMatch(null, slot())).toBe("unknown");
    expect(resolveAutoOperationStrategyMatch("1", slot())).toBe("unknown");
    expect(resolveAutoOperationStrategyMatch("sv-1", null)).toBe("unknown");
  });
});
