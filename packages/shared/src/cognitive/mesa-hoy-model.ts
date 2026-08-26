/**
 * Compositor read-only Mesa · Hoy (ADR-037).
 * Une Decision Board, portfolio, incidentes y studies sin endpoints nuevos.
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { OperationalIncidentV1 } from "./operational-incident.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import {
  buildActionQueue,
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
    return { ...row, instrumentId, study };
  });
}

export function buildMesaSessionState(
  board: DecisionBoardV1 | null | undefined,
  input: {
    entriesBlocked: boolean;
    killSwitchEffective?: boolean;
    incidentCount?: number;
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
      candidateCounts,
    };
  }

  if (input.entriesBlocked || vetoed > 0) {
    return {
      tone: "selective",
      headline: "Condiciones selectivas",
      detail: `${candidateCounts.ready} listos · ${candidateCounts.blocked} bloqueados · ${pendingConfirm} pendiente(s) de confirmación`,
      regimeHint,
      pendingConfirm,
      vetoed,
      deferred,
      candidateCounts,
    };
  }

  const actionable = candidateCounts.ready + candidateCounts.prepared;
  return {
    tone: "operational",
    headline: actionable > 0 ? "Sesión operativa" : "Sin entradas urgentes",
    detail:
      actionable > 0
        ? `${actionable} candidato(s) preparados · ${pendingConfirm} en cola Confirm`
        : `${candidateCounts.watch} en vigilancia · puede ser una buena decisión no operar`,
    regimeHint,
    pendingConfirm,
    vetoed,
    deferred,
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

export function buildMesaActionQueue(
  board: DecisionBoardV1 | null | undefined,
): HoyQueueItemV1[] {
  if (!board) return [];
  return buildActionQueue(board);
}
