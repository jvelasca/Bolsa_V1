/**
 * Opportunity Discovery V1 — funnel + ranking (≠ Action Queue).
 *
 * Fuente: universo configurado + último scan + decision studies.
 * Decision Board solo aporta overlay de gate/status (operability).
 * Ranking ≠ BUY ≠ Permission. Provisional.
 *
 * @see ADR-039 · RFC-008 Opportunity≠Permission · plan V1.19
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import { MESA_ENTRY_STATUS_LABEL } from "./mesa-entry-queue.js";
import {
  computeOperationalPriority,
  type OperationalPriorityV1,
  type PortfolioContextForPriorityV1,
} from "./operational-priority.js";
import {
  opportunityQualityLabel,
  projectOpportunityEvidence,
} from "./opportunity-evidence.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";

/** Umbral recomendado para “alta calidad” / TOP. */
export const OPPORTUNITY_HIGH_QUALITY_THRESHOLD = 75;

/** TOP mostrado en Mesa (superficie principal). */
export const OPPORTUNITY_TOP_N = 5;

/** Scan sin actualizar → stale (horas). */
export const OPPORTUNITY_SCAN_STALE_HOURS = 48;

/** Study caducado para funnel “analizadas” (horas). */
export const OPPORTUNITY_STUDY_FRESH_HOURS = 7 * 24;

export type OpportunityCategoryV1 =
  | "TOP"
  | "WATCH"
  | "NOT_FOR_PORTFOLIO"
  | "STALE"
  | "BLOCKED";

export const OPPORTUNITY_CATEGORY_LABEL: Record<OpportunityCategoryV1, string> =
  {
    TOP: "Recomendada",
    WATCH: "Vigilancia",
    NOT_FOR_PORTFOLIO: "Interesante — no para mi cartera",
    STALE: "Buena — datos pendientes",
    BLOCKED: "Bloqueada",
  };

/** Embudo honesto de lo que sí se midió hoy. */
export type OpportunityFunnelV1 = {
  universeCount: number;
  screenedCount: number;
  hitCount: number;
  analyzedCount: number;
  setupCount: number;
  portfolioFitCount: number;
  operableCount: number;
  asOf: string | null;
  universeListId: string | null;
  scanStale: boolean;
  provisional: true;
};

export type OpportunityRankRowV1 = {
  symbol: string;
  instrumentId: string | null;
  quality: number;
  qualityLabel: string;
  suitability: number;
  operability: number;
  category: OpportunityCategoryV1;
  categoryReason: string | null;
  /** Rank 1..N solo en superficie TOP; null fuera. */
  rank: number | null;
  candidate: MesaCandidateRowV1;
  operationalPriority: OperationalPriorityV1;
};

export type OpportunityRankingV1 = {
  funnel: OpportunityFunnelV1;
  all: OpportunityRankRowV1[];
  /** Superficie principal — hasta TOP_N de categoría TOP (o mejores si no hay TOP). */
  top: OpportunityRankRowV1[];
  maxQuality: number;
  highQualityThreshold: number;
  /** Semántica explícita: ranking informativo ≠ ejecutable. */
  impliesOperable: false;
  provisional: true;
};

export type OpportunityScanHitInputV1 = {
  instrumentId: string;
  symbol: string;
};

export type OpportunityDiscoveryInputV1 = {
  studies: ReadonlyArray<DecisionJournalStudyViewV1>;
  /** Hits del último scan completado (opcional). */
  scanHits?: ReadonlyArray<OpportunityScanHitInputV1>;
  /** Instrumentos evaluados en el último scan (0 si no hay scan). */
  screenedCount?: number;
  hitCount?: number;
  /** Tamaño del universo configurado (lista). */
  universeCount?: number;
  universeListId?: string | null;
  scanUpdatedAt?: string | null;
  board?: DecisionBoardV1 | null;
  priorityCtx?: PortfolioContextForPriorityV1;
  now?: Date;
  studyFreshHours?: number;
  scanStaleHours?: number;
  topN?: number;
  highQualityThreshold?: number;
};

type BoardOverlay = {
  status: TradePlanStatusV1;
  gate: string;
};

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

function finiteNonNeg(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n >= 0;
}

function hoursAgo(iso: string | null | undefined, now: Date): number | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  return (now.getTime() - t.getTime()) / (1000 * 60 * 60);
}

function isStudyFresh(
  study: DecisionJournalStudyViewV1,
  now: Date,
  freshHours: number,
): boolean {
  if (study.vigencia === "expired") return false;
  const age = hoursAgo(study.studiedAt, now);
  if (age == null) return false;
  return age <= freshHours;
}

function hasSetup(
  study: DecisionJournalStudyViewV1 | null | undefined,
): boolean {
  if (!study) return false;
  return (
    finiteNonNeg(study.strength) &&
    study.strength > 0 &&
    finitePositive(study.expectedRR)
  );
}

