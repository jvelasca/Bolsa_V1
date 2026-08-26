/**
 * DurableSubmitIntent — intento de envío durable (ADR-035 OR-2 · DEX-1).
 * Crash/restart: recorded → send_attempted → adapter.submit → UNKNOWN reconstruible.
 * Mapeo intent ↔ venueOrderId. ≠ PaperOrder status machine (OR-3).
 *
 * DEX-1: sendAttemptedDurable = fase/timestamp de envío (no «cualquier fila»).
 * Fila durable existente ⇒ no re-POST en Confirm aunque phase sea solo recorded.
 */

import {
  buildExecutionRecord,
  type ExecutionRecordV1,
} from "./execution-record.js";

export type SubmitIntentPhaseV1 =
  | "recorded"
  | "send_attempted"
  | "venue_bound"
  | "filled";

export type DurableSubmitIntentV1 = {
  decisionId: string;
  intentId: string;
  orderId: string;
  accountId: string;
  phase: SubmitIntentPhaseV1;
  venueOrderId: string | null;
  reason: string | null;
  venue: string;
  sendAttemptedAt: string | null;
};

export const SUBMIT_INTENT_KEY = "submitIntent";

const SEND_PHASES: ReadonlySet<SubmitIntentPhaseV1> = new Set([
  "send_attempted",
  "venue_bound",
  "filled",
]);

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** Antes de adapter.submit. Fase recorded, sin venue ack ni send mark. */
export function recordSubmitIntent(input: {
  decisionId: string;
  intentId: string;
  orderId: string;
  accountId: string;
  venue?: string;
}): DurableSubmitIntentV1 {
  return {
    decisionId: input.decisionId.trim(),
    intentId: input.intentId.trim(),
    orderId: input.orderId.trim(),
    accountId: input.accountId.trim(),
    phase: "recorded",
    venueOrderId: null,
    reason: "crash_before_venue_ack",
    venue: nonEmpty(input.venue) ?? "paper",
    sendAttemptedAt: null,
  };
}

/** Tras commit de recorded, antes de adapter.submit. */
export function markSendAttempted(
  intent: DurableSubmitIntentV1,
  at?: string | null,
): DurableSubmitIntentV1 {
  if (SEND_PHASES.has(intent.phase) && intent.phase !== "send_attempted") {
    return intent;
  }
  if (intent.phase === "send_attempted" && intent.sendAttemptedAt != null) {
    return intent;
  }
  const stamp = nonEmpty(at) ?? new Date().toISOString();
  return {
    ...intent,
    phase: "send_attempted",
    reason: intent.reason ?? "crash_before_venue_ack",
    sendAttemptedAt: intent.sendAttemptedAt ?? stamp,
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

/**
 * True si ya se marcó envío (fase o timestamp). Pure recorded = false.
 * Confirm no re-POST si hay fila durable; esa política no vive aquí.
 */
export function sendAttemptedDurable(
  intent: DurableSubmitIntentV1 | null | undefined,
): boolean {
  if (intent == null) return false;
  if (SEND_PHASES.has(intent.phase)) return true;
  return intent.sendAttemptedAt != null;
}

/** OR-2 — UNKNOWN reconstruible. Nunca error ni not_executed. */
export function reconstructUnknown(
  intent: DurableSubmitIntentV1,
): ExecutionRecordV1 {
  let reason: string;
  if (intent.phase === "recorded" || intent.phase === "send_attempted") {
    reason = intent.reason ?? "crash_before_venue_ack";
  } else if (intent.phase === "filled") {
    reason = intent.reason ?? "crash_after_fill_unconfirmed";
  } else {
    reason = intent.reason ?? "crash_after_venue_ack";
  }
  return buildExecutionRecord({ sendAttempted: true, exception: reason });
}
