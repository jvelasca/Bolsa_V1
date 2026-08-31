/**
 * TradeStory — proyección canónica timeline idea→cierre (V1.42 F4).
 * No es entidad, tabla ni TradeStoryEngine: compone hechos caller-supplied
 * (study · journal · proposal · fills · revisions · ExecutionState · facts).
 * Journal consume la historia; no sustituye Tesis / Evolución / Historial técnico.
 *
 * Spec: docs/engineering/spec-v142-operating-excellence-2026-08-31.md §A.6
 *
 * Honesty: omit event without asOf. Trailing hint ≠ trailing_applied.
 * Thin DTO gaps (revisions / T1 stamps) → fail-closed, no fiction.
 */

import type { DecisionJournalEntryV1 } from "./decision-journal.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { ExecutionStateV1 } from "./execution-state.js";
import type { OrderProposalV1 } from "./order-proposal.js";
import type { PaperOrderV1 } from "./paper-order.js";
import type { PositionFillV1, PositionStateV1 } from "./position-state.js";
import type { DurableSubmitIntentV1 } from "./submit-intent.js";

export type TradeStoryEventKindV1 =
  | "estudio"
  | "preparada"
  | "trigger"
  | "propuesta"
  | "confirmacion"
  | "fill"
  | "fill_partial"
  | "stop_updated"
  | "t1"
  | "t2"
  | "trailing_applied"
  | "cierre"
  | "bloqueada"
  | "caducada"
  | "unknown_order"
  | "reconciled";

export type TradeStoryEventSourceV1 =
  | "journal_study"
  | "journal_entry"
  | "order_proposal"
  | "decision_session"
  | "position_fill"
  | "position_revision"
  | "position_target"
  | "submit_intent"
  | "paper_order"
  | "execution_state"
  | "transaction"
  | "caller";

export type TradeStoryEventRefsV1 = {
  decisionId?: string | null;
  sessionId?: string | null;
  orderId?: string | null;
  intentId?: string | null;
  revisionId?: string | null;
  transactionId?: string | null;
  positionId?: string | null;
  entryId?: string | null;
};

export type TradeStoryEventV1 = {
  eventId: string;
  kind: TradeStoryEventKindV1;
  /** Required — no event without clock. */
  asOf: string;
  label: string;
  detail?: string | null;
  source: TradeStoryEventSourceV1;
  refs: TradeStoryEventRefsV1;
};

export type TradeStoryV1 = {
  instrumentId: string;
  decisionId: string | null;
  positionId: string | null;
  asOf: string | null;
  events: TradeStoryEventV1[];
};

export type TradeStorySurfaceSnapshotV1 = {
  eventKinds: TradeStoryEventKindV1[];
  firstAsOf: string | null;
  lastAsOf: string | null;
  count: number;
  decisionId: string | null;
  positionId: string | null;
};

export type TradeStoryCallerFactV1 = {
  kind: TradeStoryEventKindV1;
  asOf: string;
  detail?: string | null;
  refs?: TradeStoryEventRefsV1 | null;
  eventId?: string | null;
};

export type TradeStoryTransactionFactV1 = {
  id: string;
  type: "buy" | "sell";
  executedAt: string;
  quantity?: number | null;
};

export type BuildTradeStoryInputV1 = {
  instrumentId: string;
  decisionId?: string | null;
  positionId?: string | null;
  asOf?: string | null;
  study?: Pick<
    DecisionJournalStudyViewV1,
    | "studiedAt"
    | "sessionId"
    | "decisionId"
    | "tradePlanStatus"
    | "instrumentId"
  > | null;
  journalEntries?: DecisionJournalEntryV1[] | null;
  orderProposal?: OrderProposalV1 | null;
  positionState?: PositionStateV1 | null;
  fills?: PositionFillV1[] | null;
  transactions?: TradeStoryTransactionFactV1[] | null;
  submitIntent?: DurableSubmitIntentV1 | null;
  paperOrder?: PaperOrderV1 | null;
  executionState?: ExecutionStateV1 | null;
  /** Explicit caller facts when wire is thin — still require asOf. */
  facts?: TradeStoryCallerFactV1[] | null;
};

