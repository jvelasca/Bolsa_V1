/**
 * V1.54 — Operating Desk: proyección autoDesk / CandidateSnapshot → cubos §B.7.
 * Composición sobre EOT + exception facts. Ranking ≠ BUY · AUTO ≠ COMPRAR.
 *
 * @see packages/shared/src/cognitive/daily-desk.ts
 * @see packages/shared/src/cognitive/paper-daily-report.ts
 */

import {
  DECISION_JOURNAL_STUDY_ARTIFACT,
  DECISION_JOURNAL_STUDY_SCHEMA,
  journalStudyGeometry,
  type DecisionJournalStudyViewV1,
} from "./decision-journal-study.js";
import {
  buildDailyDeskInbox,
  dailyDeskItemFromEot,
  finalizeDailyDeskInbox,
  type BuildDailyDeskInboxInputV1,
  type DailyDeskInboxV1,
  type DailyDeskItemV1,
} from "./daily-desk.js";
import { buildEntryOperatingTruth } from "./entry-operating-truth.js";
import {
  ENTRIES_BLOCKED_CTA_LABEL,
  ENTRIES_BLOCKED_PROPOSE_MSG,
} from "./entry-operating-copy.js";
import {
  buildPaperAutoPosture,
  type PaperAutoPostureV1,
} from "./paper-auto-posture.js";
import type {
  DailyDeskExceptionFactV1,
  DailyDeskExceptionKindV1,
  PaperDailyReportV1,
  PaperDeskCandidateSnapshotV1,
  PaperDeskEntryReasonCodeV1,
} from "./paper-daily-report.js";
import { formatPositionDecisionPhrase } from "./position-decision-copy.js";
import { buildPositionDecision } from "./position-decision.js";
import {
  buildPositionStateFromFill,
  type PositionStateV1,
} from "./position-state.js";
import type { TradePlanV1, TradePlanStatusV1 } from "./trade-plan.js";

export type ProjectAutoDeskCandidatesInputV1 = {
  autoDesk?: PaperDailyReportV1 | null;
  exceptionFacts?: DailyDeskExceptionFactV1[] | null;
  portfolioReconStatus?: string | null;
  excludeInstrumentIds?: ReadonlySet<string>;
  confirmQueueInstrumentIds?: readonly string[];
  pendingInstrumentIds?: readonly string[];
  entriesBlocked?: boolean;
  paperAuto?: PaperAutoPostureV1 | null;
};

const EMPTY_CONSENSUS = {
  bullish: 0,
  bearish: 0,
  neutral: 0,
  total: 0,
} as const;

const ENTRY_DENY_PHRASE: Partial<Record<PaperDeskEntryReasonCodeV1, string>> = {
  ENTRY_RISK_LIMIT: "Gate de apertura DENY — ranking ≠ autorización.",
  ENTRY_INVALID_STOP: "Stop inválido — no autoriza entrada.",
  ENTRY_NO_TRIGGER: "Sin disparador — ranking ≠ BUY.",
  ENTRY_STALE_DATA: "Datos obsoletos — no proponer.",
  ENTRY_MANDATE_BLOCK: "Mandato en veto — no autoriza entrada.",
  ENTRY_MARKET_CLOSED: "Mercado cerrado — sin propuesta.",
  ENTRY_ENV_BLOCKED: "AUTO bloqueado por entorno — sin ejecución.",
};

export const POSITION_BIRTH_FAILED_PHRASE =
  "Fill ejecutado pero la posición no nació — reconciliar antes de reintentar.";

export const POSITION_BIRTH_FAILED_CTA = "Reconciliar";

const RECON_DRIFT_PHRASE =
  "No operes: discrepancia de cartera. Reconcilia antes de cualquier acción.";

const RECON_UNAVAILABLE_PHRASE =
  "Reconciliación no disponible — no abrir hasta certificar cartera.";

export function isCandidateDenied(
  candidate: PaperDeskCandidateSnapshotV1,
): boolean {
  if (candidate.reasonCode) return true;
  return (candidate.vetoes?.length ?? 0) > 0;
}

