/**
 * ExecutionState — proyección canónica de ciclo de orden/fill/UNKNOWN (V1.42 F2).
 * No es entidad, tabla ni segundo motor: compone PaperOrder · DurableSubmitIntent ·
 * pending_orders · ExecutionRecord · ledger paper_auto · OI-6/DEX-3.
 * Mercado / Hoy / Journal / Operaciones leen el mismo objeto.
 *
 * Spec: docs/engineering/spec-v142-operating-excellence-2026-08-31.md §A.4
 */

import type { ExecutionRecordV1 } from "./execution-record.js";
import type { MesaNextActionV1 } from "./mesa-next-action.js";
import { assertNever } from "./never.js";
import type { PaperOrderV1 } from "./paper-order.js";
import type { DurableSubmitIntentV1 } from "./submit-intent.js";

export type ExecutionLifecycleV1 =
  | "none"
  | "submit"
  | "in_flight"
  | "filled"
  | "failed"
  | "unknown"
  | "reconciled";

export type ExecutionOrderStateV1 =
  | "none"
  | "pending"
  | "accepted"
  | "partial"
  | "filled"
  | "rejected"
  | "cancelled"
  | "expired"
  | "unknown";

export type ExecutionFillStateV1 = "none" | "partial" | "complete";

/** Eco de protect — no autoridad. */
export type ExecutionProtectionStateV1 = "none" | "active" | "unknown";

/** Eco touched vs managed (H2) — no sello durable. */
export type ExecutionTargetStateV1 = "none" | "touched" | "managed" | "unknown";

/**
 * Trailing: hint ≠ applied. Hint nunca se auto-promueve (GP-A7).
 */
export type ExecutionTrailingStateV1 =
  | "inactive"
  | "hint"
  | "proposed"
  | "applied";

export type ExecutionReconciliationStateV1 =
  | "clean"
  | "attention"
  | "incident"
  | "unknown";

export type ExecutionStateSourceV1 =
  | "none"
  | "pending_order"
  | "paper_order"
  | "submit_intent"
  | "paper_auto_ledger";

export type ExecutionStateV1 = {
  instrumentId: string;
  asOf: string | null;
  lifecycle: ExecutionLifecycleV1;
  orderState: ExecutionOrderStateV1;
  fillState: ExecutionFillStateV1;
  protectionState: ExecutionProtectionStateV1;
  targetState: ExecutionTargetStateV1;
  trailingState: ExecutionTrailingStateV1;
  reconciliationState: ExecutionReconciliationStateV1;
  /** Passthrough; UNKNOWN fuerza review / ver operaciones — nunca reenviar. */
  nextAction: MesaNextActionV1 | null;
  orderId: string | null;
  intentId: string | null;
  decisionId: string | null;
  transactionId: string | null;
  source: ExecutionStateSourceV1;
};

export type ExecutionStateSurfaceSnapshotV1 = {
  lifecycle: ExecutionLifecycleV1;
  orderState: ExecutionOrderStateV1;
  fillState: ExecutionFillStateV1;
  reconciliationState: ExecutionReconciliationStateV1;
  trailingState: ExecutionTrailingStateV1;
  source: ExecutionStateSourceV1;
  orderId: string | null;
  intentId: string | null;
  nextActionKind: MesaNextActionV1["kind"] | null;
};

/** Hecho opcional de fill AUTO sin PaperOrder (Paper D → Router). */
export type PaperAutoLedgerFactV1 = {
  transactionId: string;
  instrumentId?: string;
};

export type BuildExecutionStateInputV1 = {
  instrumentId: string;
  asOf?: string | null;
  /** Germen UI: fila en GET /api/pending-orders. */
  pendingOrder?: boolean;
  paperOrder?: PaperOrderV1 | null;
  submitIntent?: DurableSubmitIntentV1 | null;
  executionRecord?: ExecutionRecordV1 | null;
  paperAutoLedger?: PaperAutoLedgerFactV1 | null;
  /** Hecho explícito de conciliación (no inventar). */
  orderReconciled?: boolean;
  /** OI-6 / DEX-3 eco — no es orderState. */
  portfolioReconStatus?: string | null;
  hasOpenIncident?: boolean;
  reconLookupFailed?: boolean;
  /** Eco protect / targets / trailing (opcionales). */
  protectionActive?: boolean;
  targetTouched?: boolean;
  targetManaged?: boolean;
  trailingHint?: boolean;
  trailingProposed?: boolean;
  trailingApplied?: boolean;
  /** CTA ya calculada; UNKNOWN la sustituye por review. */
  nextAction?: MesaNextActionV1 | null;
};

const REVIEW_OPS: MesaNextActionV1 = {
  kind: "review",
  label: "Ver operaciones",
  allowsEntry: false,
};

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function mapReconciliation(
  input: BuildExecutionStateInputV1,
): ExecutionReconciliationStateV1 {
  if (input.reconLookupFailed) return "unknown";
  if (input.hasOpenIncident) return "incident";
  const s = String(input.portfolioReconStatus ?? "")
    .trim()
    .toLowerCase();
  if (s === "drift") return "incident";
  if (s === "clean" || s === "ok" || s === "") return "clean";
  if (!s) return "clean";
  return "attention";
}

