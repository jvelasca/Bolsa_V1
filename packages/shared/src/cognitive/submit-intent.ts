/**
 * DurableSubmitIntent — intento de envío durable (ADR-035 OR-2).
 * Crash/restart: recorded antes de adapter.submit → UNKNOWN reconstruible.
 * Mapeo intent ↔ venueOrderId. ≠ PaperOrder status machine (OR-3).
 */

import {
  buildExecutionRecord,
  type ExecutionRecordV1,
} from "./execution-record.js";

export type SubmitIntentPhaseV1 = "recorded" | "venue_bound" | "filled";

export type DurableSubmitIntentV1 = {
  decisionId: string;
  intentId: string;
  orderId: string;
  accountId: string;
  phase: SubmitIntentPhaseV1;
  venueOrderId: string | null;
  reason: string | null;
};

export const SUBMIT_INTENT_KEY = "submitIntent";

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** Antes de adapter.submit. Fase recorded, sin venue. */
export function recordSubmitIntent(input: {
  decisionId: string;
  intentId: string;
  orderId: string;
  accountId: string;
}): DurableSubmitIntentV1 {
  return {
    decisionId: input.decisionId.trim(),
    intentId: input.intentId.trim(),
    orderId: input.orderId.trim(),
    accountId: input.accountId.trim(),
    phase: "recorded",
    venueOrderId: null,
    reason: "crash_before_venue_ack",
  };
}

/** Tras ack de venue. No es fill. Primer venue id gana. */
export function bindVenueOrder(
  intent: DurableSubmitIntentV1,
  venueOrderId?: string | null,
  reason?: string | null,
): DurableSubmitIntentV1 {
  if (intent.phase === "filled") {
    return intent;
  }
  const bound = nonEmpty(intent.venueOrderId) ?? nonEmpty(venueOrderId ?? null);
  return {
    ...intent,
    phase: bound ? "venue_bound" : intent.phase,
    venueOrderId: bound,
    reason: nonEmpty(reason ?? null) ?? "crash_after_venue_ack",
  };
}

/** Fill local conocido. No revierte. */
export function markSubmitFilled(
  intent: DurableSubmitIntentV1,
): DurableSubmitIntentV1 {
  if (intent.phase === "filled") {
    return intent;
  }
  return {
    ...intent,
    phase: "filled",
    reason: null,
  };
}

/** Cualquier fila durable = ya se intentó enviar (no re-POST). */
export function sendAttemptedDurable(
  intent: DurableSubmitIntentV1 | null | undefined,
): boolean {
  return intent != null;
}

/** OR-2 — UNKNOWN reconstruible. Nunca error ni not_executed. */
export function reconstructUnknown(
  intent: DurableSubmitIntentV1,
): ExecutionRecordV1 {
  let reason: string;
  if (intent.phase === "recorded") {
    reason = intent.reason ?? "crash_before_venue_ack";
  } else if (intent.phase === "filled") {
    reason = intent.reason ?? "crash_after_fill_unconfirmed";
  } else {
    reason = intent.reason ?? "crash_after_venue_ack";
  }
  return buildExecutionRecord({ sendAttempted: true, exception: reason });
}
