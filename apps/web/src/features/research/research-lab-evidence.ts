import type { ResearchTrialDto } from '@bolsa/shared';
import {
  extractOosEvidenceFromTrial,
  type OosEvidence,
  type OosEvidenceKind,
} from '@/features/backtests/backtest-oos-evidence';
import { classifyPbo, formatPbo, pboBandLabel } from '@/features/backtests/backtest-pbo';
import {
  classifyWfe,
  formatWfe,
  wfeBandLabel,
} from '@/features/backtests/backtest-walk-forward-metrics';

export type LabEvidenceSummary = {
  kind: OosEvidenceKind;
  /** Short mode for table / strip. */
  modeLabel: string;
  /** One-line cell for History. */
  compact: string;
  /** Title tooltip. */
  title: string;
  hasLab: boolean;
};

function modeLabel(kind: OosEvidenceKind): string {
  switch (kind) {
    case 'holdout':
      return 'Hold-out';
    case 'walkforward':
      return 'WF';
    case 'cpcv':
      return 'CPCV';
    default:
      return '—';
  }
}

function partsFromEvidence(evidence: OosEvidence): string[] {
  const parts: string[] = [modeLabel(evidence.kind)];
  if (evidence.kind === 'none') return [];

  if (evidence.kind === 'holdout' && evidence.oosScore != null) {
    parts.push(`OOS ${evidence.oosScore.toFixed(1)}`);
  }
  if (
    (evidence.kind === 'walkforward' || evidence.kind === 'cpcv') &&
    evidence.walkForwardEfficiency != null
  ) {
    const band = wfeBandLabel(classifyWfe(evidence.walkForwardEfficiency));
    parts.push(`WFE ${formatWfe(evidence.walkForwardEfficiency)} (${band})`);
  } else if (
    (evidence.kind === 'walkforward' || evidence.kind === 'cpcv') &&
    evidence.meanOosScore != null
  ) {
    parts.push(`OOS̄ ${evidence.meanOosScore.toFixed(1)}`);
  }
  if (evidence.pbo != null) {
    const band = pboBandLabel(classifyPbo(evidence.pbo));
    parts.push(`PBO ${formatPbo(evidence.pbo)} (${band})`);
  }
  if (evidence.edgeBand) {
    parts.push(`Edge ${evidence.edgeBand}`);
  }
  if (evidence.persistedEdgeReportId) {
    parts.push(`ER ${evidence.persistedEdgeReportId.slice(0, 10)}…`);
  }
  return parts;
}

/** Compact lab validation summary from trial.blocks (Observatory P5). */
export function summarizeLabEvidenceFromTrial(
  trial?: ResearchTrialDto | null,
): LabEvidenceSummary {
  const evidence = extractOosEvidenceFromTrial(trial);
  if (evidence.kind === 'none') {
    return {
      kind: 'none',
      modeLabel: '—',
      compact: '—',
      title: 'Sin validación lab (hold-out / WF / CPCV) en blocks',
      hasLab: false,
    };
  }
  const parts = partsFromEvidence(evidence);
  const compact = parts.join(' · ');
  return {
    kind: evidence.kind,
    modeLabel: modeLabel(evidence.kind),
    compact,
    title: `${compact}. Ledger lab — no es gate de producción.`,
    hasLab: true,
  };
}
