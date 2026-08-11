import type { ResearchTrialDto } from "@bolsa/shared";

export type OosEvidenceKind = "none" | "holdout" | "walkforward" | "cpcv";

/** Compact OOS / walk-forward / CPCV signal for the pre-paper checklist. */
export type OosEvidence = {
  kind: OosEvidenceKind;
  oosScore?: number;
  oosReturnPct?: number;
  meanOosScore?: number;
  stdOosScore?: number;
  nFolds?: number;
  pathCount?: number;
  walkForwardEfficiency?: number;
  oosCv?: number;
  positiveOosFoldShare?: number;
  wfeSource?: "lab_score" | "sharpe";
  /** Lab EdgeReport lite (P3.M). */
  credibility?: number;
  edgeBand?: string;
  monteCarloPValue?: number;
  dsr?: number;
  /** CSCV PBO lab (P3.N). */
  pbo?: number;
  /** P8 cognitive edge_reports id when persisted. */
  persistedEdgeReportId?: string;
  /** Strategy that carried this evidence (session stash after Optimizar). */
  strategyId?: string;
};

function edgeFieldsFromBlocks(
  blocks: Record<string, unknown>,
): Pick<
  OosEvidence,
  | "credibility"
  | "edgeBand"
  | "monteCarloPValue"
  | "dsr"
  | "pbo"
  | "persistedEdgeReportId"
> {
  const er = asRecord(blocks.edgeReport);
  const pboBlock = asRecord(blocks.pbo);
  const cpcv = asRecord(blocks.cpcv);
  const cpcvPbo = asRecord(cpcv?.pbo);
  const lab = asRecord(blocks.labEvidence);
  const suite = er ? asRecord(er.suite) : null;
  return {
    credibility: asFiniteNumber(er?.credibility),
    edgeBand: typeof er?.band === "string" ? er.band : undefined,
    monteCarloPValue: asFiniteNumber(suite?.monteCarloPValue),
    dsr: asFiniteNumber(suite?.dsr),
    pbo:
      asFiniteNumber(pboBlock?.pbo) ??
      asFiniteNumber(cpcvPbo?.pbo) ??
      asFiniteNumber(lab?.pbo) ??
      asFiniteNumber(er?.pbo),
    persistedEdgeReportId:
      typeof er?.persistedEdgeReportId === "string"
        ? er.persistedEdgeReportId
        : undefined,
  };
}

const SESSION_KEY = "bolsa-optimize-oos-evidence-v1";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

/** Read OOS / WF blocks from a research trial (optimize ledger). */
export function extractOosEvidenceFromTrial(
  trial?: ResearchTrialDto | null,
): OosEvidence {
  const blocks = asRecord(trial?.blocks ?? null);
  if (!blocks) return { kind: "none" };

  const edgeExtra = edgeFieldsFromBlocks(blocks);

  const cpcv = asRecord(blocks.cpcv);
  if (cpcv) {
    const meanOosScore = asFiniteNumber(cpcv.meanOosScore);
    if (meanOosScore != null) {
      const lab = asRecord(blocks.labEvidence);
      return {
        kind: "cpcv",
        meanOosScore,
        stdOosScore: asFiniteNumber(cpcv.stdOosScore),
        pathCount: asFiniteNumber(cpcv.pathCount),
        nFolds: asFiniteNumber(cpcv.pathCount),
        oosScore: meanOosScore,
        walkForwardEfficiency: asFiniteNumber(cpcv.walkForwardEfficiency),
        oosCv: asFiniteNumber(cpcv.oosCv),
        positiveOosFoldShare: asFiniteNumber(cpcv.positiveOosFoldShare),
        wfeSource: lab?.wfeSource === "sharpe" ? "sharpe" : "lab_score",
        ...edgeExtra,
      };
    }
  }

  const wf = asRecord(blocks.walkForward);
  if (wf) {
    const meanOosScore = asFiniteNumber(wf.meanOosScore);
    if (meanOosScore != null) {
      const lab = asRecord(blocks.labEvidence);
      return {
        kind: "walkforward",
        meanOosScore,
        stdOosScore: asFiniteNumber(wf.stdOosScore),
        nFolds: asFiniteNumber(wf.nFolds) ?? asFiniteNumber(wf.foldCount),
        oosScore: meanOosScore,
        walkForwardEfficiency: asFiniteNumber(wf.walkForwardEfficiency),
        oosCv: asFiniteNumber(wf.oosCv),
        positiveOosFoldShare: asFiniteNumber(wf.positiveOosFoldShare),
        wfeSource: lab?.wfeSource === "sharpe" ? "sharpe" : "lab_score",
        ...edgeExtra,
      };
    }
  }

  const oos = asRecord(blocks.oosMetrics);
  if (oos) {
    const oosScore = asFiniteNumber(oos.score);
    if (oosScore != null) {
      return {
        kind: "holdout",
        oosScore,
        oosReturnPct: asFiniteNumber(oos.totalReturnPct),
        ...edgeExtra,
      };
    }
  }

  return { kind: "none" };
}