const LABELS: Record<TradeStoryEventKindV1, string> = {
  estudio: "Estudio",
  preparada: "Preparada",
  trigger: "Trigger",
  propuesta: "Propuesta",
  confirmacion: "Confirmación",
  fill: "Fill",
  fill_partial: "Fill parcial",
  stop_updated: "Stop actualizado",
  t1: "T1",
  t2: "T2",
  trailing_applied: "Trailing aplicado",
  cierre: "Cierre",
  bloqueada: "Bloqueada",
  caducada: "Caducada",
  unknown_order: "Orden desconocida",
  reconciled: "Conciliada",
};

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function isValidAsOf(value: string | null | undefined): value is string {
  const s = nonEmpty(value);
  if (!s) return false;
  const t = Date.parse(s);
  return Number.isFinite(t);
}

export function formatTradeStoryEventLabel(
  kind: TradeStoryEventKindV1,
): string {
  return LABELS[kind];
}

function makeEventId(
  kind: TradeStoryEventKindV1,
  asOf: string,
  source: TradeStoryEventSourceV1,
  refs: TradeStoryEventRefsV1,
): string {
  const parts = [
    kind,
    asOf,
    source,
    refs.entryId ?? "",
    refs.revisionId ?? "",
    refs.transactionId ?? "",
    refs.orderId ?? "",
    refs.intentId ?? "",
    refs.sessionId ?? "",
    refs.decisionId ?? "",
    refs.positionId ?? "",
  ];
  return parts.join("|");
}

function pushEvent(
  bag: TradeStoryEventV1[],
  partial: {
    kind: TradeStoryEventKindV1;
    asOf: string;
    source: TradeStoryEventSourceV1;
    detail?: string | null;
    refs?: TradeStoryEventRefsV1;
    eventId?: string | null;
  },
): void {
  if (!isValidAsOf(partial.asOf)) return;
  const refs = partial.refs ?? {};
  const eventId =
    nonEmpty(partial.eventId) ??
    makeEventId(partial.kind, partial.asOf, partial.source, refs);
  bag.push({
    eventId,
    kind: partial.kind,
    asOf: partial.asOf,
    label: formatTradeStoryEventLabel(partial.kind),
    detail: partial.detail ?? null,
    source: partial.source,
    refs,
  });
}

function dedupeKey(e: TradeStoryEventV1): string {
  return [
    e.kind,
    e.asOf,
    e.source,
    e.refs.entryId ?? "",
    e.refs.revisionId ?? "",
    e.refs.transactionId ?? "",
    e.refs.orderId ?? "",
    e.refs.intentId ?? "",
    e.refs.sessionId ?? "",
  ].join("|");
}

function collectFromStudy(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const study = input.study;
  if (!study) return;
  const studiedAt = study.studiedAt;
  if (!isValidAsOf(studiedAt)) return;
  pushEvent(bag, {
    kind: "estudio",
    asOf: studiedAt,
    source: "journal_study",
    refs: {
      sessionId: study.sessionId,
      decisionId: study.decisionId ?? input.decisionId ?? null,
    },
  });
  // tradePlanStatus alone has no transition stamp — do not invent preparada/trigger.
}

function journalKind(
  eventType: DecisionJournalEntryV1["eventType"],
): TradeStoryEventKindV1 | null {
  switch (eventType) {
    case "proposal_recorded":
      return "propuesta";
    case "human_confirm":
      return "confirmacion";
    case "executed":
      return "fill";
    case "risk_veto":
      return "bloqueada";
    default:
      return null;
  }
}