function mapProtection(
  input: BuildExecutionStateInputV1,
): ExecutionProtectionStateV1 {
  if (input.protectionActive === true) return "active";
  if (input.protectionActive === false) return "none";
  return "none";
}

function mapTarget(input: BuildExecutionStateInputV1): ExecutionTargetStateV1 {
  if (input.targetManaged === true) return "managed";
  if (input.targetTouched === true) return "touched";
  return "none";
}

/**
 * Hint never auto-promotes to applied (GP-A7).
 * applied only when trailingApplied fact is true.
 */
function mapTrailing(
  input: BuildExecutionStateInputV1,
): ExecutionTrailingStateV1 {
  if (input.trailingApplied === true) return "applied";
  if (input.trailingProposed === true) return "proposed";
  if (input.trailingHint === true) return "hint";
  return "inactive";
}

type OrderCycle = {
  lifecycle: ExecutionLifecycleV1;
  orderState: ExecutionOrderStateV1;
  fillState: ExecutionFillStateV1;
  source: ExecutionStateSourceV1;
  orderId: string | null;
  intentId: string | null;
  decisionId: string | null;
  transactionId: string | null;
};

/**
 * Precedencia (spec F2 / plan):
 * 1. UNKNOWN beats "looks pending"
 * 2. Confirmed fill beats stale intent
 * 3. PARTIAL
 * 4. REJECTED / CANCELLED / EXPIRED
 * 5. Intent recorded → submit; send_attempted/venue_bound or SUBMITTED/ACK → in_flight
 * 6. pending_orders only → in_flight/pending
 * 7. none
 * 8. reconciled overlays when fact says so
 */
