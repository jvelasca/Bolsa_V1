/**
 * PaperOrder — ciclo paper CREATED→FILLED (ADR-034 OI-4).
 * CREATED ≠ FILLED. Orden creada no es fill.
 * ≠ OrderIntent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker.
 */

import { createRandomId } from "../create-id.js";

export type PaperOrderStatusV1 = "CREATED" | "FILLED";

export type PaperOrderSideV1 = "buy" | "sell";

export type PaperOrderVenueV1 = "PAPER";

export type PaperOrderV1 = {
  orderId: string;
  status: PaperOrderStatusV1;
  venue: PaperOrderVenueV1;
  instrumentId: string;
  side: PaperOrderSideV1;
  quantity: number;
  transactionId: string | null;
  intentId: string | null;
};

export const PAPER_ORDER_KEY = "paperOrder";

export type BuildPaperOrderInputV1 = {
  instrumentId: string;
  side: PaperOrderSideV1;
  quantity: number;
  orderId?: string | null;
  intentId?: string | null;
};

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** Nacimiento: siempre CREATED, venue PAPER, sin fill. */
export function buildPaperOrder(input: BuildPaperOrderInputV1): PaperOrderV1 {
  const orderId =
    nonEmpty(input.orderId ?? null) ?? `ORD-${createRandomId().slice(0, 12)}`;
  return {
    orderId,
    status: "CREATED",
    venue: "PAPER",
    instrumentId: input.instrumentId.trim(),
    side: input.side,
    quantity: input.quantity,
    transactionId: null,
    intentId: nonEmpty(input.intentId ?? null),
  };
}

/** CREATED→FILLED. FILLED es idempotente (primer fill gana). No revierte. */
export function applyPaperOrderFill(
  order: PaperOrderV1,
  transactionId?: string | null,
): PaperOrderV1 {
  if (order.status === "FILLED") {
    return order;
  }
  return {
    ...order,
    status: "FILLED",
    venue: "PAPER",
    transactionId: nonEmpty(transactionId ?? null),
  };
}

/** Copy de mesa: CREATED nunca se lee como cubierta. */
export function paperOrderStatusCopy(status: PaperOrderStatusV1): string {
  if (status === "FILLED") {
    return "Orden cubierta (paper)";
  }
  return "Orden creada — fill no confirmado";
}
