/**
 * Compositor read-only Mesa · Hoy (ADR-037).
 * Une Decision Board, portfolio, incidentes y studies sin endpoints nuevos.
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import {
  DECISION_JOURNAL_STUDY_ARTIFACT,
  DECISION_JOURNAL_STUDY_SCHEMA,
  journalStudyGeometry,
  type DecisionJournalStudyViewV1,
} from "./decision-journal-study.js";
import type { OperationalIncidentV1 } from "./operational-incident.js";
import type { TradePlanStatusV1, TradePlanV1 } from "./trade-plan.js";
import {
  buildActionQueue,
  readCanonicalTradePlan,
  type HoyActionKindV1,
  type HoyQueueItemV1,
} from "./hoy-queue.js";
import {
  buildMesaEntryQueue,
  deriveMesaRegimeHint,
  filterMesaEntryQueue,
  groupMesaEntryQueue,
  MESA_ENTRY_GROUP_ORDER,
  type MesaEntryQueueRowV1,
} from "./mesa-entry-queue.js";
import { MESA_CANDIDATE_GROUP_LABEL } from "./mesa-status-dimensions.js";

export type MesaSessionToneV1 = "blocked" | "selective" | "operational";

export type MesaSessionStateV1 = {
  tone: MesaSessionToneV1;
  headline: string;
  detail: string;
  regimeHint: string | null;
  pendingConfirm: number;
  vetoed: number;
  deferred: number;
  /** Tamaño del universo Estudio (supervisión), no = WATCH del board. */
  estudioUniverseCount: number | null;
  candidateCounts: {
    ready: number;
    prepared: number;
    watch: number;
    blocked: number;
  };
};

export type MesaAttentionItemV1 = HoyQueueItemV1 & {
  reason: string;
  recommendedAction: string;
};

export type MesaCandidateRowV1 = MesaEntryQueueRowV1 & {
  instrumentId: string | null;
  study: DecisionJournalStudyViewV1 | null;
};

const ATTENTION_KINDS = new Set<HoyActionKindV1>(["REVIEW", "BLOCKED"]);

export function mesaEntriesBlocked(input: {
  killSwitchEffective?: boolean;
  incidents?: OperationalIncidentV1[];
  vetoed?: number;
}): boolean {
  if (input.killSwitchEffective) return true;
  if ((input.incidents?.length ?? 0) > 0) return true;
  return (input.vetoed ?? 0) > 0;
}

export function filterMesaAttentionItems(
  queue: HoyQueueItemV1[],
  limit = 5,
  extra?: Array<{ symbol: string; reason: string; recommendedAction: string }>,
): MesaAttentionItemV1[] {
  const items: MesaAttentionItemV1[] = [];
  for (const item of queue) {
    let reason: string | null = null;
    let recommendedAction: string | null = null;

    if (ATTENTION_KINDS.has(item.kind)) {
      reason =
        item.kind === "REVIEW"
          ? (item.thesisHealth?.hint ?? "Revisión de tesis recomendada")
          : "Candidato bloqueado";
      recommendedAction = item.kind === "REVIEW" ? "REVISAR" : "REVISAR FILTRO";
    } else if (item.protectPlan?.status === "protect_hint") {
      reason = "Stop próximo al precio actual";
      recommendedAction = "REVISAR PROTECCIÓN";
    } else if (item.exitRadar?.status === "exit_hint") {
      reason = "Señal de salida advisory";
      recommendedAction = "REVISAR SALIDA";
    }

    if (!reason || !recommendedAction) continue;
    items.push({ ...item, reason, recommendedAction });
    if (items.length >= limit) break;
  }
  for (const ex of extra ?? []) {
    if (items.length >= limit) break;
    items.push({
      id: `discrepancy-${ex.symbol}`,
      symbol: ex.symbol,
      kind: "REVIEW",
      status: "WATCH",
      whyNot: [],
      gate: "PASS",
      planSource: "projection",
      reason: ex.reason,
      recommendedAction: ex.recommendedAction,
    });
  }
  return items;
}