export function candidateTradePlanStatus(
  candidate: PaperDeskCandidateSnapshotV1,
): TradePlanStatusV1 | null {
  const status = candidate.tradePlan?.status;
  if (
    status === "WATCH" ||
    status === "ARMED" ||
    status === "TRIGGERED" ||
    status === "BLOCKED" ||
    status === "EXPIRED"
  ) {
    return status;
  }
  return null;
}

export function studyFromCandidateSnapshot(
  candidate: PaperDeskCandidateSnapshotV1,
): DecisionJournalStudyViewV1 {
  const plan = candidate.tradePlan ?? null;
  const geom = journalStudyGeometry(plan);
  const status = candidateTradePlanStatus(candidate) ?? "TRIGGERED";
  const studiedAt =
    candidate.analysisAsOf?.trim() ||
    candidate.marketAsOf?.trim() ||
    candidate.executionAsOf?.trim() ||
    new Date().toISOString();

  return {
    artifactType: DECISION_JOURNAL_STUDY_ARTIFACT,
    schemaVersion: DECISION_JOURNAL_STUDY_SCHEMA,
    sessionId: candidate.decisionId,
    decisionId: candidate.decisionId,
    instrumentId: candidate.instrumentId,
    symbol: candidate.symbol ?? candidate.instrumentId,
    name: null,
    studiedAt,
    ageMs: null,
    period: null,
    timeframe: null,
    opinion: null,
    status: "in_progress",
    strength: candidate.score,
    strengthBand: null,
    vigencia: null,
    entry: candidate.entry ?? geom.entry,
    stop: candidate.structuralStop ?? geom.stop,
    target1: candidate.target1 ?? geom.target1,
    target2: candidate.target2 ?? geom.target2,
    expectedRR: candidate.expectedRr ?? geom.expectedRR,
    riskAmount: candidate.riskAmount ?? geom.riskAmount,
    quantity: geom.quantity,
    initialRiskR: geom.initialRiskR,
    positionValue: geom.positionValue,
    direction: geom.direction,
    hasOperationalPlan: geom.hasOperationalPlan || Boolean(plan),
    userThesis: null,
    decisionSummary: candidate.humanMessage ?? null,
    analysisNotes: [],
    trends: [],
    consensus: { ...EMPTY_CONSENSUS },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: status,
    action: null,
  };
}

export function formatCandidateDenyPhrase(
  candidate: PaperDeskCandidateSnapshotV1,
): string {
  if (candidate.humanMessage?.trim()) {
    return candidate.humanMessage.trim();
  }
  if (candidate.reasonCode && ENTRY_DENY_PHRASE[candidate.reasonCode]) {
    return ENTRY_DENY_PHRASE[candidate.reasonCode]!;
  }
  return ENTRIES_BLOCKED_PROPOSE_MSG;
}

function formatCandidateReason(
  candidate: PaperDeskCandidateSnapshotV1,
): string {
  const bits: string[] = [`#${candidate.rank}`];
  if (candidate.templateId?.trim()) bits.push(candidate.templateId.trim());
  if (candidate.reasonCode) bits.push(candidate.reasonCode);
  return bits.join(" · ");
}

function paperAutoFromAutoDesk(
  autoDesk: PaperDailyReportV1,
  override?: PaperAutoPostureV1 | null,
): PaperAutoPostureV1 | null {
  if (override) return override;
  return buildPaperAutoPosture({
    bookMode: "auto",
    autoArmed: true,
    paperDExecuteEnv: autoDesk.paperDExecute,
  });
}

function deskItemFromDeniedCandidate(
  candidate: PaperDeskCandidateSnapshotV1,
): DailyDeskItemV1 {
  const symbol = candidate.symbol ?? candidate.instrumentId;
  return {
    id: `auto-deny-${candidate.instrumentId}`,
    kind: "entry",
    bucket: "no_operar",
    symbol,
    attention: "BLOCKED",
    phrase: formatCandidateDenyPhrase(candidate),
    reason: formatCandidateReason(candidate),
    ctaLabel: ENTRIES_BLOCKED_CTA_LABEL,
    ctaKind: "none",
    phaseLabel: null,
    instrumentId: candidate.instrumentId,
  };
}