function collectFromJournalEntries(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const entries = input.journalEntries ?? [];
  const instrumentId = input.instrumentId.trim();
  const decisionId = nonEmpty(input.decisionId ?? null);
  for (const entry of entries) {
    if (!entry) continue;
    const entryInst = nonEmpty(entry.instrumentId ?? null);
    if (entryInst && entryInst !== instrumentId) continue;
    const entryDec = nonEmpty(entry.decisionId);
    if (decisionId && entryDec && entryDec !== decisionId) continue;
    const kind = journalKind(entry.eventType);
    if (!kind) continue;
    if (!isValidAsOf(entry.createdAt)) continue;
    pushEvent(bag, {
      kind,
      asOf: entry.createdAt,
      source: "journal_entry",
      detail: entry.eventType,
      refs: {
        entryId: entry.entryId,
        decisionId: entry.decisionId,
        sessionId: entry.sessionId ?? null,
      },
      eventId: `journal|${entry.entryId}`,
    });
  }
}

function collectFromOrderProposal(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const p = input.orderProposal;
  if (!p) return;
  if (isValidAsOf(p.createdAt)) {
    pushEvent(bag, {
      kind: "propuesta",
      asOf: p.createdAt,
      source: "order_proposal",
      refs: {
        decisionId: p.decisionId,
        sessionId: p.sessionId,
      },
      eventId: `proposal|${p.proposalId}|created`,
    });
  }
  if (p.status === "confirmed" && isValidAsOf(p.closedAt ?? null)) {
    pushEvent(bag, {
      kind: "confirmacion",
      asOf: p.closedAt!,
      source: "order_proposal",
      refs: {
        decisionId: p.decisionId,
        sessionId: p.sessionId,
      },
      eventId: `proposal|${p.proposalId}|confirmed`,
    });
  }
  if (p.status === "expired" && isValidAsOf(p.closedAt ?? null)) {
    pushEvent(bag, {
      kind: "caducada",
      asOf: p.closedAt!,
      source: "order_proposal",
      refs: {
        decisionId: p.decisionId,
        sessionId: p.sessionId,
      },
      eventId: `proposal|${p.proposalId}|expired`,
    });
  }
}

function collectFromFills(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const fills = input.fills ?? [];
  for (let i = 0; i < fills.length; i++) {
    const fill = fills[i];
    if (!fill || !isValidAsOf(fill.filledAt ?? null)) continue;
    pushEvent(bag, {
      kind: "fill",
      asOf: fill.filledAt!,
      source: "position_fill",
      detail:
        fill.quantity != null ? `qty ${fill.quantity} @ ${fill.price}` : null,
      refs: {
        positionId: fill.positionId ?? input.positionId ?? null,
      },
      eventId: `fill|${fill.filledAt}|${i}`,
    });
  }
}

function collectFromTransactions(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const txs = input.transactions ?? [];
  for (const tx of txs) {
    if (!tx || !isValidAsOf(tx.executedAt)) continue;
    const kind: TradeStoryEventKindV1 = tx.type === "sell" ? "cierre" : "fill";
    // sell may be reduce not full close — caller should prefer position_revision
    // for status CLOSED. Treat sell as cierre only when labelled; still OK as
    // honesty event when transaction bag is the only clock.
    pushEvent(bag, {
      kind: tx.type === "sell" ? "cierre" : kind,
      asOf: tx.executedAt,
      source: "transaction",
      detail: tx.quantity != null ? `${tx.type} qty ${tx.quantity}` : tx.type,
      refs: {
        transactionId: tx.id,
        positionId: input.positionId ?? null,
      },
      eventId: `tx|${tx.id}`,
    });
  }
}

