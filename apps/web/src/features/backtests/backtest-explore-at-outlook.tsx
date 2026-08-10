/**
 * Análisis AT y outlook del panel Coach (evidencia técnica, colapsable).
 *
 * Muestra: banner de régimen (cambio de tramo / mejor mitad) y un `<details>`
 * con el análisis técnico + outlook + disclaimer. Solo presenta datos del
 * `DeepTechnicalCoachNote`; sin lógica de ciclo ni peticiones (Diseño B).
 */

import type { RegimeHalfInsight } from "@/features/backtests/backtest-deep-coach";

interface Props {
  regime?: RegimeHalfInsight;
  analysis: string[];
  outlook: string[];
  disclaimer: string;
}

export function BacktestExploreAtOutlook({
  regime,
  analysis,
  outlook,
  disclaimer,
}: Props) {
  return (
    <>
      {regime && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5">
          <p className="text-[11px] font-medium text-foreground">
            {regime.label}
          </p>
          <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
            {regime.narrative}
          </p>
        </div>
      )}

      <details className="rounded-md border border-border/50 bg-background/40">
        <summary className="cursor-pointer list-none px-2 py-1.5 text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden">
          Análisis AT y outlook
        </summary>
        <div className="space-y-2 border-t border-border/40 px-2 py-2">
          <ul className="list-inside list-disc space-y-0.5 text-[11px] leading-snug text-muted-foreground">
            {analysis.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <ul className="list-inside list-disc space-y-0.5 text-[11px] text-muted-foreground">
            {outlook.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="text-[10px] leading-snug text-muted-foreground">
            {disclaimer}
          </p>
        </div>
      </details>
    </>
  );
}
