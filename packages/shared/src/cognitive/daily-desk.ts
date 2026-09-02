/**
 * Daily Desk — Hoy 2.0 four buckets (V1.42 F6).
 * Composición: EntryOperatingTruth / PositionOperatingTruth / ExecutionState +
 * board attention. No DailyEngine. Hoy ≠ segundo Mercado.
 *
 * Spec §B.7:
 * 🔴 REQUIERE ACCIÓN · 🟢 OPORTUNIDADES · 🟡 VIGILAR · ⚪ SIN ACCIÓN
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { PositionDto } from "../types.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildEntryOperatingTruth,
  type EntryOperatingTruthV1,
} from "./entry-operating-truth.js";
import { formatExecutionStateCopy } from "./execution-state.js";
import {
  enrichMesaCandidates,
  filterMesaAttentionItems,
  buildMesaActionQueue,
  type MesaAttentionItemV1,
} from "./mesa-hoy-model.js";
import { buildMesaEntryQueue } from "./mesa-entry-queue.js";
import type { MesaNextActionKindV1 } from "./mesa-next-action.js";
import { MERCADO_COCKPIT_PHASE_LABEL } from "./mercado-cockpit-phase.js";
import {
  buildPositionOperatingTruth,
  type PositionOperatingTruthV1,
} from "./position-operating-truth.js";
import type { OperationalTruthV1 } from "./operational-truth.js";
import type { PositionAttentionV1 } from "./position-decision.js";
import type { ProtectPlanV1 } from "./protect-plan.js";

export type DailyDeskBucketIdV1 =
  | "requiere_accion"
  | "proteger"
  | "posiciones"
  | "oportunidades"
  | "no_operar";

export const DAILY_DESK_BUCKET_ORDER: readonly DailyDeskBucketIdV1[] = [
  "requiere_accion",
  "proteger",
  "posiciones",
  "oportunidades",
  "no_operar",
] as const;

/** Chrome labels — human copy, never WATCH/ARMED/TRIGGERED enums. */
export const DAILY_DESK_BUCKET_LABEL: Record<DailyDeskBucketIdV1, string> = {
  requiere_accion: "Requiere acción",
  proteger: "Proteger",
  posiciones: "Posiciones",
  oportunidades: "Oportunidades",
  no_operar: "No operar",
};

export const DAILY_DESK_BUCKET_EMPTY: Record<DailyDeskBucketIdV1, string> = {
  requiere_accion: "Nada requiere tu firma ni una salida ahora",
  proteger: "Sin posiciones pendientes de protección",
  posiciones: "Sin posiciones abiertas en seguimiento",
  oportunidades: "Sin preparadas, disparadas ni propuestas",
  no_operar: "Sin bloqueos ni vigilar hoy",
};

export type DailyDeskItemKindV1 =
  | "pending_confirm"
  | "position"
  | "entry"
  | "board_attention"
  | "incident";

export type DailyDeskItemV1 = {
  id: string;
  kind: DailyDeskItemKindV1;
  bucket: DailyDeskBucketIdV1;
  symbol: string;
  attention: PositionAttentionV1;
  /** Frase operativa (misma familia que Mercado POT/EOT). */
  phrase: string;
  /** Motivo corto / eco de attention. */
  reason: string;
  ctaLabel: string;
  ctaKind: MesaNextActionKindV1 | "pending_confirm" | "none";
  /** Copy humano de fase (Preparada / Disparada / …) — no enums TradePlan. */
  phaseLabel: string | null;
  positionId?: string;
  instrumentId?: string;
  /** V1.76 — código de deny (ENTRY_STALE_DATA, …) para certificación DOM. */
  reasonCode?: string | null;
};

export type DailyDeskBucketV1 = {
  id: DailyDeskBucketIdV1;
  label: string;
  items: DailyDeskItemV1[];
  count: number;
  emptyLabel: string;
};

export type DailyDeskInboxV1 = {
  /** Flat list (todos los cubos con ítems). */
  items: DailyDeskItemV1[];
  /** Siempre los cuatro cubos §B.7, en orden. */
  buckets: DailyDeskBucketV1[];
  count: number;
  emptyLabel: string;
};

