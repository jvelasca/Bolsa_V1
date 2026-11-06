/**
 * O-4 — lectura del veredicto de ventana.
 *
 * El módulo NO decide ni conoce umbrales: agrega lo que el gate declaró por valor. Estas
 * pruebas fijan los tres estados honestos: `COMPLETE` (un veredicto medido), `PARTIAL`
 * (veredictos distintos conviviendo) y `UNKNOWN` (nada medido ⇒ nunca la constante histórica).
 */

import { describe, expect, it } from "vitest";

import {
  describeWindowVerdict,
  readWindowVerdict,
} from "@/features/auto-monitor/window-verdict";

describe("readWindowVerdict", () => {
  it("devuelve el veredicto único que el gate declaró", () => {
    const read = readWindowVerdict([
      { measured: true, resultR: { verdict: "INCONCLUSIVE", measured: true } },
      { measured: true, resultR: { verdict: "INCONCLUSIVE", measured: true } },
    ]);
    expect(read).toMatchObject({
      verdict: "INCONCLUSIVE",
      measurement: "COMPLETE",
      measuredValues: 2,
      totalValues: 2,
    });
    expect(describeWindowVerdict(read, "NO MEDIDO")).toBe("INCONCLUSIVE");
  });

  it("no inventa un veredicto de ventana cuando los valores no coinciden", () => {
    const read = readWindowVerdict([
      { measured: true, resultR: { verdict: "INCONCLUSIVE", measured: true } },
      { measured: true, resultR: { verdict: "READY", measured: true } },
    ]);
    expect(read.verdict).toBeNull();
    expect(read.measurement).toBe("PARTIAL");
    expect(read.counts).toEqual([
      { verdict: "INCONCLUSIVE", count: 1 },
      { verdict: "READY", count: 1 },
    ]);
    expect(describeWindowVerdict(read, "NO MEDIDO")).toBe(
      "SIN VEREDICTO ÚNICO (INCONCLUSIVE 1 · READY 1)",
    );
  });

  it("UNKNOWN ≠ 0: sin valores medidos no hay veredicto", () => {
    const read = readWindowVerdict([
      {
        measured: false,
        resultR: { verdict: "INCONCLUSIVE", measured: false },
      },
      { measured: true, resultR: { verdict: "NOT_MEASURED", measured: true } },
    ]);
    expect(read.verdict).toBeNull();
    expect(read.measurement).toBe("UNKNOWN");
    expect(read.measuredValues).toBe(0);
    expect(read.totalValues).toBe(2);
    expect(describeWindowVerdict(read, "NO MEDIDO")).toBe("NO MEDIDO");
  });

  it("sin DTO declara el hueco en vez de rellenar un veredicto", () => {
    for (const input of [null, undefined, []]) {
      const read = readWindowVerdict(input);
      expect(read.measurement).toBe("UNKNOWN");
      expect(read.verdict).toBeNull();
      expect(read.totalValues).toBe(0);
    }
  });

  it("un valor sin resultR no cuenta como medido", () => {
    const read = readWindowVerdict([{ measured: true, resultR: null }]);
    expect(read.measurement).toBe("UNKNOWN");
    expect(read.measuredValues).toBe(0);
  });
});