export function buildInstrumentIdBySymbol(
  board: DecisionBoardV1 | null | undefined,
): Map<string, string> {
  const map = new Map<string, string>();
  if (!board) return map;
  for (const session of board.decisionSessions) {
    const symbol = session.symbol?.trim().toUpperCase();
    if (symbol && session.instrumentId) {
      map.set(symbol, session.instrumentId);
    }
  }
  for (const row of board.semiF3Queue) {
    const symbol = row.symbol?.trim().toUpperCase();
    if (symbol && row.instrumentId) {
      map.set(symbol, row.instrumentId);
    }
  }
  return map;
}

/**
 * Overlay geometría del TradePlan vivo del board sobre el study del journal.
 * El board es SoT de sizing operativo; el study puede ir atrasado.
 */
export function overlayLiveTradePlanOnStudy(
  study: DecisionJournalStudyViewV1 | null,
  livePlan: TradePlanV1 | null | undefined,
): DecisionJournalStudyViewV1 | null {
  const geometry = journalStudyGeometry(livePlan ?? null);
  if (!geometry.hasOperationalPlan) return study;
  if (!study) {
    return {
      artifactType: DECISION_JOURNAL_STUDY_ARTIFACT,
      schemaVersion: DECISION_JOURNAL_STUDY_SCHEMA,
      sessionId: livePlan?.decisionId ?? "board-live",
      decisionId: livePlan?.decisionId ?? null,
      instrumentId: livePlan?.instrumentId ?? "",
      symbol: null,
      name: null,
      studiedAt: new Date(0).toISOString(),
      ageMs: null,
      period: null,
      timeframe: null,
      opinion: null,
      status: "in_progress",
      strength: null,
      strengthBand: null,
      vigencia: null,
      entry: geometry.entry,
      stop: geometry.stop,
      target1: geometry.target1,
      target2: geometry.target2,
      expectedRR: geometry.expectedRR,
      riskAmount: geometry.riskAmount,
      quantity: geometry.quantity,
      initialRiskR: geometry.initialRiskR,
      positionValue: geometry.positionValue,
      direction: geometry.direction,
      hasOperationalPlan: true,
      userThesis: null,
      decisionSummary: null,
      analysisNotes: [],
      trends: [],
      consensus: { bullish: 0, bearish: 0, neutral: 0, total: 0 },
      indicators: { primary: null, confirmation: null },
      invalidation: [],
      nextReviewAt: null,
      tradePlanStatus: livePlan?.status ?? null,
      action: null,
    };
  }
  return {
    ...study,
    entry: geometry.entry ?? study.entry,
    stop: geometry.stop ?? study.stop,
    target1: geometry.target1 ?? study.target1,
    target2: geometry.target2 ?? study.target2,
    expectedRR: geometry.expectedRR ?? study.expectedRR,
    riskAmount: geometry.riskAmount ?? study.riskAmount,
    quantity: geometry.quantity ?? study.quantity,
    initialRiskR: geometry.initialRiskR ?? study.initialRiskR,
    positionValue: geometry.positionValue ?? study.positionValue,
    direction: geometry.direction ?? study.direction,
    hasOperationalPlan: true,
    tradePlanStatus: livePlan?.status ?? study.tradePlanStatus,
  };
}

function findLiveTradePlanForSymbol(
  board: DecisionBoardV1 | null | undefined,
  symbol: string,
): TradePlanV1 | null {
  if (!board) return null;
  const key = symbol.trim().toUpperCase();
  for (const session of board.decisionSessions) {
    if (session.symbol?.trim().toUpperCase() !== key) continue;
    const plan = readCanonicalTradePlan(session).plan;
    if (plan) return plan;
  }
  for (const row of board.semiF3Queue) {
    if (row.symbol?.trim().toUpperCase() !== key) continue;
    const plan = readCanonicalTradePlan(row).plan;
    if (plan) return plan;
  }
  return null;
}

