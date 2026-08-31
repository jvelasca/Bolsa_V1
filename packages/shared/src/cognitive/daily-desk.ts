/**
 * Daily Desk — inbox canónico de Hoy por attention (V1.41).
 * Composición: OperationalTruth.attention + firmas pendientes + cola board.
 * Hoy no es segundo Mercado: sin paneles de ranking/KPI en el chrome.
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { PositionDto } from "../types.js";
import {
  filterMesaAttentionItems,
  buildMesaActionQueue,
  type MesaAttentionItemV1,
} from "./mesa-hoy-model.js";
import {
  buildOperationalTruth,
  openPositionNeedsAction,
  type OperationalTruthV1,
} from "./operational-truth.js";
import type { PositionAttentionV1 } from "./position-decision.js";

export type DailyDeskItemKindV1 =
  | "pending_confirm"
  | "position"
  | "board_attention";

export type DailyDeskItemV1 = {
  id: string;
  kind: DailyDeskItemKindV1;
  symbol: string;
  attention: PositionAttentionV1;
  reason: string;
  ctaLabel: string;
  /** Solo posiciones: verdad operativa de origen. */
  positionId?: string;
};

export type DailyDeskInboxV1 = {
  items: DailyDeskItemV1[];
  count: number;
  emptyLabel: string;
};

export type DailyDeskSurfaceSnapshotV1 = {
  count: number;
  ids: string[];
  attentions: PositionAttentionV1[];
  ctaLabels: string[];
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
};

export function buildDailyDeskInbox(
  input: BuildDailyDeskInboxInputV1,
): DailyDeskInboxV1 {
  const items: DailyDeskItemV1[] = [];
  const pending = Math.max(0, input.pendingConfirm ?? 0);

  if (pending > 0) {
    items.push({
      id: "pending-confirm",
      kind: "pending_confirm",
      symbol: "Confirm",
      attention: "URGENT",
      reason:
        pending === 1
          ? "1 pendiente de firma"
          : `${pending} pendientes de firma`,
      ctaLabel: "Revisar y confirmar",
    });
  }

  const seenSymbols = new Set<string>();

  for (const position of input.positions) {
    const truth = buildOperationalTruth({
      position,
      portfolioReconStatus: input.portfolioReconStatus,
    });
    if (!truth) continue;
    const needsAction = openPositionNeedsAction(truth.decision);
    if (truth.attention === "NORMAL" && !needsAction) continue;
    seenSymbols.add(position.symbol.toUpperCase());
    items.push(dailyDeskItemFromTruth(truth));
  }

  const boardItems = filterMesaAttentionItems(
    buildMesaActionQueue(input.board ?? null),
    input.attentionLimit ?? 8,
    input.protectionDiscrepancies,
  );
  for (const item of boardItems) {
    const sym = item.symbol.toUpperCase();
    if (seenSymbols.has(sym)) continue;
    seenSymbols.add(sym);
    items.push({
      id: item.id ?? `board-${item.symbol}-${item.kind}`,
      kind: "board_attention",
      symbol: item.symbol,
      attention: boardItemAttention(item),
      reason: item.reason,
      ctaLabel: formatBoardCta(item.recommendedAction),
    });
  }

  items.sort((a, b) => {
    const rank = attentionRank(b.attention) - attentionRank(a.attention);
    if (rank !== 0) return rank;
    if (a.kind === "pending_confirm") return -1;
    if (b.kind === "pending_confirm") return 1;
    return a.symbol.localeCompare(b.symbol);
  });

  return {
    items,
    count: items.length,
    emptyLabel: "Nada requiere tu atención",
  };
}

export function dailyDeskItemFromTruth(
  truth: OperationalTruthV1,
): DailyDeskItemV1 {
  return {
    id: `position-${truth.positionId}`,
    kind: "position",
    symbol: truth.symbol,
    attention: truth.attention,
    reason: truth.decision.reason || truth.primaryCta.label,
    ctaLabel: truth.primaryCta.label,
    positionId: truth.positionId,
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
