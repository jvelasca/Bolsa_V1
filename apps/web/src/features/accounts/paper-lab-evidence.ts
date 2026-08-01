import type { PaperLabEvidenceSnapshot } from '@bolsa/shared';
import { classifyPbo, formatPbo, pboBandLabel } from '@/features/backtests/backtest-pbo';
import {
  classifyWfe,
  formatWfe,
  wfeBandLabel,
} from '@/features/backtests/backtest-walk-forward-metrics';

/** Compact line for paper account detail (P7). */
export function formatPaperLabEvidence(
  snapshot?: PaperLabEvidenceSnapshot | null,
): string {
  if (!snapshot) return '—';
  const kind = snapshot.kind ?? 'none';
  if (kind === 'none' && !snapshot.edgeBand && snapshot.pbo == null) {
    return 'Sin validación lab';
  }
  const parts: string[] = [];
  if (kind === 'holdout') {
    parts.push('Hold-out');
    if (snapshot.oosScore != null && Number.isFinite(snapshot.oosScore)) {
      parts.push(`OOS ${snapshot.oosScore.toFixed(1)}`);
    }
  } else if (kind === 'walkforward') {
    parts.push('WF');
  } else if (kind === 'cpcv') {
    parts.push('CPCV');
  } else {
    parts.push('Lab');
  }
  if (
    snapshot.walkForwardEfficiency != null &&
    Number.isFinite(snapshot.walkForwardEfficiency)
  ) {
    const band = wfeBandLabel(classifyWfe(snapshot.walkForwardEfficiency));
    parts.push(`WFE ${formatWfe(snapshot.walkForwardEfficiency)} (${band})`);
  }
  if (snapshot.pbo != null && Number.isFinite(snapshot.pbo)) {
    parts.push(`PBO ${formatPbo(snapshot.pbo)} (${pboBandLabel(classifyPbo(snapshot.pbo))})`);
  }
  if (snapshot.edgeBand) {
    parts.push(`Edge ${snapshot.edgeBand}`);
  }
  if (snapshot.persistedEdgeReportId) {
    parts.push(`ER ${snapshot.persistedEdgeReportId.slice(0, 10)}…`);
  }
  return parts.join(' · ') || '—';
}
