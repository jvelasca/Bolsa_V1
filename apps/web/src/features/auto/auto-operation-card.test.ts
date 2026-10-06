/**
 * La tarjeta pinta las seis ranuras y no convierte un fill en simulación,
 * posición de la operación ni dinero real.
 */

import { describe, expect, it } from "vitest";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";
import {
  AUTO_CARD_ACCOUNT_SCOPE,
  AUTO_CARD_ORDER_NOTED,
  AUTO_CARD_PARTIAL,
  AUTO_CARD_SLOT_ABSENT,
  AUTO_CARD_SLOT_DONE,
  AUTO_CARD_SLOT_PENDING,
  buildAutoOperationCard,
} from "@/features/auto/auto-operation-card";

const ORDER_REACHED = {
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

function slot(card: ReturnType<typeof buildAutoOperationCard>, id: string) {
  const found = card.slots.find((item) => item.id === id);
  if (!found) throw new Error(`falta la ranura ${id}`);
  return found;
}

const ACCOUNT = {
  positionLabel: "2 posiciones en la cuenta simulada",
  cashLabel: "10000.00 €",
  pnlLabel: "Resultado de la cuenta 12.50 €",
};

describe("buildAutoOperationCard", () => {
  it("pinta las seis ranuras aunque solo exista la orden", () => {
    const card = buildAutoOperationCard({
      cycleId: "c",
      instrumentId: "AAPL",
      closed: false,
      closedMeasurement: "COMPLETE",
      steps: [ORDER_REACHED, FILL_PENDING],
    });
    expect(card.slots.map((item) => item.id)).toEqual([
      "decision",
      "order",
      "execution",
      "simulation",
      "position",
      "money",
    ]);
    expect(card.symbol).toBe("AAPL");
    expect(card.headline).toBe("Orden pendiente");
    expect(slot(card, "decision").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "order")).toMatchObject({
      state: AUTO_CARD_SLOT_DONE,
      detail: AUTO_CARD_ORDER_NOTED,
    });
    expect(slot(card, "execution").state).toBe(AUTO_CARD_SLOT_PENDING);
    expect(slot(card, "simulation").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "position").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "money").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    const text = JSON.stringify(card);
    expect(text).not.toContain("COMPRAR");
    expect(text).not.toContain("decidió");
    expect(text).not.toContain("Materializada");
    expect(text).not.toContain("Completada");
    expect(text).not.toContain("DINERO REAL");
    expect(text).not.toContain("Orden enviada");
    expect(text).not.toContain("Posición abierta");
  });

  it("un fill completo no marca simulación ni posición de la operación", () => {
    const card = buildAutoOperationCard(
      {
        cycleId: "c",
        instrumentId: "AAPL",
        steps: [
          { ...ORDER_REACHED, facts: [entryOrder(10, 10)] },
          FILL_REACHED,
        ],
      },
      ACCOUNT,
    );
    expect(card.headline).toBe("Precio aplicado");
    expect(slot(card, "execution")).toMatchObject({
      state: AUTO_CARD_SLOT_DONE,
      detail: "10/10",
    });
    expect(slot(card, "simulation").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "simulation").state).not.toBe(AUTO_CARD_SLOT_DONE);
    expect(slot(card, "position").state).toBe(ACCOUNT.positionLabel);
    expect(slot(card, "position").state).not.toBe(AUTO_CARD_SLOT_DONE);
    expect(slot(card, "money").state).toBe(AUTO_CARD_ACCOUNT_SCOPE);
    expect(slot(card, "money").detail).toContain("Efectivo simulado");
    expect(slot(card, "money").detail).toContain("Resultado de la cuenta");
  });

  it("una cantidad aplicada menor es Ejecución parcial", () => {
    const card = buildAutoOperationCard({
      cycleId: "c",
      steps: [{ ...ORDER_REACHED, facts: [entryOrder(10, 4)] }, FILL_REACHED],
    });
    expect(slot(card, "execution")).toMatchObject({
      state: AUTO_CARD_PARTIAL,
      detail: "4/10",
    });
    expect(slot(card, "simulation").state).toBe(AUTO_HOME_NO_DATA_LABEL);
  });

  it("un paso ausente se llama No ocurrió y no se rellena", () => {
    const card = buildAutoOperationCard({
      cycleId: "c",
      steps: [
        { id: "ORDER", state: "absent" },
        { id: "FILL", state: "absent" },
      ],
    });
    expect(slot(card, "order").state).toBe(AUTO_CARD_SLOT_ABSENT);
    expect(slot(card, "execution").state).toBe(AUTO_CARD_SLOT_ABSENT);
  });

  it("un fill sin orden no afirma la ejecución", () => {
    const card = buildAutoOperationCard({
      cycleId: "c",
      instrumentId: "AAPL",
      steps: [{ ...FILL_REACHED, facts: [entryOrder(10, 10)] }],
    });
    expect(card.headline).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "order").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "execution").state).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(slot(card, "simulation").state).toBe(AUTO_HOME_NO_DATA_LABEL);
  });
});