/** Build evidence from an optimize API result (session stash after save/adopt). */
export function extractOosEvidenceFromOptimizeResult(result: {
  walkForward?: {
    meanOosScore: number;
    stdOosScore?: number;
    nFolds?: number;
    walkForwardEfficiency?: number | null;
    oosCv?: number | null;
    positiveOosFoldShare?: number | null;
  } | null;
  cpcv?: {
    meanOosScore: number;
    stdOosScore?: number;
    pathCount?: number;
    walkForwardEfficiency?: number | null;
    oosCv?: number | null;
    positiveOosFoldShare?: number | null;
    pbo?: { pbo?: number } | null;
  } | null;
  edgeReport?: {
    credibility?: number;
    band?: string;
    pbo?: number | null;
    persistedEdgeReportId?: string | null;
    suite?: {
      monteCarloPValue?: number | null;
      dsr?: number | null;
    };
  } | null;
  pbo?: { pbo?: number } | null;
  baseline?: {
    oosMetrics?: { score?: number; totalReturnPct?: number } | null;
  };
  trials?: Array<{
    oosMetrics?: { score?: number; totalReturnPct?: number } | null;
  }>;
}): OosEvidence {
  const edgeExtra: Pick<
    OosEvidence,
    | "credibility"
    | "edgeBand"
    | "monteCarloPValue"
    | "dsr"
    | "pbo"
    | "persistedEdgeReportId"
  > = {};
  if (result.edgeReport) {
    edgeExtra.credibility = result.edgeReport.credibility;
    edgeExtra.edgeBand = result.edgeReport.band;
    edgeExtra.monteCarloPValue =
      result.edgeReport.suite?.monteCarloPValue ?? undefined;
    edgeExtra.dsr = result.edgeReport.suite?.dsr ?? undefined;
    edgeExtra.persistedEdgeReportId =
      result.edgeReport.persistedEdgeReportId ?? undefined;
  }
  edgeExtra.pbo =
    result.pbo?.pbo ??
    result.cpcv?.pbo?.pbo ??
    result.edgeReport?.pbo ??
    undefined;
  const cpcv = result.cpcv;
  if (cpcv && Number.isFinite(cpcv.meanOosScore)) {
    return {
      kind: "cpcv",
      meanOosScore: cpcv.meanOosScore,
      stdOosScore: cpcv.stdOosScore,
      pathCount: cpcv.pathCount,
      nFolds: cpcv.pathCount,
      oosScore: cpcv.meanOosScore,
      walkForwardEfficiency:
        cpcv.walkForwardEfficiency != null &&
        Number.isFinite(cpcv.walkForwardEfficiency)
          ? cpcv.walkForwardEfficiency
          : undefined,
      oosCv:
        cpcv.oosCv != null && Number.isFinite(cpcv.oosCv)
          ? cpcv.oosCv
          : undefined,
      positiveOosFoldShare:
        cpcv.positiveOosFoldShare != null &&
        Number.isFinite(cpcv.positiveOosFoldShare)
          ? cpcv.positiveOosFoldShare
          : undefined,
      wfeSource: "lab_score",
      ...edgeExtra,
    };
  }
  const wf = result.walkForward;
  if (wf && Number.isFinite(wf.meanOosScore)) {
    return {
      kind: "walkforward",
      meanOosScore: wf.meanOosScore,
      stdOosScore: wf.stdOosScore,
      nFolds: wf.nFolds,
      oosScore: wf.meanOosScore,
      walkForwardEfficiency:
        wf.walkForwardEfficiency != null &&
        Number.isFinite(wf.walkForwardEfficiency)
          ? wf.walkForwardEfficiency
          : undefined,
      oosCv:
        wf.oosCv != null && Number.isFinite(wf.oosCv) ? wf.oosCv : undefined,
      positiveOosFoldShare:
        wf.positiveOosFoldShare != null &&
        Number.isFinite(wf.positiveOosFoldShare)
          ? wf.positiveOosFoldShare
          : undefined,
      wfeSource: "lab_score",
      ...edgeExtra,
    };
  }
  const trialOos =
    result.trials?.[0]?.oosMetrics ?? result.baseline?.oosMetrics;
  if (
    trialOos &&
    typeof trialOos.score === "number" &&
    Number.isFinite(trialOos.score)
  ) {
    return {
      kind: "holdout",
      oosScore: trialOos.score,
      oosReturnPct:
        typeof trialOos.totalReturnPct === "number"
          ? trialOos.totalReturnPct
          : undefined,
      ...edgeExtra,
    };
  }
  return { kind: "none" };
}

