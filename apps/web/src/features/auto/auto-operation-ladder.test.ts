/**
 * UI Contract 5.0 (`UI5-09`/`UI5-11`/`UI5-20`) — escalera universal de operación.
 *
 * Fija que un ciclo se traduce al peldaño canónico sin saltar de orden a posición y que el fill
 * es «Ejecución parcial/completada», nunca «Posición creada».
 */

import { describe, expect, it } from "vitest";
import type { AutoBasicCycle } from "@/features/auto/auto-basic-home";
import {
  OPERATION_LADDER,
  OPERATION_LADDER_NOTES,
  operationLadderLabel,
  operationLadderRungFromCycle,
} from "@/features/auto/auto-operation-ladder";

const ORDER_COMPLETE = {
  key: "entryOrder",
  value: { requestedQty: 10, appliedQty: 10 },
  measurement: "COMPLETE",
};

describe("OPERATION_LADDER", () => {
  it("declara la escalera en el orden del contrato", () => {
    expect(OPERATION_LADDER.map((rung) => rung.label)).toEqual([
      "Orden preparada",
      "Orden enviada",
      "Esperando ejecución",
      "Ejecución parcial",
      "Ejecución completada",
      "Posición creada",
      "Posición cerrada",
    ]);
  });

  it("un término = un significado: la etiqueta canónica sale del módulo", () => {
    expect(operationLadderLabel("executed")).toBe("Ejecución completada");
    expect(OPERATION_LADDER_NOTES.priceAppliedIsNotPosition).toBe(
      "Precio aplicado ≠ posición creada",
    );
  });
});

describe("operationLadderRungFromCycle", () => {
  const cycle = (steps: AutoBasicCycle["steps"]): AutoBasicCycle => ({
    cycleId: "cyc-1",
    instrumentId: "AAPL",
    closed: false,
    closedMeasurement: "COMPLETE",
    steps,
  });

  it("una orden anotada pero no enviada está «Orden preparada»", () => {
    expect(
      operationLadderRungFromCycle(cycle([{ id: "ORDER", state: "pending" }]))
        .label,
    ).toBe("Orden preparada");
  });

  it("una orden enviada sin fill está «Orden enviada»", () => {
    expect(
      operationLadderRungFromCycle(cycle([{ id: "ORDER", state: "reached" }]))
        .label,
    ).toBe("Orden enviada");
  });

  it("entre orden y fill está «Esperando ejecución»", () => {
    const rung = operationLadderRungFromCycle(
      cycle([
        { id: "ORDER", state: "reached" },
        { id: "FILL", state: "pending" },
      ]),
    );
    expect(rung.id).toBe("waiting_execution");
    expect(rung.label).toBe("Esperando ejecución");
  });

  it("un fill parcial es «Ejecución parcial» con la distancia al peldaño siguiente", () => {
    const rung = operationLadderRungFromCycle(
      cycle([
        {
          id: "ORDER",
          state: "reached",
          facts: [
            {
              key: "entryOrder",
              value: { requestedQty: 10, appliedQty: 4 },
              measurement: "COMPLETE",
            },
          ],
        },
        { id: "FILL", state: "reached", measurement: "COMPLETE" },
      ]),
    );
    expect(rung.id).toBe("partial_execution");
    expect(rung.label).toBe("Ejecución parcial");
    expect(rung.note).toBe("Precio aplicado ≠ posición creada");
  });

  it("un fill completo es «Ejecución completada», nunca «Posición creada»", () => {
    const rung = operationLadderRungFromCycle(
      cycle([
        { id: "ORDER", state: "reached", facts: [ORDER_COMPLETE] },
        { id: "FILL", state: "reached", measurement: "COMPLETE" },
      ]),
    );
    expect(rung.id).toBe("executed");
    expect(rung.label).toBe("Ejecución completada");
    // La escalera se detiene antes de materializar: sin traza de apply, no hay «Posición creada».
    expect(rung.label).not.toBe("Posición creada");
    expect(rung.note).toBe(OPERATION_LADDER_NOTES.priceAppliedIsNotPosition);
  });

  it("un ciclo cerrado es «Posición cerrada»", () => {
    const rung = operationLadderRungFromCycle({
      ...cycle([{ id: "ORDER", state: "reached", facts: [ORDER_COMPLETE] }]),
      closed: true,
    });
    expect(rung.id).toBe("position_closed");
  });

  it("un cierre sin medición COMPLETE no salta a «Posición cerrada» (UNKNOWN ≠ 0)", () => {
    const partial = operationLadderRungFromCycle({
      ...cycle([{ id: "ORDER", state: "reached", facts: [ORDER_COMPLETE] }]),
      closed: true,
      closedMeasurement: "PARTIAL",
    });
    expect(partial.id).toBeNull();
    expect(partial.label).toBe("Sin dato todavía");

    const unmeasured = operationLadderRungFromCycle({
      ...cycle([{ id: "ORDER", state: "reached", facts: [ORDER_COMPLETE] }]),
      closed: true,
      closedMeasurement: null,
    });
    expect(unmeasured.id).not.toBe("position_closed");
    expect(unmeasured.label).toBe("Sin dato todavía");
  });

  it("un fill sin medición COMPLETE es «Sin dato todavía» (UNKNOWN ≠ 0)", () => {
    const rung = operationLadderRungFromCycle(
      cycle([
        { id: "ORDER", state: "reached", facts: [ORDER_COMPLETE] },
        { id: "FILL", state: "reached", measurement: "UNKNOWN" },
      ]),
    );
    expect(rung.id).toBeNull();
    expect(rung.label).toBe("Sin dato todavía");
  });

  it("un fill sin orden alcanzada no se afirma (no se salta peldaños)", () => {
    const rung = operationLadderRungFromCycle(
      cycle([{ id: "FILL", state: "reached", measurement: "COMPLETE" }]),
    );
    expect(rung.id).toBeNull();
    expect(rung.label).toBe("Sin dato todavía");
  });
});
