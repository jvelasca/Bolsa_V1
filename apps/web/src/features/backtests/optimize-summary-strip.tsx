import type { PboSummaryDto } from '@bolsa/shared';
import { classifyPbo, formatPbo, pboBandLabel } from '@/features/backtests/backtest-pbo';
import { formatWfe } from '@/features/backtests/backtest-walk-forward-metrics';

interface OptimizeSummaryStripProps {
  mode: string;
  wfe: number | null;
  pbo: PboSummaryDto | null;
  edgeBand: string | null;
}

/**
 * Franja resumen del experimento (Diseño B, data-only): modo (CPCV /
 * walk-forward / hold-out) + WFE + PBO + banda Edge. La decisión de render (qué
 * modo) y los datos se derivan en el orquestador `backtest-optimize-panel.tsx`.
 */
export function OptimizeSummaryStrip({ mode, wfe, pbo, edgeBand }: OptimizeSummaryStripProps) {
  return (
    <p
      className="rounded-md border border-border/70 bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground"
      title="Resumen del experimento. No es gate de producción."
    >
      Modo{' '}
      <span className="font-medium text-foreground">{mode}</span>
      {wfe != null ? ` · WFE ${formatWfe(wfe)}` : ''}
      {pbo != null ? ` · PBO ${formatPbo(pbo.pbo)} (${pboBandLabel(classifyPbo(pbo.pbo))})` : ''}
      {edgeBand ? ` · Edge ${edgeBand}` : ''}
      {' · '}
      lab, no producción
    </p>
  );
}
