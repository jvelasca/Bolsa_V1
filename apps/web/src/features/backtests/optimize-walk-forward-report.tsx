import type { WalkForwardSummaryDto } from "@bolsa/shared";
import {
  classifyWfe,
  formatPositiveFoldShare,
  formatWfe,
  wfeBandLabel,
} from "@/features/backtests/backtest-walk-forward-metrics";

export interface OptimizeLabWfeHint {
  credibility: number;
  edgeScore: number;
  band: string;
  note: string;
}

interface OptimizeWalkForwardReportProps {
  walkForward: WalkForwardSummaryDto;
  /** Hint de credibilidad solo-WFE; nullptr si hay EdgeReport completo. */
  labWfeHint: OptimizeLabWfeHint | null;
}

/**
 * Card de informe Walk-Forward (Diseño B, data-only). Muestra media OOS del
 * mejor de cada pliegue, WFE, CV, share de pliegues positivos y el detalle de
 * cada pliegue. La lógica de negocio permanece en `backtest-optimize-panel.tsx`.
 */
export function OptimizeWalkForwardReport({
  walkForward,
  labWfeHint,
}: OptimizeWalkForwardReportProps) {
  return (
    <div className="space-y-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-3 text-sm">
      <p className="font-medium text-foreground">
        Walk-forward · {walkForward.nFolds} pliegues ({walkForward.mode})
      </p>
      <p className="text-xs text-muted-foreground">
        Media OOS del mejor de cada pliegue:{" "}
        <strong className="text-foreground tabular-nums">
          {walkForward.meanOosScore.toFixed(2)}
        </strong>
        {walkForward.stdOosScore > 0
          ? ` ± ${walkForward.stdOosScore.toFixed(2)}`
          : ""}
        {" · "}
        WFE{" "}
        <strong className="text-foreground tabular-nums">
          {formatWfe(walkForward.walkForwardEfficiency)}
        </strong>
        {walkForward.walkForwardEfficiency != null
          ? ` (${wfeBandLabel(classifyWfe(walkForward.walkForwardEfficiency))})`
          : ""}
        {walkForward.oosCv != null
          ? ` · CV ${walkForward.oosCv.toFixed(2)}`
          : ""}
        {walkForward.positiveOosFoldShare != null
          ? ` · ${formatPositiveFoldShare(walkForward.positiveOosFoldShare, walkForward.nFolds)}`
          : ""}
        . WFE = media OOS / media IS (score lab). La tabla inferior es el último
        pliegue + su OOS.
      </p>
      {labWfeHint && (
        <p className="text-[11px] text-muted-foreground">
          Credibility hint (solo WFE lab): {labWfeHint.credibility.toFixed(1)} ·
          banda {labWfeHint.band}. {labWfeHint.note}
        </p>
      )}
      <ul className="grid gap-1.5 text-[11px] text-muted-foreground sm:grid-cols-3">
        {walkForward.folds.map((fold) => (
          <li
            key={fold.index}
            className="rounded border border-border/60 bg-background/50 px-2 py-1.5"
            title={
              fold.testStartTimestamp
                ? `Test desde ${fold.testStartTimestamp}`
                : undefined
            }
          >
            <span className="font-medium text-foreground">#{fold.index}</span>
            {" · "}
            train {fold.trainBarCount} / test {fold.testBarCount}
            <br />
            IS {fold.isScore.toFixed(1)}
            {fold.oosMetrics != null
              ? ` → OOS ${fold.oosMetrics.score.toFixed(1)}`
              : ""}
            {fold.walkForwardEfficiency != null
              ? ` · WFE ${fold.walkForwardEfficiency.toFixed(2)}`
              : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
