/**
 * LiveOrder — XL-3 LIVE execution state machine (domain only).
 * UNKNOWN first-class · no automatic re-POST · PARTIAL qty honesty.
 * Mirror of bolsa_analytics.cognitive.live_order.
 *
 * Cantidades: el espejo TS usa `number` para la proyección de UI/red SOLO.
 * La fuente de verdad de cantidad es Decimal(6dp) en el dominio PY y en el
 * `NUMERIC(18,6)` de `live_orders` (H1 V2.13): aquí cada `quantity`/`filled`/
 * `remaining` se trata como valor redondeado a 6 decimales; NO se hace aquí
 * aritmética financiera de libro (comisiones/precio medio) porque JS `number`
 * es binario (float). Toda escritura durable pasa por PY/SQL (Decimal exacto).
 */

export type LiveOrderStatusV1 =
  | "AUTHORIZED"
  | "SUBMITTING"
  | "SUBMITTED"
  | "WORKING"
  | "PARTIAL"
  | "FILLED"
  | "REJECTED"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "UNKNOWN";

export type LiveOrderSideV1 = "buy" | "sell";
export type LiveOrderVenueV1 = "LIVE";

export const LIVE_ORDER_KEY = "liveOrder";

const TERMINAL: ReadonlySet<LiveOrderStatusV1> = new Set([
  "FILLED",
  "REJECTED",
  "CANCELLED",
]);

/**
 * Cancelación honesta (intención vs resultado): una decisión local = CANCEL_REQUESTED
 * (NO terminal, sigue in-flight); CANCELLED (terminal) solo llega cuando el broker
 * confirma. Espejo de live_order.py.
 */
/** UNKNOWN → SUBMITTING intentionally ABSENT (no re-POST). */
export const ALLOWED_LIVE_ORDER_TRANSITIONS: Readonly<
  Record<LiveOrderStatusV1, ReadonlySet<LiveOrderStatusV1>>
> = {
  AUTHORIZED: new Set([
    "SUBMITTING",
    "REJECTED",
    "CANCELLED",
    "CANCEL_REQUESTED",
  ]),
  SUBMITTING: new Set(["REJECTED", "UNKNOWN", "SUBMITTED", "CANCEL_REQUESTED"]),
  SUBMITTED: new Set([
    "WORKING",
    "UNKNOWN",
    "CANCELLED",
    "REJECTED",
    "CANCEL_REQUESTED",
  ]),
  WORKING: new Set([
    "PARTIAL",
    "FILLED",
    "UNKNOWN",
    "CANCELLED",
    "REJECTED",
    "CANCEL_REQUESTED",
  ]),
  PARTIAL: new Set(["FILLED", "UNKNOWN", "CANCELLED", "CANCEL_REQUESTED"]),
  FILLED: new Set(),
  REJECTED: new Set(),
  CANCEL_REQUESTED: new Set([
    "CANCELLED",
    "UNKNOWN",
    "REJECTED",
    "FILLED",
    "WORKING",
  ]),
  CANCELLED: new Set(),
  UNKNOWN: new Set([
    "WORKING",
    "REJECTED",
    "FILLED",
    "PARTIAL",
    "CANCELLED",
    "CANCEL_REQUESTED",
  ]),
};

export type LiveOrderV1 = {
  orderId: string;
  status: LiveOrderStatusV1;
  venue: LiveOrderVenueV1;
  instrumentId: string;
  side: LiveOrderSideV1;
  quantity: number;
  filledQuantity: number;
  remainingQuantity: number;
  venueOrderId: string | null;
  intentId: string | null;
  financialApplyCount: number;
  accountId?: string | null;
};

export function buildLiveOrder(input: {
  orderId: string;
  instrumentId: string;
  side: LiveOrderSideV1;
  quantity: number;
  intentId?: string | null;
  status?: LiveOrderStatusV1;
  accountId?: string | null;
}): LiveOrderV1 {
  const qty = Number(input.quantity);
  return {
    orderId: input.orderId,
    status: input.status ?? "AUTHORIZED",
    venue: "LIVE",
    instrumentId: input.instrumentId,
    side: input.side,
    quantity: qty,
    filledQuantity: 0,
    remainingQuantity: qty,
    venueOrderId: null,
    intentId: input.intentId ?? null,
    financialApplyCount: 0,
    accountId: input.accountId ?? null,
  };
}