export type DailyDeskSurfaceSnapshotV1 = {
  count: number;
  ids: string[];
  attentions: PositionAttentionV1[];
  ctaLabels: string[];
  bucketIds: DailyDeskBucketIdV1[];
  phrases: string[];
};

const ATTENTION_RANK: Record<PositionAttentionV1, number> = {
  BLOCKED: 3,
  URGENT: 2,
  ATTENTION: 1,
  NORMAL: 0,
};

export function attentionRank(attention: PositionAttentionV1): number {
  return ATTENTION_RANK[attention] ?? 0;
}

function boardItemAttention(item: MesaAttentionItemV1): PositionAttentionV1 {
  if (item.kind === "BLOCKED") return "BLOCKED";
  if (item.recommendedAction === "REVISAR PROTECCIÓN") return "URGENT";
  if (item.kind === "REVIEW") return "ATTENTION";
  return "ATTENTION";
}

export type BuildDailyDeskInboxInputV1 = {
  positions: PositionDto[];
  board?: DecisionBoardV1 | null;
  portfolioReconStatus?: string | null;
  pendingConfirm?: number;
  /** Discrepancias de protección (mismo shape que filterMesaAttentionItems extra). */
  protectionDiscrepancies?: Array<{
    symbol: string;
    reason: string;
    recommendedAction: string;
  }>;
  attentionLimit?: number;
  /** Instrumentos con orden en vuelo (mismo executionHint que Mercado). */
  pendingInstrumentIds?: readonly string[];
  /** Studies por instrumentId — misma fuente que Mercado EOT. */
  studiesByInstrument?: Map<string, DecisionJournalStudyViewV1> | null;
  /** Instrumentos en cola Confirm (fase propuesta). */
  confirmQueueInstrumentIds?: readonly string[];
  entriesBlocked?: boolean;
  hasOpenIncident?: boolean;
  /** Instrumentos con ExecutionState UNKNOWN (OR-2). */
  unknownInstrumentIds?: readonly string[];
  protectPlanByInstrument?: Map<string, ProtectPlanV1> | null;
};

function sortDeskItems(items: DailyDeskItemV1[]): void {
  items.sort((a, b) => {
    const bucketRank =
      DAILY_DESK_BUCKET_ORDER.indexOf(a.bucket) -
      DAILY_DESK_BUCKET_ORDER.indexOf(b.bucket);
    if (bucketRank !== 0) return bucketRank;
    const rank = attentionRank(b.attention) - attentionRank(a.attention);
    if (rank !== 0) return rank;
    if (a.kind === "pending_confirm") return -1;
    if (b.kind === "pending_confirm") return 1;
    return a.symbol.localeCompare(b.symbol);
  });
}

function groupBuckets(items: DailyDeskItemV1[]): DailyDeskBucketV1[] {
  const byId = new Map<DailyDeskBucketIdV1, DailyDeskItemV1[]>();
  for (const id of DAILY_DESK_BUCKET_ORDER) byId.set(id, []);
  for (const item of items) {
    byId.get(item.bucket)!.push(item);
  }
  return DAILY_DESK_BUCKET_ORDER.map((id) => {
    const bucketItems = byId.get(id) ?? [];
    return {
      id,
      label: DAILY_DESK_BUCKET_LABEL[id],
      items: bucketItems,
      count: bucketItems.length,
      emptyLabel: DAILY_DESK_BUCKET_EMPTY[id],
    };
  });
}

/** §B.7 V1.55 — clasifica CTA/fase de posición → cubo. */
export function bucketFromPositionTruth(
  truth: PositionOperatingTruthV1,
): DailyDeskBucketIdV1 {
  if (
    truth.execution.lifecycle === "unknown" ||
    truth.execution.orderState === "unknown"
  ) {
    return "requiere_accion";
  }
  if (
    truth.operationalView?.operatingState === "RECONCILIATION_ERROR" ||
    truth.operationalView?.operatingState === "RECONCILIATION_DRIFT"
  ) {
    return "requiere_accion";
  }
  switch (truth.primaryCta.kind) {
    case "exit":
    case "reduce":
    case "review":
    case "review_filter":
    case "review_proposal":
      return "requiere_accion";
    case "protect":
      return "proteger";
    case "maintain":
    case "none":
      return "posiciones";
    case "watch":
      return "no_operar";
    case "view_thesis":
      return "oportunidades";
    default:
      return "requiere_accion";
  }
}

