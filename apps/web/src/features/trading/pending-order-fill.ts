/**
 * P1-02 — un fill `skipped`/`unknown` NO es una orden ejecutada.
 *
 * `POST /api/pending-orders/:id/fill` devuelve seis desenlaces y **solo uno**
 * mueve dinero (`executed`, con `transactionId`). El resto —`expired`,
 * `rejected_by_gate`, `skipped` (live no cableado / rechazo del bróker),
 * `submitted` y `unknown`— comparten `transactionId: null`. El monitor
 * anunciaba «ejecutada @ precio» para todos ellos, así que la UI afirmaba una
 * ejecución sin transacción y el bucle de 15 s reintentaba indefinidamente.
 *
 * Este resolutor es la única fuente de la copia y del efecto sobre la orden. La
 * regla es cerrada: **sin `transactionId` no hay ejecución**, y un estado fuera
 * del vocabulario cae en `unknown` (nunca en `executed`).
 *
 * @see packages/py/application/src/bolsa_application/fill_pending_order.py:166-237
 * @see docs/engineering/auditoria-ui-operativa-profunda-2026-10-28.md §3.2 / §7 I-07
 */

export type PendingFillKind =
  | "executed"
  | "expired"
  | "rejected"
  | "skipped"
  | "unknown";

export type PendingFillVerdict = {
  kind: PendingFillKind;
  /** Solo `executed` con transacción: hay dinero movido. */
  executed: boolean;
  /** La orden ya no existe en el servidor (solo `executed` y `expired`). */
  removesOrder: boolean;
  /** ¿Reintentar en el siguiente ciclo? Un desenlace no ejecutado no se reintenta. */
  retryable: boolean;
  /** Aviso de primer nivel. Nunca dice «ejecutada» si no hay transacción. */
  copy: string;
  /** Motivo declarado por el servidor, sin reinterpretarlo. */
  reason: string | null;
  transactionId: string | null;
};

export type PendingFillInput = {
  status: string;
  reason?: string | null;
  transactionId?: string | null;
  side: "buy" | "sell";
  symbol: string;
  /** Precio de la orden ya formateado (el fill se ejecuta a ese precio). */
  priceLabel: string;
};

/** Traducción de los motivos del contrato. Un motivo nuevo se muestra crudo. */
const REASON_LABELS: Record<string, string> = {
  expired: "vencida",
  risk_veto: "veto de riesgo",
  live_not_wired: "el adaptador live no está conectado",
  live_rejected: "el bróker la rechazó",
  live_submitted_no_fill: "enviada al bróker sin confirmación de ejecución",
};

function reasonLabel(reason: string | null | undefined): string {
  if (!reason) return "sin motivo declarado";
  return REASON_LABELS[reason] ?? reason;
}

function sideLabel(side: "buy" | "sell"): string {
  return side === "buy" ? "compra" : "venta";
}

/**
 * Resuelve el desenlace del fill. Precedencia: un `executed` **sin** transacción
 * degrada a `unknown` (el contrato no se da por bueno).
 */
export function resolvePendingFill(
  input: PendingFillInput,
): PendingFillVerdict {
  const reason = input.reason ?? null;
  const transactionId = input.transactionId ?? null;
  const order = `${sideLabel(input.side)} ${input.symbol}`;

  if (input.status === "executed" && transactionId) {
    return {
      kind: "executed",
      executed: true,
      removesOrder: true,
      retryable: false,
      copy: `Orden ${order} ejecutada @ ${input.priceLabel}`,
      reason,
      transactionId,
    };
  }

  if (input.status === "expired") {
    return {
      kind: "expired",
      executed: false,
      removesOrder: true,
      retryable: false,
      copy: `Orden ${input.symbol} cancelada — vencida`,
      reason: reason ?? "expired",
      transactionId,
    };
  }

  if (input.status === "rejected_by_gate") {
    return {
      kind: "rejected",
      executed: false,
      removesOrder: false,
      retryable: false,
      copy: `Orden ${order} no ejecutada — ${reasonLabel(reason)}`,
      reason,
      transactionId,
    };
  }

  if (input.status === "skipped") {
    return {
      kind: "skipped",
      executed: false,
      removesOrder: false,
      retryable: false,
      copy: `Orden ${order} no ejecutada — ${reasonLabel(reason)}`,
      reason,
      transactionId,
    };
  }

  // `submitted` (mapea a `unknown` en el servidor), `unknown` y cualquier estado
  // fuera del vocabulario: fail-closed.
  return {
    kind: "unknown",
    executed: false,
    removesOrder: false,
    retryable: false,
    copy: `Orden ${order} sin confirmar — no consta ejecución (${reasonLabel(reason)})`,
    reason,
    transactionId,
  };
}