export function enrichMesaCandidates(
  rows: MesaEntryQueueRowV1[],
  board: DecisionBoardV1 | null | undefined,
  studiesByInstrument: Map<string, DecisionJournalStudyViewV1>,
): MesaCandidateRowV1[] {
  const bySymbol = buildInstrumentIdBySymbol(board);
  return rows.map((row) => {
    const instrumentId = bySymbol.get(row.symbol.toUpperCase()) ?? null;
    const study = instrumentId
      ? (studiesByInstrument.get(instrumentId) ?? null)
      : null;
    const livePlan = findLiveTradePlanForSymbol(board, row.symbol);
    return {
      ...row,
      instrumentId,
      study: overlayLiveTradePlanOnStudy(study, livePlan),
    };
  });
}

export function buildMesaSessionState(
  board: DecisionBoardV1 | null | undefined,
  input: {
    entriesBlocked: boolean;
    killSwitchEffective?: boolean;
    incidentCount?: number;
    /** Instrumentos en lista Estudio (universo supervisable). */
    estudioUniverseCount?: number | null;
  },
): MesaSessionStateV1 {
  const buckets = board?.buckets;
  const pendingConfirm = buckets?.pendingConfirm ?? 0;
  const vetoed = buckets?.vetoed ?? 0;
  const deferred = buckets?.deferred ?? 0;
  const queue = board ? buildMesaEntryQueue(board) : [];
  const countByStatus = (status: TradePlanStatusV1) =>
    queue.filter((row) => row.status === status).length;

  const candidateCounts = {
    ready: countByStatus("TRIGGERED"),
    prepared: countByStatus("ARMED"),
    watch: countByStatus("WATCH"),
    blocked: countByStatus("BLOCKED"),
  };

  const estudioUniverseCount =
    typeof input.estudioUniverseCount === "number" &&
    Number.isFinite(input.estudioUniverseCount)
      ? Math.max(0, Math.floor(input.estudioUniverseCount))
      : null;

  const estudioPrefix =
    estudioUniverseCount != null
      ? `Estudio ${estudioUniverseCount} en supervisión`
      : null;

  const regimeHint = board ? deriveMesaRegimeHint(board) : null;

  if (input.incidentCount && input.incidentCount > 0) {
    return {
      tone: "blocked",
      headline: "Sistema en incidente",
      detail:
        "Nuevas entradas: BLOQUEADAS · Automatismos: BLOQUEADOS · Desriesgo humano: DISPONIBLE",
      regimeHint,
      pendingConfirm,
      vetoed,
      deferred,
      estudioUniverseCount,
      candidateCounts,
    };
  }

  if (input.killSwitchEffective) {
    return {
      tone: "blocked",
      headline: "Kill switch activo",
      detail: "Nuevas entradas bloqueadas. Revisa riesgo antes de operar.",
      regimeHint,
      pendingConfirm,
      vetoed,
      deferred,
      estudioUniverseCount,
      candidateCounts,
    };
  }

  if (input.entriesBlocked || vetoed > 0) {
    return {
      tone: "selective",
      headline: "Condiciones selectivas",
      detail: [
        estudioPrefix,
        `${candidateCounts.ready} listos · ${candidateCounts.blocked} bloqueados · ${pendingConfirm} pendiente(s) de confirmación`,
      ]
        .filter(Boolean)
        .join(" · "),
      regimeHint,
      pendingConfirm,
      vetoed,
      deferred,
      estudioUniverseCount,
      candidateCounts,
    };
  }

  const actionable = candidateCounts.ready + candidateCounts.prepared;
  const noOperationsToday = actionable === 0 && candidateCounts.ready === 0;
  const boardWatchHint =
    candidateCounts.watch > 0
      ? `${candidateCounts.watch} WATCH en board (≠ tamaño Estudio)`
      : "0 WATCH en board";

  return {
    tone: "operational",
    headline:
      noOperationsToday && pendingConfirm === 0
        ? "Hoy no hay operaciones recomendadas"
        : actionable > 0
          ? "Sesión operativa"
          : "Sin entradas urgentes",
    detail:
      noOperationsToday && pendingConfirm === 0
        ? [
            estudioPrefix,
            boardWatchHint,
            `${candidateCounts.blocked} bloqueados`,
            "la decisión correcta puede ser no operar",
          ]
            .filter(Boolean)
            .join(" · ")
        : actionable > 0
          ? [
              estudioPrefix,
              `${actionable} candidato(s) preparados · ${pendingConfirm} en cola Confirm`,
            ]
              .filter(Boolean)
              .join(" · ")
          : [
              estudioPrefix,
              boardWatchHint,
              "puede ser una buena decisión no operar",
            ]
              .filter(Boolean)
              .join(" · "),
    regimeHint,
    pendingConfirm,
    vetoed,
    deferred,
    estudioUniverseCount,
    candidateCounts,
  };
}