function resolveOrderCycle(input: BuildExecutionStateInputV1): OrderCycle {
  const paper = input.paperOrder ?? null;
  const intent = input.submitIntent ?? null;
  const record = input.executionRecord ?? null;
  const auto = input.paperAutoLedger ?? null;

  const refs = {
    orderId: nonEmpty(paper?.orderId) ?? nonEmpty(intent?.orderId),
    intentId: nonEmpty(paper?.intentId) ?? nonEmpty(intent?.intentId),
    decisionId: nonEmpty(intent?.decisionId),
    transactionId:
      nonEmpty(paper?.transactionId) ??
      nonEmpty(record?.transactionId) ??
      nonEmpty(auto?.transactionId),
  };

  const filledPaper = paper?.status === "FILLED";
  const filledIntent = intent?.phase === "filled";
  const filledRecord = record?.outcome === "executed";
  const filledAuto = Boolean(nonEmpty(auto?.transactionId));
  const confirmedFill =
    filledPaper || filledIntent || filledRecord || filledAuto;

  // 2 before 1 when fill is confirmed (fill wins over stale unknown intent).
  if (confirmedFill) {
    let source: ExecutionStateSourceV1 = "none";
    if (filledPaper) source = "paper_order";
    else if (filledIntent) source = "submit_intent";
    else if (filledAuto) source = "paper_auto_ledger";
    else source = "paper_order";
    return {
      lifecycle: input.orderReconciled ? "reconciled" : "filled",
      orderState: "filled",
      fillState: "complete",
      source,
      ...refs,
      transactionId: refs.transactionId,
    };
  }

  const unknownPaper = paper?.status === "UNKNOWN";
  const unknownRecord = record?.outcome === "unknown";
  const intentInFlight =
    intent != null &&
    (intent.phase === "recorded" ||
      intent.phase === "send_attempted" ||
      intent.phase === "venue_bound");
  // Intent without confirmed fill → UNKNOWN (OR-2 crash path). recorded alone
  // is also unknown-capable after crash; plan step 1 says unknown beats pending.
  // Exception: recorded without sendAttempted and without paper UNKNOWN and
  // without executionRecord unknown maps to submit (step 5) — only when we
  // have no crash signal. Crash signal = sendAttemptedAt OR record unknown OR
  // paper UNKNOWN OR phase send_attempted/venue_bound.
  const crashSignal =
    unknownPaper ||
    unknownRecord ||
    (intent != null &&
      (intent.phase === "send_attempted" ||
        intent.phase === "venue_bound" ||
        (intent.phase === "recorded" && intent.sendAttemptedAt != null)));

  if (crashSignal || (intentInFlight && unknownRecord)) {
    return {
      lifecycle: input.orderReconciled ? "reconciled" : "unknown",
      orderState: "unknown",
      fillState: "none",
      source: unknownPaper
        ? "paper_order"
        : intent
          ? "submit_intent"
          : "paper_order",
      ...refs,
    };
  }

  // Intent recorded (pre-send, no crash signal) → submit
  if (intent?.phase === "recorded") {
    return {
      lifecycle: "submit",
      orderState: "pending",
      fillState: "none",
      source: "submit_intent",
      ...refs,
    };
  }

  if (paper?.status === "PARTIAL") {
    return {
      lifecycle: "in_flight",
      orderState: "partial",
      fillState: "partial",
      source: "paper_order",
      ...refs,
    };
  }

  if (paper?.status === "REJECTED") {
    return {
      lifecycle: "failed",
      orderState: "rejected",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }
  if (paper?.status === "CANCELLED") {
    return {
      lifecycle: "failed",
      orderState: "cancelled",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }
  if (paper?.status === "EXPIRED") {
    return {
      lifecycle: "failed",
      orderState: "expired",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }

  if (record?.outcome === "error") {
    return {
      lifecycle: "failed",
      orderState: "rejected",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }

  if (paper?.status === "ACK") {
    return {
      lifecycle: "in_flight",
      orderState: "accepted",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }
  if (paper?.status === "SUBMITTED" || paper?.status === "CREATED") {
    return {
      lifecycle: "in_flight",
      orderState: "pending",
      fillState: "none",
      source: "paper_order",
      ...refs,
    };
  }

  if (input.pendingOrder) {
    return {
      lifecycle: "in_flight",
      orderState: "pending",
      fillState: "none",
      source: "pending_order",
      ...refs,
    };
  }

  return {
    lifecycle: "none",
    orderState: "none",
    fillState: "none",
    source: "none",
    orderId: null,
    intentId: null,
    decisionId: null,
    transactionId: null,
  };
}

function resolveNextAction(
  cycle: OrderCycle,
  passthrough: MesaNextActionV1 | null | undefined,
): MesaNextActionV1 | null {
  if (cycle.lifecycle === "unknown") return REVIEW_OPS;
  if (
    cycle.lifecycle === "in_flight" ||
    cycle.lifecycle === "submit" ||
    cycle.orderState === "partial"
  ) {
    return REVIEW_OPS;
  }
  return passthrough ?? null;
}

export function buildExecutionState(
  input: BuildExecutionStateInputV1,
): ExecutionStateV1 {
  const instrumentId = input.instrumentId.trim();
  const cycle = resolveOrderCycle(input);
  return {
    instrumentId,
    asOf: nonEmpty(input.asOf ?? null),
    lifecycle: cycle.lifecycle,
    orderState: cycle.orderState,
    fillState: cycle.fillState,
    protectionState: mapProtection(input),
    targetState: mapTarget(input),
    trailingState: mapTrailing(input),
    reconciliationState: mapReconciliation(input),
    nextAction: resolveNextAction(cycle, input.nextAction),
    orderId: cycle.orderId,
    intentId: cycle.intentId,
    decisionId: cycle.decisionId,
    transactionId: cycle.transactionId,
    source: cycle.source,
  };
}

/**
 * Compatibilidad con el booleano `orderPending` / `orderPendingFill`.
 * In-flight = pending | accepted | partial | unknown (no terminal filled/failed/none).
 */
export function isOrderInFlight(state: ExecutionStateV1): boolean {
  if (state.lifecycle === "none" || state.lifecycle === "filled") return false;
  if (state.lifecycle === "failed" && state.orderState !== "partial")
    return false;
  if (state.lifecycle === "reconciled" && state.orderState === "filled")
    return false;
  return (
    state.lifecycle === "submit" ||
    state.lifecycle === "in_flight" ||
    state.lifecycle === "unknown" ||
    state.orderState === "partial"
  );
}

export function executionStateSurfaceSnapshot(
  state: ExecutionStateV1,
): ExecutionStateSurfaceSnapshotV1 {
  return {
    lifecycle: state.lifecycle,
    orderState: state.orderState,
    fillState: state.fillState,
    reconciliationState: state.reconciliationState,
    trailingState: state.trailingState,
    source: state.source,
    orderId: state.orderId,
    intentId: state.intentId,
    nextActionKind: state.nextAction?.kind ?? null,
  };
}

/**
 * Copy de producto para ciclo de orden. Una frase; sin BUY.
 * Complementa formatExecutionHintCopy (recommended_not_executed).
 */
export function formatExecutionStateCopy(
  state: ExecutionStateV1,
): string | null {
  switch (state.lifecycle) {
    case "unknown":
      return "Orden desconocida — no duplicar. Revisar / reconciliar.";
    case "submit":
      return "Envío registrado — fill pendiente.";
    case "in_flight":
      if (state.orderState === "partial") {
        return "Fill parcial — orden en vuelo.";
      }
      if (state.orderState === "accepted") {
        return "Orden aceptada — fill pendiente.";
      }
      return "Orden en vuelo — fill pendiente.";
    case "filled":
      return null;
    case "failed":
      if (state.orderState === "rejected") return "Orden rechazada.";
      if (state.orderState === "cancelled") return "Orden cancelada.";
      if (state.orderState === "expired") return "Orden caducada.";
      return "Orden fallida.";
    case "reconciled":
      return "Orden conciliada.";
    case "none":
      return null;
    default:
      return assertNever(state.lifecycle);
  }
}