function boardOverlayBySymbol(
  board: DecisionBoardV1 | null | undefined,
): Map<string, BoardOverlay> {
  const map = new Map<string, BoardOverlay>();
  if (!board) return map;

  for (const session of board.decisionSessions) {
    const symbol = session.symbol?.trim().toUpperCase();
    if (!symbol) continue;
    const status =
      (session.tradePlan?.status as TradePlanStatusV1 | undefined) ?? "WATCH";
    map.set(symbol, { status, gate: session.gate || "PASS" });
  }
  for (const row of board.semiF3Queue) {
    const symbol = row.symbol?.trim().toUpperCase();
    if (!symbol) continue;
    const payload =
      row.extra && typeof row.extra === "object"
        ? (row.extra as {
            payload?: { tradePlan?: { status?: string } };
            tradePlan?: { status?: string };
          })
        : null;
    const planStatus =
      payload?.payload?.tradePlan?.status ?? payload?.tradePlan?.status;
    const status = (planStatus as TradePlanStatusV1 | undefined) ?? "WATCH";
    if (!map.has(symbol)) {
      map.set(symbol, { status, gate: "PASS" });
    }
  }
  return map;
}

function buildCandidateFromStudy(
  study: DecisionJournalStudyViewV1,
  overlay: BoardOverlay | undefined,
): MesaCandidateRowV1 {
  const symbol = (
    study.symbol?.trim() ||
    study.instrumentId ||
    "UNKNOWN"
  ).toUpperCase();
  const status =
    overlay?.status ??
    (study.tradePlanStatus as TradePlanStatusV1 | null) ??
    "WATCH";
  return {
    symbol,
    status,
    statusLabel: MESA_ENTRY_STATUS_LABEL[status] ?? status,
    gate: overlay?.gate ?? "PASS",
    instrumentId: study.instrumentId || null,
    study,
  };
}

function buildCandidateFromHit(
  hit: OpportunityScanHitInputV1,
  overlay: BoardOverlay | undefined,
): MesaCandidateRowV1 {
  const symbol = hit.symbol.trim().toUpperCase();
  const status = overlay?.status ?? "WATCH";
  return {
    symbol,
    status,
    statusLabel: MESA_ENTRY_STATUS_LABEL[status] ?? status,
    gate: overlay?.gate ?? "PASS",
    instrumentId: hit.instrumentId || null,
    study: null,
  };
}

function categorize(
  priority: OperationalPriorityV1,
  candidate: MesaCandidateRowV1,
  now: Date,
  freshHours: number,
  highQualityThreshold: number,
): { category: OpportunityCategoryV1; reason: string | null } {
  const study = candidate.study;
  const stale =
    study != null &&
    (study.vigencia === "expired" || !isStudyFresh(study, now, freshHours));
  const qualityOk = priority.quality.value >= highQualityThreshold;
  const qualityHigh = priority.quality.value >= 70;
  const fitOk = priority.suitability.value >= 50;

  if (stale && (qualityOk || qualityHigh) && fitOk) {
    return {
      category: "STALE",
      reason: "Datos de análisis desactualizados — no operable hasta refrescar",
    };
  }

  if (qualityHigh && !fitOk) {
    return {
      category: "NOT_FOR_PORTFOLIO",
      reason:
        priority.suitability.factors[0] ?? "Encaje de cartera insuficiente",
    };
  }

  if (
    !priority.operability.operable ||
    candidate.gate === "VETO" ||
    candidate.status === "BLOCKED"
  ) {
    const reason =
      priority.operability.blockReasons[0] ??
      (candidate.gate === "VETO" ? "Veto de gate" : "No ejecutable ahora");
    return { category: "BLOCKED", reason };
  }

  if (
    priority.verdict === "OPERABLE" &&
    priority.quality.value >= highQualityThreshold &&
    fitOk
  ) {
    return { category: "TOP", reason: null };
  }

  return { category: "WATCH", reason: null };
}

/**
 * Construye funnel + ranking de oportunidades.
 * No usa buildActionQueue — Discovery ≠ atención operativa.
 */