export function dailyDeskItemFromCandidateSnapshot(
  candidate: PaperDeskCandidateSnapshotV1,
  opts: {
    paperAuto?: PaperAutoPostureV1 | null;
    inConfirmQueue?: boolean;
    orderPendingFill?: boolean;
    entriesBlocked?: boolean;
  } = {},
): DailyDeskItemV1 | null {
  if (isCandidateDenied(candidate)) {
    return deskItemFromDeniedCandidate(candidate);
  }

  const status = candidateTradePlanStatus(candidate);
  if (status !== "TRIGGERED" && status !== "ARMED") {
    return null;
  }

  const study = studyFromCandidateSnapshot(candidate);
  const eot = buildEntryOperatingTruth({
    study,
    hasOpenPosition: false,
    inConfirmQueue: opts.inConfirmQueue === true,
    orderPendingFill: opts.orderPendingFill === true,
    inEstudio: true,
    entriesBlocked: opts.entriesBlocked === true,
    paperAuto: opts.paperAuto ?? null,
    asOf: study.studiedAt,
  });
  if (!eot) return null;

  const item = dailyDeskItemFromEot(eot);
  // AUTO disparada sigue siendo oportunidad aunque CTA sea none (≠ COMPRAR).
  if (
    item.ctaKind === "none" &&
    item.bucket === "oportunidades" &&
    status !== "TRIGGERED"
  ) {
    item.bucket = "no_operar";
  }
  if (status === "TRIGGERED" && !isCandidateDenied(candidate)) {
    item.bucket = "oportunidades";
    item.attention =
      eot.phase === "disparada" || eot.phase === "propuesta"
        ? "URGENT"
        : item.attention;
  }
  return {
    ...item,
    id: `auto-entry-${candidate.instrumentId}`,
    reason: formatCandidateReason(candidate),
  };
}

export function exceptionPhrase(kind: DailyDeskExceptionKindV1): string {
  switch (kind) {
    case "position_birth_failed":
      return POSITION_BIRTH_FAILED_PHRASE;
    case "portfolio_recon_drift":
      return RECON_DRIFT_PHRASE;
    case "portfolio_recon_unavailable":
      return RECON_UNAVAILABLE_PHRASE;
    default:
      return "Excepción operativa — requiere acción humana.";
  }
}

export function exceptionCta(kind: DailyDeskExceptionKindV1): string {
  switch (kind) {
    case "position_birth_failed":
      return POSITION_BIRTH_FAILED_CTA;
    case "portfolio_recon_drift":
    case "portfolio_recon_unavailable":
      return "Reconciliar";
    default:
      return "Revisar";
  }
}

export function dailyDeskItemFromExceptionFact(
  fact: DailyDeskExceptionFactV1,
): DailyDeskItemV1 {
  const symbol = fact.symbol?.trim() || fact.instrumentId?.trim() || "Cartera";
  const phrase = fact.message?.trim() || exceptionPhrase(fact.kind);
  return {
    id: `exception-${fact.kind}-${fact.instrumentId ?? fact.decisionId ?? symbol}`,
    kind: "incident",
    bucket: "requiere_accion",
    symbol,
    attention: fact.kind === "position_birth_failed" ? "URGENT" : "BLOCKED",
    phrase,
    reason: fact.kind,
    ctaLabel: exceptionCta(fact.kind),
    ctaKind: "review",
    phaseLabel: null,
    instrumentId: fact.instrumentId ?? undefined,
  };
}

export function reconPhraseFromPortfolioStatus(
  portfolioReconStatus?: string | null,
): string | null {
  const status = portfolioReconStatus?.trim().toLowerCase();
  if (status === "drift") return RECON_DRIFT_PHRASE;
  if (status === "unavailable") return RECON_UNAVAILABLE_PHRASE;
  return null;
}

