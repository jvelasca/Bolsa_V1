/**
 * LiveOrder — XL-3 LIVE execution state machine (domain only).
 * UNKNOWN first-class · no automatic re-POST · PARTIAL qty honesty.
 * Mirror of bolsa_analytics.cognitive.live_order.
 */

export type LiveOrderStatusV1 =
  | "AUTHORIZED"
  | "SUBMITTING"
  | "SUBMITTED"
  | "WORKING"
  | "PARTIAL"
  | "FILLED"
  | "REJECTED"
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

/** UNKNOWN → SUBMITTING intentionally ABSENT (no re-POST). */
export const ALLOWED_LIVE_ORDER_TRANSITIONS: Readonly<
  Record<LiveOrderStatusV1, ReadonlySet<LiveOrderStatusV1>>
> = {
  AUTHORIZED: new Set(["SUBMITTING", "REJECTED", "CANCELLED"]),
  SUBMITTING: new Set(["REJECTED", "UNKNOWN", "SUBMITTED"]),
  SUBMITTED: new Set(["WORKING", "UNKNOWN", "CANCELLED", "REJECTED"]),
  WORKING: new Set(["PARTIAL", "FILLED", "UNKNOWN", "CANCELLED", "REJECTED"]),
  PARTIAL: new Set(["FILLED", "UNKNOWN", "CANCELLED"]),
  FILLED: new Set(),
  REJECTED: new Set(),
  CANCELLED: new Set(),
  UNKNOWN: new Set(["WORKING", "REJECTED", "FILLED", "PARTIAL", "CANCELLED"]),
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
    filled = opts?.filledQuantity == null ? order.quantity : filled;
    remaining = 0;
  }

  let applyCount = order.financialApplyCount;
  if (opts?.applyFinancial) {
    if (next !== "FILLED") {
      throw new LiveOrderTransitionError(
        "financial apply only allowed on FILLED",
      );
    }
    applyCount = 1;
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