export function buildMesaCandidateGroups(
  board: DecisionBoardV1 | null | undefined,
  studiesByInstrument: Map<string, DecisionJournalStudyViewV1>,
  entriesBlocked: boolean,
) {
  if (!board) return [];
  const rows = enrichMesaCandidates(
    filterMesaEntryQueue(buildMesaEntryQueue(board), {
      statuses: [...MESA_ENTRY_GROUP_ORDER].filter((s) => s !== "EXPIRED"),
    }),
    board,
    studiesByInstrument,
  );
  const grouped = groupMesaEntryQueue(rows);
  return grouped.map((group) => ({
    ...group,
    label: MESA_CANDIDATE_GROUP_LABEL[group.status] ?? group.label,
    items: group.items as MesaCandidateRowV1[],
    entriesBlocked,
  }));
}

export function studiesByInstrumentMap(
  studies: DecisionJournalStudyViewV1[],
): Map<string, DecisionJournalStudyViewV1> {
  const map = new Map<string, DecisionJournalStudyViewV1>();
  for (const study of studies) {
    map.set(study.instrumentId, study);
  }
  return map;
}

/** V1.18 L1 — índice por decisionId (origen Position→Package). */
export function studiesByDecisionIdMap(
  studies: DecisionJournalStudyViewV1[],
): Map<string, DecisionJournalStudyViewV1> {
  const map = new Map<string, DecisionJournalStudyViewV1>();
  for (const study of studies) {
    const id = study.decisionId?.trim();
    if (id) map.set(id, study);
  }
  return map;
}

export type PositionStudyPairV1 = {
  /** Study cuyo decisionId === tradePlanId (origen). */
  originStudy: DecisionJournalStudyViewV1 | null;
  /** Último study del instrumento (evolución / Next Action). */
  evolutionStudy: DecisionJournalStudyViewV1 | null;
};

/**
 * Soft-join por instrumento solo para evolución.
 * Origen exige match por decisionId (= operational.decisionId ?? tradePlanId).
 */
export function pickPositionStudies(
  position: {
    instrumentId: string;
    operational?: {
      decisionId?: string | null;
      tradePlanId?: string | null;
    } | null;
  },
  studiesByDecisionId: Map<string, DecisionJournalStudyViewV1>,
  studiesByInstrument: Map<string, DecisionJournalStudyViewV1>,
): PositionStudyPairV1 {
  const originKey =
    position.operational?.decisionId?.trim() ||
    position.operational?.tradePlanId?.trim() ||
    null;
  const originStudy = originKey
    ? (studiesByDecisionId.get(originKey) ?? null)
    : null;
  const evolutionStudy = studiesByInstrument.get(position.instrumentId) ?? null;
  return { originStudy, evolutionStudy };
}

export function buildMesaActionQueue(
  board: DecisionBoardV1 | null | undefined,
): HoyQueueItemV1[] {
  if (!board) return [];
  return buildActionQueue(board);
}
