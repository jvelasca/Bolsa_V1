/**
 * B-5 / O-6 — read-model de las declaraciones de HOLD con su procedencia.
 *
 * Lo que se fija aquí es la regla de honestidad: la causa se clasifica con el vocabulario
 * cerrado, sólo las claves conocidas suben al primer nivel, un valor o una medición ausente no
 * se rellenan, la fecha de la barra no se desplaza de día y el alcance temporal es explícito.
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_HOLD_PROVENANCE_LABELS,
  AUTO_HOLD_PROVENANCE_ABSENT,
  AUTO_HOLD_REASON_ABSENT,
  autoHoldReasonLabel,
  autoHoldSymbolLabel,
  buildAutoHoldDeclarations,
  describeGatedState,
  formatHoldBarDay,
  formatHoldInstant,
} from "@/features/auto/auto-hold-declarations";

function fact(key: string, value: unknown, measurement = "COMPLETE") {
  return { key, value, measurement };
}

describe("formatHoldInstant", () => {
  it("presenta el sello en formato legible es-ES", () => {
    const label = formatHoldInstant("2026-09-30T00:00:00Z");
    expect(label).toBeTruthy();
    expect(label).toContain("2026");
    expect(label).not.toContain("T00:00:00");
  });

  it("conserva el sello original si no es parseable en lugar de inventar una fecha", () => {
    expect(formatHoldInstant("no-es-fecha")).toBe("no-es-fecha");
  });

  it("sin sello no hay etiqueta (y no se rellena con la fecha de hoy)", () => {
    expect(formatHoldInstant(null)).toBeNull();
    expect(formatHoldInstant("   ")).toBeNull();
  });
});

describe("formatHoldBarDay", () => {
  it("presenta sólo el día de la barra, sin hora", () => {
    const label = formatHoldBarDay("2026-09-30T00:00:00Z");
    expect(label).toContain("30");
    expect(label).toContain("2026");
    expect(label).not.toContain(":");
  });

  it("no desplaza el día por la zona horaria del navegador", () => {
    // Un sello a medianoche UTC es el día 30 en cualquier zona: la barra es diaria.
    expect(formatHoldBarDay("2026-09-30T00:00:00Z")).toBe(
      formatHoldBarDay("2026-09-30"),
    );
    expect(formatHoldBarDay("2026-09-30T23:30:00Z")).toBe(
      formatHoldBarDay("2026-09-30"),
    );
  });

  it("un sello no parseable se conserva crudo", () => {
    expect(formatHoldBarDay("no-es-fecha")).toBe("no-es-fecha");
    expect(formatHoldBarDay("2026-13-45")).toBe("2026-13-45");
  });

  it("sin sello no hay etiqueta", () => {
    expect(formatHoldBarDay(null)).toBeNull();
    expect(formatHoldBarDay("  ")).toBeNull();
  });
});

describe("describeGatedState", () => {
  it("resume el estado declarado del libro sin derivarlo", () => {
    expect(
      describeGatedState({
        holdsLong: true,
        source: "book",
        exitEvaluated: "last_bar",
      }),
    ).toBe(
      "libro con posición larga · leído del libro · salida evaluada en la última barra",
    );
  });

  it("declara el hueco cuando el libro no se pudo leer", () => {
    const label = describeGatedState({
      holdsLong: null,
      source: "unavailable",
    });
    expect(label).toContain("no se sabe si había posición");
    expect(label).toContain("libro no legible");
  });

  it("sin holdsLong pero con otros campos declara que no se sabe si había posición", () => {
    const label = describeGatedState({ source: "book" });
    expect(label).toContain("no se sabe si había posición");
    expect(label).toContain("leído del libro");
  });

  it("una forma desconocida no se inventa: no hay resumen", () => {
    expect(describeGatedState(null)).toBeNull();
    expect(describeGatedState("largo")).toBeNull();
    expect(describeGatedState({})).toBeNull();
  });
});

describe("buildAutoHoldDeclarations", () => {
  it("clasifica «no evaluable» y «sin señal» sin mezclarlos", () => {
    const { rows, summary, attention } = buildAutoHoldDeclarations([
      { instrumentId: "AAA", reason: "warmup_unmeasurable", facts: [] },
      { instrumentId: "BBB", reason: "no_signal", facts: [] },
    ]);

    expect(rows.map((row) => row.cause)).toEqual([
      "not_evaluable",
      "no_signal",
    ]);
    expect(rows[0]?.reasonLabel).toBe("warmup no medible");
    expect(rows[1]?.reasonLabel).toBe("sin señal");
    expect(summary.headline).toContain("1 sin señal");
    expect(summary.headline).toContain("1 HOLD no evaluable");
    // El aviso se calcula en el read-model con la MISMA clasificación del titular.
    expect(attention.map((row) => row.symbol)).toEqual(["AAA"]);
  });

  it("sube la procedencia declarada al primer nivel, en orden de lectura", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "no_signal",
        facts: [
          fact("strategyPresetKey", "sma_crossover"),
          fact("gatedState", {
            holdsLong: false,
            source: "book",
            exitEvaluated: "last_bar",
          }),
          fact("signalWindowBars", 201),
          fact("featureSource", "real"),
          fact("warmupBars", 201),
          fact("signalWindowSource", "preset_warmup"),
        ],
      },
    ]);

    const provenance = rows[0]!.provenance;
    expect(provenance.map((item) => item.key)).toEqual([
      "featureSource",
      "signalWindowBars",
      "warmupBars",
      "signalWindowSource",
      "gatedState",
      "strategyPresetKey",
    ]);
    expect(provenance[0]?.label).toBe(
      AUTO_HOLD_PROVENANCE_LABELS.featureSource,
    );
    expect(provenance[0]?.value).toBe("datos reales");
    expect(provenance[1]?.value).toBe("201 barras");
    expect(provenance[2]?.value).toBe("201 barras");
    expect(provenance[3]?.value).toBe("calentamiento del preset");
    expect(provenance[4]?.value).toContain("libro sin posición larga");
    expect(provenance[5]?.value).toBe("sma_crossover");
  });

  it("un hecho desconocido NO se presenta como causa: queda en el detalle técnico", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "no_signal",
        facts: [
          fact("mysteryKey", "valor"),
          fact("featureSource", "synthetic"),
        ],
      },
    ]);

    expect(rows[0]?.provenance.map((item) => item.key)).toEqual([
      "featureSource",
    ]);
    expect(rows[0]?.technicalFacts.map((item) => item.key)).toContain(
      "mysteryKey",
    );
  });

  it("un valor ausente no produce item de procedencia ni inventa un cero", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "no_snapshot",
        facts: [
          fact("signalWindowBars", null, "UNKNOWN"),
          fact("featureSource", "   ", "UNKNOWN"),
          fact("warmupBars", 0),
        ],
      },
    ]);

    expect(rows[0]?.provenance.map((item) => item.key)).toEqual(["warmupBars"]);
    expect(rows[0]?.provenance[0]?.value).toBe("0 barras");
    expect(rows[0]?.measurement).toBe("UNKNOWN");
  });

  it("no deduce la medición: sin medición declarada un hecho es UNKNOWN", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "no_signal",
        facts: [{ key: "warmupBars", value: 201 }],
      },
    ]);

    expect(rows[0]?.measurement).toBe("UNKNOWN");
    expect(rows[0]?.provenance[0]?.measurement).toBe("UNKNOWN");
  });

  it("sin hechos no hay procedencia y la fila declara la medición del productor", () => {
    const { rows } = buildAutoHoldDeclarations([
      { instrumentId: "AAA", reason: "no_signal", facts: [] },
    ]);

    expect(rows[0]?.provenance).toEqual([]);
    expect(rows[0]?.technicalFacts).toEqual([]);
    expect(rows[0]?.measurement).toBe("UNKNOWN");
    expect(AUTO_HOLD_PROVENANCE_ABSENT).toBe("Procedencia no declarada");
  });

  it("conserva el código crudo del motivo para el detalle técnico", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "gated_unavailable",
        facts: [],
      },
    ]);

    expect(rows[0]?.causeLabel).toBe("no evaluable");
    expect(rows[0]?.reasonCode).toBe("gated_unavailable");
    expect(rows[0]?.reasonMissing).toBe(false);
  });

  it("un motivo desconocido no se presenta como causa ni como motivo legible", () => {
    const { rows } = buildAutoHoldDeclarations([
      { instrumentId: "AAA", reason: "invented_reason", facts: [] },
    ]);

    expect(rows[0]?.cause).toBe("unmeasured");
    expect(rows[0]?.reasonLabel).toBeNull();
    expect(rows[0]?.reasonMissing).toBe(true);
    expect(autoHoldReasonLabel(rows[0]!)).toBe(AUTO_HOLD_REASON_ABSENT);
  });

  it("el detalle del motivo pierde el código delante, pero no un texto con dos puntos", () => {
    const { rows } = buildAutoHoldDeclarations([
      {
        instrumentId: "AAA",
        reason: "gated_unavailable",
        facts: [
          fact("holdDetail", "gated_unavailable: el libro no se pudo leer"),
        ],
      },
      {
        instrumentId: "BBB",
        reason: "no_signal",
        facts: [fact("holdDetail", "ventana: 120 barras")],
      },
    ]);

    expect(rows[0]?.provenance[0]?.value).toBe("el libro no se pudo leer");
    expect(rows[1]?.provenance[0]?.value).toBe("ventana: 120 barras");
  });

  it("sin declaraciones no afirma «sin señal»", () => {
    const { rows, summary } = buildAutoHoldDeclarations([]);
    expect(rows).toEqual([]);
    expect(summary.headline).toBe("Sin HOLD declarados en la ventana");
    expect(summary.headline).not.toContain("sin señal");
  });

  it("un HOLD sin símbolo declara el hueco", () => {
    const { rows } = buildAutoHoldDeclarations([
      { instrumentId: null, reason: "no_signal", facts: [] },
    ]);
    expect(autoHoldSymbolLabel(rows[0]!)).toBe("Sin dato todavía");
    expect(rows[0]?.symbol).toBeNull();
  });
});

describe("buildAutoHoldDeclarations · alcance temporal", () => {
  const today = {
    instrumentId: "AAA",
    barTimestamp: "2026-10-28T00:00:00Z",
    at: "2026-10-28T10:00:00Z",
    reason: "no_signal",
    facts: [],
  };
  const yesterday = {
    instrumentId: "BBB",
    barTimestamp: "2026-10-27T00:00:00Z",
    at: "2026-10-27T10:00:00Z",
    reason: "warmup_unmeasurable",
    facts: [],
  };

  it("filtra por el día explicado y declara cuántas quedan fuera", () => {
    const result = buildAutoHoldDeclarations([yesterday, today], {
      day: "2026-10-28",
    });

    expect(result.rows.map((row) => row.symbol)).toEqual(["AAA"]);
    expect(result.excludedByDay).toBe(1);
    expect(result.scopeNote).toContain("1 declaración queda fuera");
    // El titular se refiere al conjunto LEÍDO, no a la ventana completa.
    expect(result.summary.headline).toBe("1 HOLD sin señal");
  });

  it("sin filtro conserva la ventana completa y no declara exclusiones", () => {
    const result = buildAutoHoldDeclarations([yesterday, today]);

    expect(result.rows).toHaveLength(2);
    expect(result.excludedByDay).toBe(0);
    expect(result.scopeNote).toBeNull();
    expect(result.withoutBarDay).toBe(0);
    expect(result.undatedNote).toBeNull();
  });

  it("el día de la barra manda sobre `at` cuando difieren", () => {
    // La vela es del 27; el registro se escribió el 28. La fila pertenece al 27 y el 28 la
    // declara fuera, en vez de asignarla al día de registro.
    const lateRegistration = {
      instrumentId: "DDD",
      barTimestamp: "2026-10-27T00:00:00Z",
      at: "2026-10-28T10:00:00Z",
      reason: "no_signal",
      facts: [],
    };

    const day27 = buildAutoHoldDeclarations([lateRegistration], {
      day: "2026-10-27",
    });
    expect(day27.rows.map((row) => row.symbol)).toEqual(["DDD"]);
    expect(day27.excludedByDay).toBe(0);

    const day28 = buildAutoHoldDeclarations([lateRegistration], {
      day: "2026-10-28",
    });
    expect(day28.rows).toEqual([]);
    expect(day28.excludedByDay).toBe(1);
    expect(day28.scopeNote).toContain("1 declaración queda fuera");
  });

  it("el día vacío declara el hueco del día, no el de la ventana", () => {
    const result = buildAutoHoldDeclarations([yesterday], {
      day: "2026-10-28",
    });

    expect(result.rows).toEqual([]);
    expect(result.summary.headline).toBe(
      "Sin HOLD declarados en el día explicado",
    );
    expect(result.scopeNote).toContain("fuera del día explicado");
  });

  it("sin sello no se atribuye a un día y se declara en un contador propio", () => {
    const result = buildAutoHoldDeclarations(
      [{ instrumentId: "CCC", reason: "no_signal", facts: [] }, today],
      { day: "2026-10-28" },
    );

    // La primera parte se mantiene: no se le asigna un día.
    expect(result.rows.map((row) => row.symbol)).toEqual(["AAA"]);
    // Y no se cuenta como si perteneciera a otro día.
    expect(result.excludedByDay).toBe(0);
    expect(result.scopeNote).toBeNull();
    // Pero el hueco de trazabilidad se declara aparte.
    expect(result.withoutBarDay).toBe(1);
    expect(result.undatedNote).toContain("1 declaración sin fecha de barra");
    expect(result.undatedNote).toContain("no se puede asignar a este día");
  });

  it("`at` por sí solo no asigna la declaración al día ni cuenta como exclusión", () => {
    const onlyAt = {
      instrumentId: "EEE",
      at: "2026-10-28T10:00:00Z",
      reason: "no_signal",
      facts: [],
    };

    const result = buildAutoHoldDeclarations([onlyAt], { day: "2026-10-28" });

    expect(result.rows).toEqual([]);
    expect(result.excludedByDay).toBe(0);
    expect(result.withoutBarDay).toBe(1);
  });

  it("una fecha de barra imposible no atribuye la declaración a ningún día", () => {
    const corrupted = {
      instrumentId: "FFF",
      barTimestamp: "2026-13-45T00:00:00Z",
      reason: "no_signal",
      facts: [],
    };

    const result = buildAutoHoldDeclarations([corrupted], {
      day: "2026-10-28",
    });

    expect(result.rows).toEqual([]);
    expect(result.excludedByDay).toBe(0);
    expect(result.withoutBarDay).toBe(1);
  });
});