export function buildOpportunityRanking(
  input: OpportunityDiscoveryInputV1,
): OpportunityRankingV1 {
  const now = input.now ?? new Date();
  const freshHours = input.studyFreshHours ?? OPPORTUNITY_STUDY_FRESH_HOURS;
  const scanStaleHours = input.scanStaleHours ?? OPPORTUNITY_SCAN_STALE_HOURS;
  const topN = input.topN ?? OPPORTUNITY_TOP_N;
  const highQualityThreshold =
    input.highQualityThreshold ?? OPPORTUNITY_HIGH_QUALITY_THRESHOLD;
  const priorityCtx = input.priorityCtx ?? {};
  const overlay = boardOverlayBySymbol(input.board);

  const byKey = new Map<string, MesaCandidateRowV1>();

  for (const study of input.studies) {
    const candidate = buildCandidateFromStudy(
      study,
      overlay.get((study.symbol?.trim() || "").toUpperCase()),
    );
    const key = candidate.instrumentId || candidate.symbol || study.sessionId;
    const prev = byKey.get(key);
    if (
      !prev ||
      (study.studiedAt &&
        (!prev.study?.studiedAt || study.studiedAt > prev.study.studiedAt))
    ) {
      byKey.set(key, candidate);
    }
  }

  for (const hit of input.scanHits ?? []) {
    const symbol = hit.symbol.trim().toUpperCase();
    const key = hit.instrumentId || symbol;
    if (byKey.has(key) || byKey.has(symbol)) continue;
    // Evitar duplicar por símbolo si ya hay study
    let exists = false;
    for (const row of byKey.values()) {
      if (row.symbol === symbol) {
        exists = true;
        break;
      }
    }
    if (exists) continue;
    byKey.set(key, buildCandidateFromHit(hit, overlay.get(symbol)));
  }

  const candidates = [...byKey.values()];
  const ranked: OpportunityRankRowV1[] = candidates.map((candidate) => {
    const priority = computeOperationalPriority(candidate, {
      ...priorityCtx,
      candidateSector:
        priorityCtx.candidateSector ??
        (candidate.instrumentId
          ? priorityCtx.sectorByInstrumentId?.[candidate.instrumentId]
          : null) ??
        null,
    });
    const evidence = projectOpportunityEvidence(candidate);
    const { category, reason } = categorize(
      priority,
      candidate,
      now,
      freshHours,
      highQualityThreshold,
    );
    return {
      symbol: candidate.symbol,
      instrumentId: candidate.instrumentId,
      quality: evidence.qualityValue,
      qualityLabel: evidence.label,
      suitability: priority.suitability.value,
      operability: priority.operability.value,
      category,
      categoryReason: reason,
      rank: null,
      candidate,
      operationalPriority: priority,
    };
  });

  ranked.sort((a, b) => {
    const catOrder: Record<OpportunityCategoryV1, number> = {
      TOP: 0,
      WATCH: 1,
      STALE: 2,
      NOT_FOR_PORTFOLIO: 3,
      BLOCKED: 4,
    };
    if (catOrder[a.category] !== catOrder[b.category]) {
      return catOrder[a.category] - catOrder[b.category];
    }
    if (b.quality !== a.quality) return b.quality - a.quality;
    return b.suitability - a.suitability;
  });

  const topSource =
    ranked.filter((r) => r.category === "TOP").length > 0
      ? ranked.filter((r) => r.category === "TOP")
      : ranked.filter((r) => r.category === "WATCH" || r.category === "TOP");
  const top = topSource.slice(0, topN).map((row, i) => ({
    ...row,
    rank: i + 1,
  }));

  const analyzed = input.studies.filter((s) =>
    isStudyFresh(s, now, freshHours),
  );
  const withSetup = analyzed.filter((s) => hasSetup(s));

  let portfolioFitCount = 0;
  let operableCount = 0;
  for (const row of ranked) {
    if (
      row.candidate.study &&
      isStudyFresh(row.candidate.study, now, freshHours) &&
      hasSetup(row.candidate.study)
    ) {
      if (row.suitability >= 50) portfolioFitCount += 1;
      if (row.operationalPriority.verdict === "OPERABLE") operableCount += 1;
    }
  }

  const scanAgeH = hoursAgo(input.scanUpdatedAt ?? null, now);
  const screenedCount = input.screenedCount ?? 0;
  const scanStale =
    screenedCount === 0 || scanAgeH == null || scanAgeH > scanStaleHours;

  const maxQuality =
    ranked.length === 0 ? 0 : Math.max(...ranked.map((r) => r.quality));

  const funnel: OpportunityFunnelV1 = {
    universeCount: input.universeCount ?? 0,
    screenedCount,
    hitCount: input.hitCount ?? input.scanHits?.length ?? 0,
    analyzedCount: analyzed.length,
    setupCount: withSetup.length,
    portfolioFitCount,
    operableCount,
    asOf: input.scanUpdatedAt ?? now.toISOString(),
    universeListId: input.universeListId ?? null,
    scanStale,
    provisional: true,
  };

  return {
    funnel,
    all: ranked,
    top,
    maxQuality,
    highQualityThreshold,
    impliesOperable: false,
    provisional: true,
  };
}

/** Resumen de bandas de calidad para copy Mesa. */
export function opportunityQualityBandCounts(
  rows: ReadonlyArray<Pick<OpportunityRankRowV1, "quality">>,
): Record<string, number> {
  const counts: Record<string, number> = {
    Excelente: 0,
    Alta: 0,
    Buena: 0,
    Débil: 0,
    "No atractiva": 0,
  };
  for (const row of rows) {
    const label = opportunityQualityLabel(row.quality);
    counts[label] = (counts[label] ?? 0) + 1;
  }
  return counts;
}