/** §B.7 — fase EOT → cubo (copy humano, no enums TradePlan). */
export function bucketFromEntryTruth(
  truth: EntryOperatingTruthV1,
): DailyDeskBucketIdV1 {
  switch (truth.phase) {
    case "preparada":
    case "disparada":
    case "propuesta":
      return "oportunidades";
    case "confirmada":
      return "requiere_accion";
    default:
      return "no_operar";
  }
}

function phraseForPosition(truth: PositionOperatingTruthV1): string {
  const execCopy = formatExecutionStateCopy(truth.execution);
  if (
    truth.execution.lifecycle === "unknown" ||
    truth.execution.orderState === "unknown"
  ) {
    return execCopy ?? truth.phrase;
  }
  if (execCopy && truth.primaryCta.kind === "review") {
    return execCopy;
  }
  return truth.phrase;
}

function shouldListPosition(_bucket: DailyDeskBucketIdV1): boolean {
  return true;
}

function dailyDeskItemFromPot(
  truth: PositionOperatingTruthV1,
): DailyDeskItemV1 {
  const bucket = bucketFromPositionTruth(truth);
  return {
    id: `position-${truth.positionId}`,
    kind: "position",
    bucket,
    symbol: truth.symbol,
    attention: truth.attention,
    phrase: phraseForPosition(truth),
    reason: truth.phrase || truth.primaryCta.label,
    ctaLabel: truth.primaryCta.label,
    ctaKind: truth.primaryCta.kind,
    phaseLabel: MERCADO_COCKPIT_PHASE_LABEL.posicion,
    positionId: truth.positionId,
    instrumentId: truth.instrumentId,
  };
}

export function dailyDeskItemFromEot(
  truth: EntryOperatingTruthV1,
): DailyDeskItemV1 {
  const bucket = bucketFromEntryTruth(truth);
  const ctaKind: DailyDeskItemV1["ctaKind"] =
    truth.primaryCta.kind === "prepare"
      ? "view_thesis"
      : truth.primaryCta.kind === "review_confirm"
        ? "review_proposal"
        : truth.primaryCta.kind === "view_operations"
          ? "watch"
          : "none";
  return {
    id: `entry-${truth.instrumentId}`,
    kind: "entry",
    bucket,
    symbol: truth.symbol,
    attention:
      truth.phase === "disparada" || truth.phase === "propuesta"
        ? "URGENT"
        : truth.primaryCta.kind === "none"
          ? "BLOCKED"
          : "ATTENTION",
    phrase: truth.phrase,
    reason: truth.phrase,
    ctaLabel: truth.primaryCta.label,
    ctaKind,
    phaseLabel: truth.phaseLabel,
    instrumentId: truth.instrumentId,
  };
}

/** Compat V1.41 — proyecta OperationalTruth a ítem de cubo. */
export function dailyDeskItemFromTruth(
  truth: OperationalTruthV1,
): DailyDeskItemV1 {
  const kind = truth.primaryCta.kind as MesaNextActionKindV1;
  const bucket: DailyDeskBucketIdV1 =
    kind === "protect"
      ? "proteger"
      : kind === "maintain" || kind === "none"
        ? "posiciones"
        : kind === "watch"
          ? "no_operar"
          : "requiere_accion";
  return {
    id: `position-${truth.positionId}`,
    kind: "position",
    bucket,
    symbol: truth.symbol,
    attention: truth.attention,
    phrase: truth.decision.reason || truth.primaryCta.label,
    reason: truth.decision.reason || truth.primaryCta.label,
    ctaLabel: truth.primaryCta.label,
    ctaKind: kind,
    phaseLabel: MERCADO_COCKPIT_PHASE_LABEL.posicion,
    positionId: truth.positionId,
    instrumentId: truth.instrumentId,
  };
}