export function canTransitionLiveOrder(
  current: LiveOrderStatusV1,
  next: LiveOrderStatusV1,
): boolean {
  if (TERMINAL.has(current) && next !== current) return false;
  return ALLOWED_LIVE_ORDER_TRANSITIONS[current]?.has(next) ?? false;
}

export class LiveOrderTransitionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LiveOrderTransitionError";
  }
}

export function transitionLiveOrder(
  order: LiveOrderV1,
  next: LiveOrderStatusV1,
  opts?: {
    filledQuantity?: number;
    venueOrderId?: string | null;
    applyFinancial?: boolean;
  },
): LiveOrderV1 {
  if (!canTransitionLiveOrder(order.status, next)) {
    throw new LiveOrderTransitionError(
      `live_order forbidden: ${order.status} → ${next}`,
    );
  }

  let filled = order.filledQuantity;
  let remaining = order.remainingQuantity;
  if (opts?.filledQuantity != null) {
    filled = Number(opts.filledQuantity);
    if (filled < 0 || filled > order.quantity + 1e-9) {
      throw new LiveOrderTransitionError("filled_quantity out of range");
    }
    remaining = Math.max(0, order.quantity - filled);
  }

  if (next === "PARTIAL" && filled <= 0) {
    throw new LiveOrderTransitionError("PARTIAL requires filled_quantity > 0");
  }
  if (next === "PARTIAL" && remaining <= 0) {
    throw new LiveOrderTransitionError(
      "PARTIAL requires remaining_quantity > 0",
    );
  }
  if (next === "FILLED") {
    if (opts?.filledQuantity == null) {
      // FILLED sin detalle de broker → el total capturado es la orden entera.
      filled = order.quantity;
    } else if (Math.abs(filled - order.quantity) > 1e-9) {
      // Terminal FILLED significa que la cantidad total de la orden se capturó.
      // filled < quantity por el broker = desacuerdo broker-truth; quedamos
      // fail-closed para reconcil (raise) en vez de un FILLED artificial.
      throw new LiveOrderTransitionError(
        `FILLED requires filled_quantity == quantity (order ${order.quantity}, broker ${filled}) · reconciliation required`,
      );
    }
    remaining = 0;
  }

  let applyCount = order.financialApplyCount;
  if (opts?.applyFinancial) {
    if (next !== "FILLED") {
      throw new LiveOrderTransitionError(
        "financial apply only allowed on FILLED",
      );
    }
    // Duplicate FILLED events: only one financial effect. The counter is a
    // monotonic "first financial application recorded" marker: it never
    // decreases, so an already-applied marker stays as-is (idempotent).
    if (applyCount < 1) {
      applyCount = 1;
    }
  }

  return {
    orderId: order.orderId,
    status: next,
    venue: "LIVE",
    instrumentId: order.instrumentId,
    side: order.side,
    quantity: order.quantity,
    filledQuantity: filled,
    remainingQuantity: remaining,
    venueOrderId:
      opts?.venueOrderId !== undefined ? opts.venueOrderId : order.venueOrderId,
    intentId: order.intentId,
    financialApplyCount: applyCount,
    accountId: order.accountId ?? null,
  };
}

export function forbidExecuteTradeForPartial(order: LiveOrderV1): void {
  if (order.status === "PARTIAL") {
    throw new LiveOrderTransitionError(
      "execute_trade forbidden on PARTIAL · use filled_quantity only (PARKED)",
    );
  }
}

export function forbidRepostFromUnknown(order: LiveOrderV1): void {
  if (order.status === "UNKNOWN") {
    throw new LiveOrderTransitionError(
      "UNKNOWN forbids re-POST · query_broker only",
    );
  }
}