/** Proyecta candidatos autoDesk → ítems Desk (🟢 o 🟡 bloqueados). GP-DESK-UI-08: null-safe. */
export function projectAutoDeskCandidates(
  input: ProjectAutoDeskCandidatesInputV1,
): DailyDeskItemV1[] {
  const autoDesk = input.autoDesk ?? null;
  if (!autoDesk) return [];

  const exclude = input.excludeInstrumentIds ?? new Set<string>();
  const confirmIds = new Set(input.confirmQueueInstrumentIds ?? []);
  const pendingIds = new Set(input.pendingInstrumentIds ?? []);
  const paperAuto = paperAutoFromAutoDesk(autoDesk, input.paperAuto);
  const rows = [
    ...(autoDesk.entry.candidates ?? []),
    ...(autoDesk.entry.skipped ?? []),
  ];

  const items: DailyDeskItemV1[] = [];
  const seen = new Set<string>();

  for (const candidate of rows) {
    const instId = candidate.instrumentId;
    if (!instId || exclude.has(instId) || seen.has(instId)) continue;

    const item = dailyDeskItemFromCandidateSnapshot(candidate, {
      paperAuto,
      inConfirmQueue: confirmIds.has(instId),
      orderPendingFill: pendingIds.has(instId),
      entriesBlocked: input.entriesBlocked === true,
    });
    if (!item) continue;
    seen.add(instId);
    items.push(item);
  }

  return items;
}

/** Proyecta exception facts + recon portfolio → 🔴 requiere_accion. */
export function projectDeskExceptionFacts(
  input: ProjectAutoDeskCandidatesInputV1,
): DailyDeskItemV1[] {
  const items: DailyDeskItemV1[] = [];
  const seen = new Set<string>();

  for (const fact of input.exceptionFacts ?? []) {
    const item = dailyDeskItemFromExceptionFact(fact);
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    items.push(item);
  }

  const reconPhrase = reconPhraseFromPortfolioStatus(
    input.portfolioReconStatus,
  );
  if (reconPhrase && !items.some((i) => i.reason.includes("recon"))) {
    const status = input.portfolioReconStatus?.trim().toLowerCase();
    const kind: DailyDeskExceptionKindV1 =
      status === "unavailable"
        ? "portfolio_recon_unavailable"
        : "portfolio_recon_drift";
    items.push(
      dailyDeskItemFromExceptionFact({
        kind,
        symbol: "Cartera",
        message: reconPhrase,
      }),
    );
  }

  return items;
}

export type BuildOperatingDeskInboxInputV1 = BuildDailyDeskInboxInputV1 &
  ProjectAutoDeskCandidatesInputV1;

/** V1.54 — inbox Desk clásico + proyección autoDesk/excepciones. */
export function buildOperatingDeskInbox(
  input: BuildOperatingDeskInboxInputV1,
): DailyDeskInboxV1 {
  const base = buildDailyDeskInbox(input);
  const exclude = new Set<string>();
  for (const item of base.items) {
    if (item.instrumentId) exclude.add(item.instrumentId);
  }

  const autoItems = projectAutoDeskCandidates({
    ...input,
    excludeInstrumentIds: exclude,
  });
  const exceptionItems = projectDeskExceptionFacts(input);
  return finalizeDailyDeskInbox(
    [...base.items, ...autoItems, ...exceptionItems],
    base.emptyLabel,
  );
}

/** Paridad frase recon drift con position-decision-copy (GP-DESK-UI-09). */
export function reconDriftPhraseParityCheck(
  portfolioReconStatus: string,
): boolean {
  const projected = reconPhraseFromPortfolioStatus(portfolioReconStatus);
  if (!projected) return true;

  const plan: TradePlanV1 = {
    decisionId: "dec-parity",
    instrumentId: "inst-parity",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    target1: 105,
    target2: 110,
  };
  const position: PositionStateV1 | null = buildPositionStateFromFill(plan, {
    price: 100,
    quantity: 10,
    filledAt: "2026-08-28T10:00:00Z",
  });
  if (!position) return false;

  const decision = buildPositionDecision({
    position,
    signals: { markPrice: 102 },
    templateId: "moderate",
    portfolioReconStatus,
  });
  if (!decision) return false;
  return formatPositionDecisionPhrase(decision) === projected;
}
