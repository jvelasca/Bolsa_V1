/**
 * U6 — preview de ticket SEMI en Confirm/drawer (margen / comisión).
 *
 * Solo lectura de datos ya disponibles (qty×precio, settings, summary).
 * No firma ni ejecuta; el camino Ejecutar en PAPER|LIVE no cambia.
 *
 * @see apps/web/src/features/trading/f3-ticket-preview-block.tsx
 * @see packages/shared/src/account-settings.ts (`calculateTradeFees`)
 */

import type { AccountSettings, TradeFeeBreakdownDto } from "@bolsa/shared";
import { calculateTradeFees } from "@bolsa/shared";
import {
  DECISION_ACTION_CHIP_LABEL,
  parseDecisionAction,
} from "@/features/trading/decision-package-chips";
import { coercePositivePrice } from "@/features/trading/f3-order-projection";

export type F3TicketSide = "buy" | "sell";

export type F3TicketPreviewView = {
  side: F3TicketSide;
  sideLabel: string;
  actionLabel: string;
  quantity: number;
  price: number;
  notional: number;
  currency: string;
  fees: TradeFeeBreakdownDto;
  /** Débito/crédito estimado en cash (buy: notional+fees; sell: notional−fees). */
  cashImpact: number;
  cashImpactLabel: string;
  commissionProfileLabel: string;
  /** Margen requerido estimado de la orden (notional / leverage). */
  marginRequired: number | null;
  marginUsed: number | null;
  freeMargin: number | null;
  /** Estimación post-fill de margen libre (fail soft si faltan datos). */
  freeMarginAfter: number | null;
};

const SIDE_LABEL: Record<F3TicketSide, string> = {
  buy: "Compra",
  sell: "Venta",
};

/**
 * Lado de fill informativo (espejo ligero de `_required_fill_side` backend).
 * Aperturas: long→buy / short→sell. Cierres: inverso del package.
 * `wait` / indeterminable → null (sin ticket).
 */
export function resolveF3TicketSide(input: {
  action?: unknown;
  packageAction?: unknown;
}): F3TicketSide | null {
  const action = parseDecisionAction(input.action);
  if (!action || action === "wait") return null;

  if (action === "recommend_long") return "buy";
  if (action === "recommend_short") return "sell";

  if (action === "exit_hint" || action === "reduce") {
    const pkg = parseDecisionAction(input.packageAction);
    if (pkg === "recommend_long") return "sell";
    if (pkg === "recommend_short") return "buy";
    return null;
  }
  return null;
}

/** Cantidad finita > 0, o null. */
export function coercePositiveQuantity(raw: unknown): number | null {
  if (typeof raw === "number") {
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  }
  if (typeof raw === "string" && raw.trim()) {
    const n = Number(raw.trim().replace(",", "."));
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  return null;
}

/** Notional: payload.notional si válido, si no qty×precio. */
export function resolveF3TicketNotional(input: {
  notional?: unknown;
  quantity: number;
  price: number;
}): number | null {
  const direct = coercePositivePrice(input.notional);
  if (direct != null) return direct;
  const n = input.quantity * input.price;
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** Margen requerido teórico (misma idea M-6: MV / leverage). */
export function resolveF3TicketMarginRequired(
  notional: number,
  leverage: number | null | undefined,
): number | null {
  if (!Number.isFinite(notional) || notional <= 0) return null;
  const lev =
    typeof leverage === "number" && Number.isFinite(leverage) && leverage > 0
      ? leverage
      : 1;
  const req = notional / lev;
  return Number.isFinite(req) ? req : null;
}

export function resolveF3TicketFreeMarginAfter(input: {
  side: F3TicketSide;
  freeMargin: number | null | undefined;
  marginRequired: number | null;
}): number | null {
  const free = input.freeMargin;
  const req = input.marginRequired;
  if (typeof free !== "number" || !Number.isFinite(free)) return null;
  if (req == null || !Number.isFinite(req)) return null;
  // Compra/apertura consume margen; venta/cierre lo libera (estimación UI).
  const after = input.side === "buy" ? free - req : free + req;
  return Number.isFinite(after) ? after : null;
}

/**
 * Vista completa del ticket preview.
 * Null si no hay lado, qty, precio o notional resolubles.
 */
export function resolveF3TicketPreview(input: {
  action?: unknown;
  packageAction?: unknown;
  quantity: unknown;
  price: unknown;
  notional?: unknown;
  settings: AccountSettings;
  currency: string;
  leverage?: number | null;
  marginUsed?: number | null;
  freeMargin?: number | null;
  isFxConversion?: boolean;
}): F3TicketPreviewView | null {
  const side = resolveF3TicketSide({
    action: input.action,
    packageAction: input.packageAction,
  });
  if (!side) return null;

  const quantity = coercePositiveQuantity(input.quantity);
  const price = coercePositivePrice(input.price);
  if (quantity == null || price == null) return null;

  const notional = resolveF3TicketNotional({
    notional: input.notional,
    quantity,
    price,
  });
  if (notional == null) return null;

  const fees = calculateTradeFees(notional, side, input.settings, {
    currency: input.currency,
    isFxConversion: Boolean(input.isFxConversion),
  });

  const cashImpact =
    side === "buy" ? notional + fees.total : notional - fees.total;

  const action =
    parseDecisionAction(input.action) ??
    parseDecisionAction(input.packageAction);
  const actionLabel = action ? DECISION_ACTION_CHIP_LABEL[action] : "";

  const marginRequired = resolveF3TicketMarginRequired(
    notional,
    input.leverage,
  );
  const freeMargin =
    typeof input.freeMargin === "number" && Number.isFinite(input.freeMargin)
      ? input.freeMargin
      : null;
  const marginUsed =
    typeof input.marginUsed === "number" && Number.isFinite(input.marginUsed)
      ? input.marginUsed
      : null;

  return {
    side,
    sideLabel: SIDE_LABEL[side],
    actionLabel,
    quantity,
    price,
    notional,
    currency: input.currency,
    fees,
    cashImpact,
    cashImpactLabel:
      side === "buy" ? "Total a debitar (est.)" : "Neto estimado en cuenta",
    commissionProfileLabel: input.settings.commission.label,
    marginRequired,
    marginUsed,
    freeMargin,
    freeMarginAfter: resolveF3TicketFreeMarginAfter({
      side,
      freeMargin,
      marginRequired,
    }),
  };
}
