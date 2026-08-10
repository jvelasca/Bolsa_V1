import type { LabEdgeReportLiteDto } from '@bolsa/shared';

interface OptimizeEdgeReportProps {
  edgeReport: LabEdgeReportLiteDto;
}

/**
 * Card de informe Edge (Diseño B, data-only). Muestra banda, credibility, MC p,
 * DSR, PSR, WFE de suite, trades del campeón y bloqueos auto-live. La lógica de
 * negocio permanece en `backtest-optimize-panel.tsx`.
 */
export function OptimizeEdgeReport({ edgeReport }: OptimizeEdgeReportProps) {
  return (
    <div className="space-y-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-3 text-sm">
      <p className="font-medium text-foreground">
        EdgeReport lab · banda {edgeReport.band} · credibility{' '}
        <span className="tabular-nums">{edgeReport.credibility.toFixed(1)}</span>
      </p>
      <p className="text-xs text-muted-foreground">
        MC p=
        <span className="tabular-nums">
          {edgeReport.suite.monteCarloPValue != null
            ? edgeReport.suite.monteCarloPValue.toFixed(3)
            : 'n/d'}
        </span>
        {edgeReport.suite.dsr != null
          ? ` · DSR ${edgeReport.suite.dsr.toFixed(2)}`
          : ''}
        {edgeReport.suite.psr != null
          ? ` · PSR ${edgeReport.suite.psr.toFixed(2)}`
          : ''}
        {edgeReport.suite.walkForwardEfficiency != null
          ? ` · WFE ${edgeReport.suite.walkForwardEfficiency.toFixed(2)} (${edgeReport.suite.wfeSource ?? 'lab'})`
          : ''}
        {edgeReport.sampleTradesCount != null
          ? ` · ${edgeReport.sampleTradesCount} ops campeón`
          : ''}
        . Suite lite sobre trades del Mejor (OOS si hay); no es auto-live.
        {edgeReport.persistedEdgeReportId
          ? ` Persistido en edge_reports (${edgeReport.persistedEdgeReportId.slice(0, 12)}…).`
          : ''}
      </p>
      {edgeReport.blockReasons && edgeReport.blockReasons.length > 0 && (
        <p className="text-[11px] text-amber-700 dark:text-amber-400">
          Bloqueos auto-live: {edgeReport.blockReasons.join(', ')}
        </p>
      )}
    </div>
  );
}
