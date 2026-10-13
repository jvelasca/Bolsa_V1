/**
 * P2 (sello 2) — helpers puros de la auditoría por valor de ESTUDIO.
 *
 * Invariante clave: un dato ausente se declara «Sin dato todavía», nunca un `0`.
 */

import { describe, expect, it } from "vitest";
import {
  describeCycle,
  describeSignal,
  describeStrategy,
  describeVerdict,
  estudioValueState,
  formatPct,
  formatR,
  formatRate,
} from "@/features/auto-monitor/estudio-audit-view";

describe("estudio-audit-view", () => {
  it("declara huecos como «Sin dato todavía» (nunca 0)", () => {
    expect(formatR(null)).toBe("Sin dato todavía");
    expect(formatR(undefined)).toBe("Sin dato todavía");
    expect(formatPct(null)).toBe("Sin dato todavía");
    expect(formatRate(null)).toBe("Sin dato todavía");
    expect(formatR(-0.25)).toBe("-0.25R");
    expect(formatPct(2.5)).toBe("+2.50%");
    expect(formatRate(0.6)).toBe("60%");
  });

  it("el estado de medición solo es «measured» con la bandera explícita", () => {
    expect(estudioValueState(true)).toBe("measured");
    expect(estudioValueState(false)).toBe("unmeasured");
  });

  it("describe la estrategia con la identidad exacta o el hueco declarado", () => {
    expect(
      describeStrategy({ presetKey: "sma_crossover", version: "ver-1" }),
    ).toBe("sma_crossover · ver-1");
    expect(
      describeStrategy({ presetKey: "sma_crossover", version: null }),
    ).toBe("sma_crossover");
    expect(describeStrategy({ presetKey: null, version: "ver-1" })).toContain(
      "Sin dato todavía",
    );
    expect(describeStrategy({ presetKey: "  ", version: "ver-1" })).toContain(
      "Sin dato todavía",
    );
  });

  it("describe el veredicto con su motivo", () => {
    expect(
      describeVerdict({
        verdict: "MIXED",
        verdictReason: "preliminary_sample",
      }),
    ).toBe("MIXED · preliminary_sample");
    expect(describeVerdict({ verdict: "", verdictReason: null })).toBe(
      "NOT_MEASURED",
    );
  });

  it("describe un ciclo con su ventana y R, declarando los huecos", () => {
    expect(
      describeCycle({
        entryDay: "2026-04-01",
        exitDay: "2026-04-02",
        realizedR: 0.4,
      }),
    ).toBe("2026-04-01 → 2026-04-02 · +0.40R");
    expect(
      describeCycle({ entryDay: null, exitDay: null, realizedR: null }),
    ).toBe("sin día → sin día · Sin dato todavía");
  });

  it("describe la señal con los ciclos enlazables explícitos (cuadra con la lista)", () => {
    expect(
      describeSignal(
        {
          cycles: 3,
          linkedCycles: 2,
          unlinkedCycles: 1,
          duplicateCycles: 0,
          measuredCycles: 3,
        },
        2,
      ),
    ).toBe("2 de 3 ciclos enlazables · 3 medidos · 1 sin enlazar");
    // Sin desglose (artefacto antiguo) cae al nº realmente listado, nunca al total declarado.
    expect(describeSignal({ cycles: 3, measuredCycles: 3 }, 1)).toBe(
      "1 de 3 ciclos enlazables · 3 medidos",
    );
    // Claves repetidas declaradas (deduplicadas).
    expect(
      describeSignal(
        {
          cycles: 2,
          linkedCycles: 1,
          unlinkedCycles: 0,
          duplicateCycles: 1,
          measuredCycles: 2,
        },
        1,
      ),
    ).toBe("1 de 2 ciclos enlazables · 2 medidos · 1 repetidos");
  });
});
