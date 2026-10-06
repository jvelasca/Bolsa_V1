/**
 * Tarjeta de una operación (spec de usuario básico §4–§5).
 *
 * Seis ranuras siempre visibles. No salta peldaños: un fill no marca
 * simulación ni posición de la operación. La decisión durable y la traza
 * de apply no existen: esas ranuras quedan en «Sin dato todavía».
 *
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §4 §5
 */

import {
  type AutoBasicCycle,
  operationHappenedLabel,
  readEntryQuantities,
} from "@/features/auto/auto-basic-home";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";

export const AUTO_CARD_SLOT_DONE = "Hecho";
export const AUTO_CARD_SLOT_PENDING = "Pendiente";
export const AUTO_CARD_SLOT_ABSENT = "No ocurrió";
export const AUTO_CARD_ORDER_NOTED = "Orden anotada";
export const AUTO_CARD_PARTIAL = "Ejecución parcial";
export const AUTO_CARD_ACCOUNT_SCOPE = "en la cuenta simulada";

export type AutoCardSlotId =
  | "decision"
  | "order"
  | "execution"
  | "simulation"
  | "position"
  | "money";

export type AutoCardSlot = {
  id: AutoCardSlotId;
  label: string;
  state: string;
  detail: string | null;
};

/** Cifras de cuenta ya medidas. Un hueco llega como «Sin dato todavía». */
export type AutoOperationCardAccount = {
  positionLabel: string;
  cashLabel: string;
  pnlLabel: string;
};

export type AutoOperationCardV1 = {
  cycleId: string;
  symbol: string;
  headline: string;
  slots: readonly AutoCardSlot[];
};

const SLOT_LABELS: readonly { id: AutoCardSlotId; label: string }[] = [
  { id: "decision", label: "Decisión" },
  { id: "order", label: "Orden" },
  { id: "execution", label: "Ejecución" },
  { id: "simulation", label: "Simulación" },
  { id: "position", label: "Posición" },
  { id: "money", label: "Dinero" },
];

function stepOf(cycle: AutoBasicCycle, id: string) {
  return (cycle.steps ?? []).find((step) => step.id === id);
}

function orderSlot(
  cycle: AutoBasicCycle,
): Pick<AutoCardSlot, "state" | "detail"> {
  const order = stepOf(cycle, "ORDER");
  if (!order) return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  if (order.state === "reached") {
    return { state: AUTO_CARD_SLOT_DONE, detail: AUTO_CARD_ORDER_NOTED };
  }
  if (order.state === "pending") {
    return { state: AUTO_CARD_SLOT_PENDING, detail: null };
  }
  if (order.state === "absent") {
    return { state: AUTO_CARD_SLOT_ABSENT, detail: null };
  }
  return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
}

function executionSlot(
  cycle: AutoBasicCycle,
): Pick<AutoCardSlot, "state" | "detail"> {
  const order = stepOf(cycle, "ORDER");
  const fill = stepOf(cycle, "FILL");
  const orderReached = order?.state === "reached";
  const fillReached = fill?.state === "reached";

  if (fillReached && !orderReached) {
    return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }
  if (!fill) {
    return orderReached
      ? { state: AUTO_CARD_SLOT_PENDING, detail: null }
      : { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }
  if (fill.state === "pending") {
    return { state: AUTO_CARD_SLOT_PENDING, detail: null };
  }
  if (fill.state === "absent") {
    return { state: AUTO_CARD_SLOT_ABSENT, detail: null };
  }
  if (!fillReached) return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  if (fill.measurement != null && fill.measurement !== "COMPLETE") {
    return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }

  const { requested, applied } = readEntryQuantities(cycle);
  if (requested == null || applied == null) {
    return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }
  if (applied < requested) {
    return {
      state: AUTO_CARD_PARTIAL,
      detail: `${applied}/${requested}`,
    };
  }
  if (applied === requested) {
    return {
      state: AUTO_CARD_SLOT_DONE,
      detail: `${applied}/${requested}`,
    };
  }
  return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
}

function positionSlot(
  account: AutoOperationCardAccount | null,
): Pick<AutoCardSlot, "state" | "detail"> {
  if (!account || account.positionLabel === AUTO_HOME_NO_DATA_LABEL) {
    return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }
  return { state: account.positionLabel, detail: null };
}

function moneySlot(
  account: AutoOperationCardAccount | null,
): Pick<AutoCardSlot, "state" | "detail"> {
  if (!account) return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  const cashKnown = account.cashLabel !== AUTO_HOME_NO_DATA_LABEL;
  const pnlKnown = account.pnlLabel !== AUTO_HOME_NO_DATA_LABEL;
  if (!cashKnown && !pnlKnown) {
    return { state: AUTO_HOME_NO_DATA_LABEL, detail: null };
  }
  const parts = [
    cashKnown ? `Efectivo simulado ${account.cashLabel}` : null,
    pnlKnown ? account.pnlLabel : null,
  ].filter((part): part is string => part != null);
  return { state: AUTO_CARD_ACCOUNT_SCOPE, detail: parts.join(" · ") };
}

export function buildAutoOperationCard(
  cycle: AutoBasicCycle,
  account: AutoOperationCardAccount | null = null,
): AutoOperationCardV1 {
  const symbol = cycle.instrumentId?.trim()
    ? cycle.instrumentId.trim()
    : AUTO_HOME_NO_DATA_LABEL;
  const bodies: Record<
    AutoCardSlotId,
    Pick<AutoCardSlot, "state" | "detail">
  > = {
    decision: { state: AUTO_HOME_NO_DATA_LABEL, detail: null },
    order: orderSlot(cycle),
    execution: executionSlot(cycle),
    simulation: { state: AUTO_HOME_NO_DATA_LABEL, detail: null },
    position: positionSlot(account),
    money: moneySlot(account),
  };

  return {
    cycleId: cycle.cycleId,
    symbol,
    headline: operationHappenedLabel(cycle),
    slots: SLOT_LABELS.map((slot) => ({
      id: slot.id,
      label: slot.label,
      state: bodies[slot.id].state,
      detail: bodies[slot.id].detail,
    })),
  };
}
