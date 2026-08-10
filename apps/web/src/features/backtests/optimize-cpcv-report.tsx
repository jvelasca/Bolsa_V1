import type { CpcvSummaryDto, PboSummaryDto } from '@bolsa/shared';
import { classifyPbo, formatPbo, pboBandLabel } from '@/features/backtests/backtest-pbo';
import {
  classifyWfe,
  formatPositiveFoldShare,
  formatWfe,
  wfeBandLabel,
} from '@/features/backtests/backtest-walk-forward-metrics';

interface OptimizeLabWfeHint {
  credibility: number;
  edgeScore: number;
  band: string;
  note: string;
}

interface OptimizeCpcvReportProps {
  cpcv: CpcvSummaryDto;
  /** PBO CSCV lab (top-level del resultado). */
  pbo: PboSummaryDto | null;
  labWfeHint: OptimizeLabWfeHint | null;
}

/**
 * Card de informe CPCV (Diseño B, data-only). Muestra media OOS por path, WFE,
 * CV, share de paths positivos, PBO CSCV lab y el detalle de cada path. La
 * lógica de negocio permanece en `backtest-optimize-panel.tsx`.
 */
export function OptimizeCpcvReport({ cpcv, pbo, labWfeHint }: OptimizeCpcvReportProps) {
  return (
    <div className="space-y-2 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-3 text-sm">
      <p className="font-medium text-foreground">
        CPCV ligero · {cpcv.pathCount} paths · {cpcv.nGroups} grupos (purge {cpcv.purgeBars} /
        embargo {cpcv.embargoBars})
      </p>
      <p className="text-xs text-muted-foreground">
        Media OOS del mejor de cada path:{' '}
        <strong className="text-foreground tabular-nums">
          {cpcv.meanOosScore.toFixed(2)}
        </strong>
        {cpcv.stdOosScore > 0 ? ` ± ${cpcv.stdOosScore.toFixed(2)}` : ''}
        {' · '}
        WFE{' '}
        <strong className="text-foreground tabular-nums">
          {formatWfe(cpcv.walkForwardEfficiency)}
        </strong>
        {cpcv.walkForwardEfficiency != null
          ? ` (${wfeBandLabel(classifyWfe(cpcv.walkForwardEfficiency))})`
          : ''}
        {cpcv.oosCv != null ? ` · CV ${cpcv.oosCv.toFixed(2)}` : ''}
        {cpcv.positiveOosFoldShare != null
          ? ` · ${formatPositiveFoldShare(cpcv.positiveOosFoldShare, cpcv.pathCount)}`
          : ''}
        . La tabla inferior es el último path + su OOS.
      </p>
      {pbo && (
        <p className="text-xs text-muted-foreground">
          PBO CSCV lab:{' '}
          <strong className="text-foreground tabular-nums">{formatPbo(pbo.pbo)}</strong>
          {' '}
          ({pboBandLabel(classifyPbo(pbo.pbo))}) · S={pbo.segmentCount} ·{' '}
          {pbo.splitCount} splits · N={pbo.strategyCount} · mean logit{' '}
          {pbo.meanLogit.toFixed(2)}. ≥0.5 ≈ selección IS al azar OOS.
        </p>
      )}
      {labWfeHint && (
        <p className="text-[11px] text-muted-foreground">
          Credibility hint (solo WFE lab): {labWfeHint.credibility.toFixed(1)} · banda{' '}
          {labWfeHint.band}. {labWfeHint.note}
        </p>
      )}
      <ul className="grid max-h-40 gap-1.5 overflow-y-auto text-[11px] text-muted-foreground sm:grid-cols-3">
        {cpcv.paths.map((path) => (
          <li
            key={path.index}
            className="rounded border border-border/60 bg-background/50 px-2 py-1.5"
          >
            <span className="font-medium text-foreground">#{path.index}</span>
            {' · test G'}
            {path.testGroupIndices.join('+')}
            <br />
            train {path.trainBarCount} / test {path.testBarCount}
            <br />
            IS {path.isScore.toFixed(1)}
            {path.oosMetrics != null ? ` → OOS ${path.oosMetrics.score.toFixed(1)}` : ''}
            {path.walkForwardEfficiency != null
              ? ` · WFE ${path.walkForwardEfficiency.toFixed(2)}`
              : ''}
          </li>
        ))}
      </ul>
    </div>
  );
}
