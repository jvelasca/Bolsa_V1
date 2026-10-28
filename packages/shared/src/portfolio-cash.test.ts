/**
 * P1-04 — el tono de un asiento no sale del signo del importe.
 *
 * Falsable: si el primer nivel vuelve a `amount >= 0 ? verde : rojo`, una
 * comisión (coste) se pinta como una compra y una venta como un ingreso; esta
 * tabla fija el papel de cada movimiento.
 */
import { describe, expect, it } from "vitest";
import { ledgerAmountTone } from "./portfolio-cash.js";

describe("ledgerAmountTone", () => {
  it("las comisiones y la custodia son coste, aunque el importe sea negativo", () => {
    expect(
      ledgerAmountTone({
        type: "fee",
        referenceType: "transaction",
        amount: -4.5,
      }),
    ).toBe("cost");
    expect(
      ledgerAmountTone({ type: "fee", referenceType: "custody", amount: -12 }),
    ).toBe("cost");
    expect(
      ledgerAmountTone({
        type: "withdrawal",
        referenceType: null,
        amount: -500,
      }),
    ).toBe("cost");
  });

  it("ventas, dividendos e ingresos son entradas", () => {
    expect(
      ledgerAmountTone({
        type: "sell",
        referenceType: "transaction",
        amount: 900,
      }),
    ).toBe("in");
    expect(
      ledgerAmountTone({ type: "dividend", referenceType: null, amount: 12 }),
    ).toBe("in");
    expect(
      ledgerAmountTone({
        type: "deposit",
        referenceType: "external",
        amount: 1000,
      }),
    ).toBe("in");
  });

  it("una compra no es una pérdida: es neutral", () => {
    expect(
      ledgerAmountTone({
        type: "buy",
        referenceType: "transaction",
        amount: -1000,
      }),
    ).toBe("neutral");
  });

  it("transferencias y ajustes no juzgan resultado", () => {
    expect(
      ledgerAmountTone({
        type: "deposit",
        referenceType: "transfer",
        amount: 250,
      }),
    ).toBe("neutral");
    expect(
      ledgerAmountTone({ type: "adjustment", referenceType: null, amount: 3 }),
    ).toBe("neutral");
  });
});
