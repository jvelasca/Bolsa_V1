/**
 * Q3.2 — informe estabilidad compacto en Finalistas / Coach.
 * Reutiliza formatPaperLabEvidence + flags WF del checklist (sin campaña Δ).
 */

import type { PaperLabEvidenceSnapshot } from "@bolsa/shared";
import { formatPaperLabEvidence } from "@/features/accounts/paper-lab-evidence";
import {
  oosEvidenceToPaperLabSnapshot,
  resolveOosEvidence,
  type OosEvidence,
} from "@/features/backtests/backtest-oos-evidence";
import { walkForwardStabilityFlags } from "@/features/backtests/backtest-walk-forward-metrics";

export function readLabEvidenceFromCoachFacts(
  facts: Record<string, unknown> | null | undefined,
): PaperLabEvidenceSnapshot | null {
  if (!facts || typeof facts !== "object") return null;
  const raw = facts.labEvidence;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const kind = (raw as PaperLabEvidenceSnapshot).kind;
  if (
    kind !== "holdout" &&
    kind !== "walkforward" &&
    kind !== "cpcv" &&
    kind !== "none"
  ) {
    return null;
  }
  return raw as PaperLabEvidenceSnapshot;
}

/** Snapshot para stamp en coachFacts (misma forma que paper deploy). */
export function buildFinalistsLabEvidenceSnapshot(
  evidence: OosEvidence | null | undefined,
  opts?: { sourceBacktestRunId?: string | null; trialId?: string | null },
): PaperLabEvidenceSnapshot | null {
  if (!evidence || evidence.kind === "none") return null;
  const snap = oosEvidenceToPaperLabSnapshot(evidence, opts);
  return {
    ...snap,
    note: "Lab provenance on Finalistas — not a production gate, Belief, or auto-live.",
  };
}

export function mergeLabEvidenceIntoCoachFacts(
  facts: Record<string, unknown>,
  snapshot: PaperLabEvidenceSnapshot | null,
): Record<string, unknown> {
  if (!snapshot) return facts;
  return { ...facts, labEvidence: snapshot };
}

/** Línea corta: Hold-out / WF / CPCV · WFE… (vocabulario Lab/checklist). */
export function formatFinalistsStabilityBadge(
  snapshot: PaperLabEvidenceSnapshot | null | undefined,
): string | null {
  if (!snapshot || snapshot.kind === "none") return null;
  const text = formatPaperLabEvidence(snapshot);
  if (!text || text === "—" || text === "Sin validación lab") return null;
  return text;
}

export function finalistsStabilityWarnTitle(
  snapshot: PaperLabEvidenceSnapshot | null | undefined,
): string | null {
  if (!snapshot) return null;
  const flags = walkForwardStabilityFlags({
    walkForwardEfficiency: snapshot.walkForwardEfficiency,
    oosCv: snapshot.oosCv,
    positiveOosFoldShare: snapshot.positiveOosFoldShare,
  });
  const parts: string[] = [];
  if (flags.weakWfe) parts.push("WFE débil");
  if (flags.unstableCv) parts.push("CV OOS alto");
  if (flags.fewPositiveFolds) parts.push("pocos folds +");
  return parts.length ? `Estabilidad frágil: ${parts.join(" · ")}` : null;
}

/**
 * Resuelve OOS del slot#1 (stash Lab) → snapshot para stamp al guardar Finalistas.
 */
export function resolveLabEvidenceForFinalistsSave(opts: {
  strategyDefinitionId?: string | null;
  runId?: string | null;
}): PaperLabEvidenceSnapshot | null {
  const evidence = resolveOosEvidence({
    strategyId: opts.strategyDefinitionId,
  });
  return buildFinalistsLabEvidenceSnapshot(evidence, {
    sourceBacktestRunId: opts.runId ?? null,
  });
}