function collectFromPositionState(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const ps = input.positionState;
  if (!ps) return;

  if (isValidAsOf(ps.createdAt) && ps.actualEntry != null) {
    pushEvent(bag, {
      kind: "fill",
      asOf: ps.createdAt,
      source: "position_fill",
      detail: `entry ${ps.actualEntry}`,
      refs: {
        positionId: ps.positionId,
        decisionId: input.decisionId ?? null,
      },
      eventId: `pos|${ps.positionId}|open`,
    });
  }

  if (ps.status === "PARTIAL" && isValidAsOf(ps.updatedAt)) {
    pushEvent(bag, {
      kind: "fill_partial",
      asOf: ps.updatedAt,
      source: "position_fill",
      refs: { positionId: ps.positionId },
      eventId: `pos|${ps.positionId}|partial|${ps.updatedAt}`,
    });
  }

  if (isValidAsOf(ps.target1AchievedAt ?? null)) {
    pushEvent(bag, {
      kind: "t1",
      asOf: ps.target1AchievedAt!,
      source: "position_target",
      refs: { positionId: ps.positionId },
      eventId: `pos|${ps.positionId}|t1`,
    });
  }
  if (isValidAsOf(ps.target2AchievedAt ?? null)) {
    pushEvent(bag, {
      kind: "t2",
      asOf: ps.target2AchievedAt!,
      source: "position_target",
      refs: { positionId: ps.positionId },
      eventId: `pos|${ps.positionId}|t2`,
    });
  }

  for (const rev of ps.revisions ?? []) {
    if (!rev || !isValidAsOf(rev.at)) continue;
    const stopChanged =
      rev.previousStop !== rev.nextStop &&
      (rev.previousStop != null || rev.nextStop != null);
    if (stopChanged) {
      const trailing =
        rev.origin === "protect" &&
        typeof rev.reason === "string" &&
        /trail/i.test(rev.reason);
      pushEvent(bag, {
        kind: trailing ? "trailing_applied" : "stop_updated",
        asOf: rev.at,
        source: "position_revision",
        detail: rev.reason,
        refs: {
          revisionId: rev.revisionId,
          positionId: ps.positionId,
        },
        eventId: `rev|${rev.revisionId}|stop`,
      });
    }
    if (rev.nextStatus === "CLOSED") {
      pushEvent(bag, {
        kind: "cierre",
        asOf: rev.at,
        source: "position_revision",
        detail: rev.reason,
        refs: {
          revisionId: rev.revisionId,
          positionId: ps.positionId,
        },
        eventId: `rev|${rev.revisionId}|close`,
      });
    }
  }

  if (
    ps.status === "CLOSED" &&
    isValidAsOf(ps.updatedAt) &&
    !(ps.revisions ?? []).some((r) => r.nextStatus === "CLOSED")
  ) {
    pushEvent(bag, {
      kind: "cierre",
      asOf: ps.updatedAt,
      source: "position_revision",
      refs: { positionId: ps.positionId },
      eventId: `pos|${ps.positionId}|closed`,
    });
  }
}

/**
 * PaperOrder has no clock — only emit when ExecutionState.asOf is present
 * and lifecycle warrants an honesty event.
 */
function collectFromExecutionState(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const es = input.executionState;
  if (!es || !isValidAsOf(es.asOf)) return;
  const refs: TradeStoryEventRefsV1 = {
    orderId: es.orderId,
    intentId: es.intentId,
    decisionId: es.decisionId,
    transactionId: es.transactionId,
  };
  if (es.lifecycle === "unknown" || es.orderState === "unknown") {
    pushEvent(bag, {
      kind: "unknown_order",
      asOf: es.asOf,
      source: "execution_state",
      refs,
      eventId: `es|unknown|${es.asOf}|${es.orderId ?? ""}`,
    });
  }
  if (es.lifecycle === "reconciled") {
    pushEvent(bag, {
      kind: "reconciled",
      asOf: es.asOf,
      source: "execution_state",
      refs,
      eventId: `es|reconciled|${es.asOf}|${es.orderId ?? ""}`,
    });
  }
  if (es.fillState === "partial" || es.orderState === "partial") {
    pushEvent(bag, {
      kind: "fill_partial",
      asOf: es.asOf,
      source: "execution_state",
      refs,
      eventId: `es|partial|${es.asOf}|${es.orderId ?? ""}`,
    });
  }
  if (
    es.fillState === "complete" &&
    (es.lifecycle === "filled" || es.lifecycle === "reconciled")
  ) {
    pushEvent(bag, {
      kind: "fill",
      asOf: es.asOf,
      source: "execution_state",
      refs,
      eventId: `es|fill|${es.asOf}|${es.orderId ?? es.transactionId ?? ""}`,
    });
  }
  // trailingState hint/proposed must NEVER emit trailing_applied
}