export function buildDailyDeskInbox(
  input: BuildDailyDeskInboxInputV1,
): DailyDeskInboxV1 {
  const items: DailyDeskItemV1[] = [];
  const pending = Math.max(0, input.pendingConfirm ?? 0);
  const pendingIds = new Set(input.pendingInstrumentIds ?? []);
  const confirmIds = new Set(input.confirmQueueInstrumentIds ?? []);
  const unknownIds = new Set(input.unknownInstrumentIds ?? []);
  const studies = input.studiesByInstrument ?? null;
  const protectByInst = input.protectPlanByInstrument ?? null;
  const discrepancyBySymbol = new Map(
    (input.protectionDiscrepancies ?? []).map((d) => [
      d.symbol.toUpperCase(),
      d,
    ]),
  );

  if (pending > 0) {
    items.push({
      id: "pending-confirm",
      kind: "pending_confirm",
      bucket: "requiere_accion",
      symbol: "Confirm",
      attention: "URGENT",
      phrase:
        pending === 1
          ? "1 propuesta pendiente de firma en Confirm"
          : `${pending} propuestas pendientes de firma en Confirm`,
      reason:
        pending === 1
          ? "1 pendiente de firma"
          : `${pending} pendientes de firma`,
      ctaLabel: "Revisar y confirmar",
      ctaKind: "pending_confirm",
      phaseLabel: MERCADO_COCKPIT_PHASE_LABEL.propuesta,
    });
  }

  if (input.hasOpenIncident === true) {
    items.push({
      id: "open-incident",
      kind: "incident",
      bucket: "requiere_accion",
      symbol: "Incidente",
      attention: "BLOCKED",
      phrase:
        "Incidente operativo abierto — entradas bloqueadas; desriesgo humano disponible",
      reason: "Incidente operativo",
      ctaLabel: "Revisar",
      ctaKind: "review",
      phaseLabel: null,
    });
  }

  const seenSymbols = new Set<string>();
  const seenInstrumentIds = new Set<string>();

  for (const position of input.positions) {
    const disc = discrepancyBySymbol.get(position.symbol.toUpperCase());
    const pot = buildPositionOperatingTruth({
      position,
      study: studies?.get(position.instrumentId) ?? null,
      portfolioReconStatus: input.portfolioReconStatus,
      orderPending:
        pendingIds.has(position.instrumentId) ||
        unknownIds.has(position.instrumentId),
      protectPlan: protectByInst?.get(position.instrumentId) ?? null,
      protectionDiscrepancy: Boolean(disc),
      hasOpenIncident: input.hasOpenIncident === true,
      includeExitRoute: false,
    });
    if (!pot) continue;

    let item = dailyDeskItemFromPot(pot);
    // Thin wire UNKNOWN (sin PaperOrder en Hoy): misma CTA/frase que Mercado.
    if (unknownIds.has(position.instrumentId)) {
      item = {
        ...item,
        bucket: "requiere_accion",
        attention: item.attention === "NORMAL" ? "URGENT" : item.attention,
        phrase: "Orden desconocida — no duplicar. Revisar / reconciliar.",
        reason: "Orden UNKNOWN",
        ctaLabel: "Ver operaciones",
        ctaKind: "review",
      };
    }
    if (!shouldListPosition(item.bucket)) continue;
    seenSymbols.add(position.symbol.toUpperCase());
    seenInstrumentIds.add(position.instrumentId);
    items.push(item);
  }

  // Entry opportunities from board (EOT — misma verdad que Mercado).
  const board = input.board ?? null;
  if (board && studies) {
    const rows = buildMesaEntryQueue(board);
    const enriched = enrichMesaCandidates(rows, board, studies);
    for (const row of enriched) {
      if (!row.study || !row.instrumentId) continue;
      const sym = row.symbol.toUpperCase();
      if (seenSymbols.has(sym) || seenInstrumentIds.has(row.instrumentId)) {
        continue;
      }
      // Ranking ≠ BUY: no meter WATCH puro sin plan en 🟢.
      const eot = buildEntryOperatingTruth({
        study: row.study,
        hasOpenPosition: false,
        inConfirmQueue: confirmIds.has(row.instrumentId),
        orderPendingFill: pendingIds.has(row.instrumentId),
        inEstudio: true,
        entriesBlocked: input.entriesBlocked === true,
        gateStatus: row.gate,
      });
      if (!eot) {
        // Sin EOT: WATCH / en estudio → 🟡 si está en cola.
        if (row.status === "WATCH") {
          seenSymbols.add(sym);
          seenInstrumentIds.add(row.instrumentId);
          items.push({
            id: `watch-${row.instrumentId}`,
            kind: "entry",
            bucket: "no_operar",
            symbol: row.symbol,
            attention: "NORMAL",
            phrase: "En estudio — esperando disparador",
            reason: "En estudio",
            ctaLabel: "Ver análisis",
            ctaKind: "watch",
            phaseLabel: MERCADO_COCKPIT_PHASE_LABEL.vigilar,
            instrumentId: row.instrumentId,
          });
        }
        continue;
      }
      const item = dailyDeskItemFromEot(eot);
      // bloqueada/caducada con CTA none: no saturar 🟢; van a vigilar solo si hay atención.
      if (item.ctaKind === "none" && item.bucket === "oportunidades") {
        item.bucket = "no_operar";
      }
      seenSymbols.add(sym);
      seenInstrumentIds.add(row.instrumentId);
      items.push(item);
    }
  }

  // Board attention residual (protect / REVIEW / BLOCKED) no cubierto arriba.
  const boardItems = filterMesaAttentionItems(
    buildMesaActionQueue(board),
    input.attentionLimit ?? 8,
    input.protectionDiscrepancies,
  );
  for (const item of boardItems) {
    const sym = item.symbol.toUpperCase();
    if (seenSymbols.has(sym)) continue;
    seenSymbols.add(sym);
    const isProtect = item.recommendedAction === "REVISAR PROTECCIÓN";
    const isExit = item.recommendedAction === "REVISAR SALIDA";
    const isBlocked = item.kind === "BLOCKED";
    const bucket: DailyDeskBucketIdV1 = isProtect
      ? "proteger"
      : isExit || isBlocked
        ? "requiere_accion"
        : "no_operar";
    items.push({
      id: item.id ?? `board-${item.symbol}-${item.kind}`,
      kind: "board_attention",
      bucket,
      symbol: item.symbol,
      attention: boardItemAttention(item),
      phrase: item.reason,
      reason: item.reason,
      ctaLabel: formatBoardCta(item.recommendedAction),
      ctaKind: isProtect
        ? "protect"
        : isExit
          ? "exit"
          : isBlocked
            ? "review_filter"
            : "review",
      phaseLabel: null,
    });
  }

  sortDeskItems(items);
  const buckets = groupBuckets(items);

  return {
    items,
    buckets,
    count: items.length,
    emptyLabel: "Nada requiere tu atención",
  };
}

/** Reagrupa ítems ya construidos (merge autoDesk / excepciones). */
export function finalizeDailyDeskInbox(
  items: DailyDeskItemV1[],
  emptyLabel = "Nada requiere tu atención",
): DailyDeskInboxV1 {
  sortDeskItems(items);
  const buckets = groupBuckets(items);
  return {
    items,
    buckets,
    count: items.length,
    emptyLabel,
  };
}

export function dailyDeskSurfaceSnapshot(
  inbox: DailyDeskInboxV1,
): DailyDeskSurfaceSnapshotV1 {
  return {
    count: inbox.count,
    ids: inbox.items.map((i) => i.id),
    attentions: inbox.items.map((i) => i.attention),
    ctaLabels: inbox.items.map((i) => i.ctaLabel),
    bucketIds: inbox.items.map((i) => i.bucket),
    phrases: inbox.items.map((i) => i.phrase),
  };
}

function formatBoardCta(recommendedAction: string): string {
  switch (recommendedAction) {
    case "REVISAR PROTECCIÓN":
      return "Proteger";
    case "REVISAR SALIDA":
      return "Salir";
    case "REVISAR FILTRO":
      return "Revisar";
    case "REVISAR":
      return "Revisar";
    default:
      return recommendedAction;
  }
}
