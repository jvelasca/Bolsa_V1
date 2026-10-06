/**
 * HOME de seis preguntas: no inventa acción, decisión ni cabecera de fill.
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_HEADER_ORDER_PENDING,
  AUTO_HEADER_PARTIAL,
  AUTO_HEADER_PRICE_APPLIED,
  AUTO_NO_CURRENT_OPERATION,
  AUTO_SIMULATION_BANNER,
  buildAutoBasicHome,
  operationHappenedLabel,
} from "@/features/auto/auto-basic-home";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";

const ORDER_PENDING = {
  id: "ORDER",
  state: "reached",
  measurement: "COMPLETE",
} as const;
const FILL_PENDING = { id: "FILL", state: "pending" } as const;
const FILL_REACHED = {
  id: "FILL",
  state: "reached",
  measurement: "COMPLETE",
} as const;

function entryOrder(requestedQty: number, appliedQty: number) {
  return {
    key: "entryOrder",
    measurement: "COMPLETE",
    value: { requestedQty, appliedQty },
  };
}

describe("operationHappenedLabel", () => {
  it("una orden sin fill es Orden pendiente", () => {
    expect(
      operationHappenedLabel({
        cycleId: "c",
        steps: [ORDER_PENDING, FILL_PENDING],
      }),
    ).toBe(AUTO_HEADER_ORDER_PENDING);
  });

  it("un fill sin cantidades medidas no se llama Precio aplicado", () => {
    expect(
      operationHappenedLabel({
        cycleId: "c",
        steps: [ORDER_PENDING, FILL_REACHED],
      }),
    ).toBe(AUTO_HOME_NO_DATA_LABEL);
  });

  it("cantidades iguales, sin apply, son Precio aplicado", () => {
    expect(
      operationHappenedLabel({
        cycleId: "c",
        steps: [
          { ...ORDER_PENDING, facts: [entryOrder(10, 10)] },
          FILL_REACHED,
        ],
      }),
    ).toBe(AUTO_HEADER_PRICE_APPLIED);
  });

  it("una cantidad aplicada menor es Ejecución parcial", () => {
    expect(
      operationHappenedLabel({
        cycleId: "c",
        steps: [{ ...ORDER_PENDING, facts: [entryOrder(10, 4)] }, FILL_REACHED],
      }),
    ).toBe(AUTO_HEADER_PARTIAL);
  });

  it("un fill con medición incompleta no afirma el precio", () => {
    expect(
      operationHappenedLabel({
        cycleId: "c",
        steps: [
          { ...ORDER_PENDING, facts: [entryOrder(10, 10)] },
          { ...FILL_REACHED, measurement: "PARTIAL" },
        ],
      }),
    ).toBe(AUTO_HOME_NO_DATA_LABEL);
  });

  it("no dice Materializada ni Completada", () => {
    const label = operationHappenedLabel({
      cycleId: "c",
      closed: false,
      closedMeasurement: "COMPLETE",
      steps: [{ ...ORDER_PENDING, facts: [entryOrder(10, 10)] }, FILL_REACHED],
    });
    expect(label).not.toBe("Materializada");
    expect(label).not.toBe("Completada");
    expect(label).not.toBe("Posición abierta");
  });
});

describe("buildAutoBasicHome", () => {
  it("responde las seis preguntas sin inventar acción ni decisión", () => {
    const home = buildAutoBasicHome({
      header: { state: "RUNNING" },
      cycles: [
        {
          cycleId: "c",
          instrumentId: "AAPL",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [
            { ...ORDER_PENDING, facts: [entryOrder(10, 10)] },
            FILL_REACHED,
          ],
        },
      ],
    });
    expect(home.workingLabel).toBe("Funcionando");
    expect(home.doingLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(home.doingLabel).not.toContain("Esperando");
    expect(home.doingLabel).not.toContain("Analizando");
    expect(home.assetLabel).toBe("AAPL");
    expect(home.decisionLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(home.happenedLabel).toBe(AUTO_HEADER_PRICE_APPLIED);
    expect(home.moneyLabel).toBe(AUTO_SIMULATION_BANNER);
  });

  it("una reserva o un cierre no medido no son una operación en curso", () => {
    const home = buildAutoBasicHome({
      header: { state: "RUNNING" },
      cycles: [
        {
          cycleId: "reserve",
          instrumentId: "AAPL",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [{ id: "RESERVATION", state: "reached" }],
        },
        {
          cycleId: "gap",
          instrumentId: "MSFT",
          closed: null,
          closedMeasurement: "UNKNOWN",
          steps: [ORDER_PENDING, FILL_PENDING],
        },
        {
          cycleId: "done",
          instrumentId: "IBM",
          closed: true,
          closedMeasurement: "COMPLETE",
          steps: [
            { ...ORDER_PENDING, facts: [entryOrder(10, 10)] },
            FILL_REACHED,
          ],
        },
      ],
    });
    expect(home.currentOperations).toHaveLength(0);
    expect(home.happenedLabel).toBe(AUTO_NO_CURRENT_OPERATION);
  });

  it("sin ciclo en curso distingue el vacío del hueco", () => {
    const home = buildAutoBasicHome({
      header: { state: "PAUSED" },
      cycles: [],
    });
    expect(home.workingLabel).toBe("Detenido");
    expect(home.assetLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(home.happenedLabel).toBe(AUTO_NO_CURRENT_OPERATION);
    expect(home.moneyLabel).toBe(AUTO_SIMULATION_BANNER);
  });

  it("durante la carga no finge el estado y el banner de dinero sigue", () => {
    const home = buildAutoBasicHome({
      isLoading: true,
      header: { state: "RUNNING" },
      cycles: [
        {
          cycleId: "c",
          instrumentId: "AAPL",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [ORDER_PENDING, FILL_PENDING],
        },
      ],
    });
    expect(home.workingLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(home.happenedLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(home.moneyLabel).toBe(AUTO_SIMULATION_BANNER);
    expect(home.currentOperations).toHaveLength(0);
  });

  it("dos operaciones en curso no se colapsan en la primera", () => {
    const home = buildAutoBasicHome({
      header: { state: "RUNNING" },
      cycles: [
        {
          cycleId: "a",
          instrumentId: "AAPL",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [ORDER_PENDING, FILL_PENDING],
        },
        {
          cycleId: "b",
          instrumentId: "MSFT",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [ORDER_PENDING, FILL_PENDING],
        },
      ],
    });
    expect(home.assetLabel).toBe("AAPL, MSFT");
    expect(home.happenedLabel).toBe("2 operaciones en curso");
    expect(home.currentOperations.map((item) => item.cycleId)).toEqual([
      "a",
      "b",
    ]);
  });
});
