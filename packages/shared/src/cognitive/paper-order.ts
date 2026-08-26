/**
 * PaperOrder — ciclo paper CREATED→…→FILLED + ramas (ADR-034 OI-4 · ADR-035 OR-3).
 * CREATED ≠ FILLED. Orden creada no es fill.
 * OR-3 amplía el Literal; OI-4 nacimiento CREATED se conserva.
 * ≠ OrderIntent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker.
 * ≠ DurableSubmitIntent (OR-2).
 *
 * OR-1 (ADR-035): orderId estable derivado de decisionId cuando se pasa explícito.
 */

import { createRandomId } from "../create-id.js";

export type PaperOrderStatusV1 =
  | "CREATED"
  | "SUBMITTED"
  | "ACK"
  | "PARTIAL"
  | "FILLED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "UNKNOWN";

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
  filledQuantity: number | null;
};

export const PAPER_ORDER_KEY = "paperOrder";

const TERMINAL: ReadonlySet<PaperOrderStatusV1> = new Set([
  "FILLED",
  "REJECTED",
  "CANCELLED",
  "EXPIRED",
]);

/** Grafo OR-3. CREATED→FILLED directo = atajo paper OI-4. */
export const ALLOWED_PAPER_ORDER_TRANSITIONS: Readonly<
  Record<PaperOrderStatusV1, ReadonlySet<PaperOrderStatusV1>>
> = {
  CREATED: new Set([
    "SUBMITTED",
    "ACK",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "UNKNOWN",
  ]),
  SUBMITTED: new Set([
    "ACK",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "UNKNOWN",
  ]),
  ACK: new Set([
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "UNKNOWN",
  ]),
  PARTIAL: new Set(["FILLED", "CANCELLED", "EXPIRED", "UNKNOWN"]),
  UNKNOWN: new Set([
    "ACK",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
  ]),
  FILLED: new Set(),
  REJECTED: new Set(),
  CANCELLED: new Set(),
  EXPIRED: new Set(),
};

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

/** OR-1 — identidad de orden paper estable (retry = mismo ORD-). */
export function stableOrderIdFromDecision(decisionId: string): string {
  const slug = decisionId
    .trim()
    .replace(/[^a-zA-Z0-9-_]/g, "")
    .slice(0, 48);
  return slug ? `ORD-${slug}` : `ORD-missing`;
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
    filledQuantity: null,
  };
}

export function canTransitionPaperOrder(
  from: PaperOrderStatusV1,
  to: PaperOrderStatusV1,
): boolean {
  if (from === to) {
    return TERMINAL.has(from) || from === "UNKNOWN";
  }
  return ALLOWED_PAPER_ORDER_TRANSITIONS[from]?.has(to) ?? false;
}

export type TransitionPaperOrderOpts = {
  transactionId?: string | null;
  filledQuantity?: number | null;
};

/** Aplica transición legal. Ilegal → throw. Terminal idempotente (misma status). */
export function transitionPaperOrder(
  order: PaperOrderV1,
  toStatus: PaperOrderStatusV1,
  opts?: TransitionPaperOrderOpts,
): PaperOrderV1 {
  if (order.status === toStatus) {
    if (TERMINAL.has(order.status) || order.status === "UNKNOWN") {
      return order;
    }
    throw new Error(`paper_order_noop_not_terminal:${order.status}`);
  }
  if (!canTransitionPaperOrder(order.status, toStatus)) {
    throw new Error(
      `paper_order_illegal_transition:${order.status}->${toStatus}`,
    );
  }

  let nextFilled = order.filledQuantity;
  let nextTx = order.transactionId;
  const transactionId = opts?.transactionId;
  const filledQuantity = opts?.filledQuantity;

  if (toStatus === "PARTIAL") {
    const qty =
      typeof filledQuantity === "number" ? filledQuantity : Number.NaN;
    if (!(qty > 0) || !(qty < order.quantity)) {
      throw new Error("paper_order_partial_requires_qty");
    }
    nextFilled = qty;
  } else if (toStatus === "FILLED") {
    nextTx =
      transactionId !== undefined
        ? nonEmpty(transactionId ?? null)
        : order.transactionId;
    nextFilled =
      typeof filledQuantity === "number" ? filledQuantity : order.quantity;
  } else if (transactionId !== undefined) {
    nextTx = nonEmpty(transactionId ?? null);
  }

  return {
    ...order,
    status: toStatus,
    venue: "PAPER",
    transactionId: nextTx,
    filledQuantity: nextFilled,
  };
}

/** → FILLED desde estado abierto. FILLED idempotente (primer fill gana). No revierte. */
export function applyPaperOrderFill(
  order: PaperOrderV1,
  transactionId?: string | null,
): PaperOrderV1 {
  if (order.status === "FILLED") {
    return order;
  }
  if (
    order.status === "REJECTED" ||
    order.status === "CANCELLED" ||
    order.status === "EXPIRED"
  ) {
    throw new Error(`paper_order_fill_from_terminal:${order.status}`);
  }
  return transitionPaperOrder(order, "FILLED", {
    transactionId,
    filledQuantity: order.quantity,
  });
}

/** Copy de mesa: CREATED nunca se lee como cubierta. */
export function paperOrderStatusCopy(status: PaperOrderStatusV1): string {
  const copies: Record<PaperOrderStatusV1, string> = {
    CREATED: "Orden creada — fill no confirmado",
    SUBMITTED: "Orden enviada — pendiente de ack",
    ACK: "Orden aceptada por el venue — fill pendiente",
    PARTIAL: "Orden parcialmente cubierta",
    FILLED: "Orden cubierta (paper)",
    REJECTED: "Orden rechazada",
    CANCELLED: "Orden cancelada",
    EXPIRED: "Orden expirada",
    UNKNOWN: "Estado de orden desconocido — no asumir fill",
  };
  return copies[status];
}