function collectFromSubmitIntent(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  const intent = input.submitIntent;
  if (!intent) return;
  const crash =
    intent.phase === "send_attempted" ||
    intent.phase === "venue_bound" ||
    (intent.phase === "recorded" && intent.sendAttemptedAt != null);
  if (crash && isValidAsOf(intent.sendAttemptedAt)) {
    pushEvent(bag, {
      kind: "unknown_order",
      asOf: intent.sendAttemptedAt!,
      source: "submit_intent",
      refs: {
        intentId: intent.intentId,
        orderId: intent.orderId,
        decisionId: intent.decisionId,
      },
      eventId: `intent|unknown|${intent.intentId}`,
    });
  }
}

function collectFromCallerFacts(
  bag: TradeStoryEventV1[],
  input: BuildTradeStoryInputV1,
): void {
  for (const fact of input.facts ?? []) {
    if (!fact || !isValidAsOf(fact.asOf)) continue;
    // Never promote trailing from caller without explicit kind trailing_applied
    pushEvent(bag, {
      kind: fact.kind,
      asOf: fact.asOf,
      source: "caller",
      detail: fact.detail ?? null,
      refs: fact.refs ?? {},
      eventId: fact.eventId ?? null,
    });
  }
}

/**
 * Collect → dedupe → sort by asOf. Omit without asOf. Never drop earlier events
 * once collected (dedupe only exact key collisions).
 */
export function buildTradeStory(input: BuildTradeStoryInputV1): TradeStoryV1 {
  const instrumentId = input.instrumentId.trim();
  const bag: TradeStoryEventV1[] = [];

  collectFromStudy(bag, input);
  collectFromJournalEntries(bag, input);
  collectFromOrderProposal(bag, input);
  collectFromFills(bag, input);
  collectFromTransactions(bag, input);
  collectFromPositionState(bag, input);
  collectFromSubmitIntent(bag, input);
  collectFromExecutionState(bag, input);
  collectFromCallerFacts(bag, input);

  const seen = new Set<string>();
  const events: TradeStoryEventV1[] = [];
  for (const e of bag) {
    const key = dedupeKey(e);
    if (seen.has(key)) continue;
    seen.add(key);
    events.push(e);
  }
  events.sort((a, b) => {
    const ta = Date.parse(a.asOf);
    const tb = Date.parse(b.asOf);
    if (ta !== tb) return ta - tb;
    return a.eventId.localeCompare(b.eventId);
  });

  const decisionId =
    nonEmpty(input.decisionId ?? null) ??
    nonEmpty(input.study?.decisionId ?? null) ??
    nonEmpty(input.orderProposal?.decisionId ?? null) ??
    nonEmpty(input.submitIntent?.decisionId ?? null) ??
    nonEmpty(input.executionState?.decisionId ?? null);

  const positionId =
    nonEmpty(input.positionId ?? null) ??
    nonEmpty(input.positionState?.positionId ?? null);

  const lastAsOf = events.length > 0 ? events[events.length - 1]!.asOf : null;
  const asOf = nonEmpty(input.asOf ?? null) ?? lastAsOf;

  return {
    instrumentId,
    decisionId,
    positionId,
    asOf,
    events,
  };
}

export function tradeStorySurfaceSnapshot(
  story: TradeStoryV1,
): TradeStorySurfaceSnapshotV1 {
  return {
    eventKinds: story.events.map((e) => e.kind),
    firstAsOf: story.events[0]?.asOf ?? null,
    lastAsOf: story.events[story.events.length - 1]?.asOf ?? null,
    count: story.events.length,
    decisionId: story.decisionId,
    positionId: story.positionId,
  };
}
