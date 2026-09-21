/**
 * V2.47 — copia del valor esperado: signo, moneda y ausencia declarada.
 *
 * Estos tests fijan la regla honesta: un valor NO medido se declara con `null` (la
 * superficie omite la fila) y jamás se publica como `0 €`, que afirmaría "esta operación
 * no deja dinero" — algo que solo se sabe midiendo.
 */

import { describe, expect, it } from "vitest";
import {
  formatExpectedCurrency,
  formatExpectedR,
  formatExpectedValueLabel,
} from "./expected-value-copy.js";

describe("expectedValueCopy V2.47", () => {
  it("money con signo explícito y moneda explícita", () => {
    expect(formatExpectedCurrency(34)).toBe("+34.00 €");
    expect(formatExpectedCurrency(-12.5)).toBe("−12.50 €");
    expect(formatExpectedCurrency(0)).toBe("0.00 €");
  });

  it("R adimensional con dos decimales", () => {
    expect(formatExpectedR(0.8)).toBe("0.80");
    expect(formatExpectedR(-0.25)).toBe("-0.25");
  });

  it("sin medición devuelve null: no hay fila que pintar", () => {
    expect(formatExpectedCurrency(null)).toBeNull();
    expect(formatExpectedCurrency(undefined)).toBeNull();
    expect(formatExpectedCurrency(Number.NaN)).toBeNull();
    expect(formatExpectedR(null)).toBeNull();
    expect(formatExpectedValueLabel({})).toBeNull();
    expect(
      formatExpectedValueLabel({
        expectedR: null,
        netExpectedCurrency: null,
      }),
    ).toBeNull();
  });

  it("etiqueta compuesta: neto primero, R después", () => {
    expect(
      formatExpectedValueLabel({ expectedR: 0.8, netExpectedCurrency: 34 }),
    ).toBe("+34.00 € · R esperado 0.80");
  });

  it("R sin coste cerrado publica solo el R (el hueco es el dato que falta)", () => {
    expect(
      formatExpectedValueLabel({ expectedR: 0.42, netExpectedCurrency: null }),
    ).toBe("R esperado 0.42");
  });
});