/**
 * Evidence to stash when saving/adopting a compare row.
 * Prefer full WF/CPCV (+ PBO/Edge) from the optimize result; never downgrade
 * multipath evidence to bare hold-out just because the row has last-path oosMetrics.
 */
export function buildOosEvidenceForAdopt(
  result:
    | Parameters<typeof extractOosEvidenceFromOptimizeResult>[0]
    | null
    | undefined,
  row?: {
    oosMetrics?: { score?: number; totalReturnPct?: number } | null;
  } | null,
): OosEvidence {
  const fromResult = result
    ? extractOosEvidenceFromOptimizeResult(result)
    : { kind: "none" as const };
  if (fromResult.kind === "walkforward" || fromResult.kind === "cpcv") {
    return fromResult;
  }
  const rowScore = row?.oosMetrics?.score;
  if (rowScore != null && Number.isFinite(rowScore)) {
    return {
      kind: "holdout",
      oosScore: rowScore,
      oosReturnPct:
        row?.oosMetrics?.totalReturnPct != null &&
        Number.isFinite(row.oosMetrics.totalReturnPct)
          ? row.oosMetrics.totalReturnPct
          : fromResult.oosReturnPct,
      credibility: fromResult.credibility,
      edgeBand: fromResult.edgeBand,
      monteCarloPValue: fromResult.monteCarloPValue,
      dsr: fromResult.dsr,
      pbo: fromResult.pbo,
      persistedEdgeReportId: fromResult.persistedEdgeReportId,
    };
  }
  return fromResult;
}

export function stashOosEvidenceForStrategy(
  strategyId: string,
  evidence: OosEvidence,
): void {
  if (typeof sessionStorage === "undefined" || evidence.kind === "none") return;
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    const map = raw ? (JSON.parse(raw) as Record<string, OosEvidence>) : {};
    map[strategyId] = { ...evidence, strategyId };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(map));
  } catch {
    // ignore quota / private mode
  }
}

export function readStashedOosEvidence(
  strategyId?: string | null,
): OosEvidence | null {
  if (!strategyId || typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const map = JSON.parse(raw) as Record<string, OosEvidence>;
    const evidence = map[strategyId];
    return evidence?.kind && evidence.kind !== "none" ? evidence : null;
  } catch {
    return null;
  }
}

/** Prefer trial ledger blocks; fall back to session stash from Optimizar → adoptar. */
export function resolveOosEvidence(opts: {
  trial?: ResearchTrialDto | null;
  strategyId?: string | null;
}): OosEvidence {
  const fromTrial = extractOosEvidenceFromTrial(opts.trial);
  if (fromTrial.kind !== "none") return fromTrial;
  return readStashedOosEvidence(opts.strategyId) ?? { kind: "none" };
}

/** Map checklist evidence → deploy body snapshot (P7). */
export function oosEvidenceToPaperLabSnapshot(
  evidence: OosEvidence,
  opts?: { sourceBacktestRunId?: string | null; trialId?: string | null },
): import("@bolsa/shared").PaperLabEvidenceSnapshot {
  return {
    kind: evidence.kind,
    oosScore: evidence.oosScore,
    meanOosScore: evidence.meanOosScore,
    oosReturnPct: evidence.oosReturnPct,
    nFolds: evidence.nFolds,
    pathCount: evidence.pathCount,
    walkForwardEfficiency: evidence.walkForwardEfficiency,
    oosCv: evidence.oosCv,
    positiveOosFoldShare: evidence.positiveOosFoldShare,
    wfeSource: evidence.wfeSource,
    credibility: evidence.credibility,
    edgeBand: evidence.edgeBand,
    monteCarloPValue: evidence.monteCarloPValue,
    dsr: evidence.dsr,
    pbo: evidence.pbo,
    persistedEdgeReportId: evidence.persistedEdgeReportId,
    trialId: opts?.trialId ?? undefined,
    sourceBacktestRunId: opts?.sourceBacktestRunId ?? undefined,
    note: "Lab provenance at paper deploy — not a production gate, Belief, or auto-live.",
  };
}
