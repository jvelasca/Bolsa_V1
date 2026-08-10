import type { ExploreCoachNote } from "@/features/backtests/backtest-explore-value";

interface Props {
  /** Nota heurística local (ranking vs buy & hold del lote). */
  coach: ExploreCoachNote;
}

/** Comparativa heurística vs buy & hold del lote del panel Coach.
 * Extraído de `backtest-explore-panel.tsx` (feature-slicing M5, frente
 * `backtest-explore-panel`). Diseño B: evidencia secundaria que **no decide**
 * el TOP ★; solo recibe la nota local (`coach`) como prop y renderiza el
 * `<details>` colapsable. */
export function BacktestExploreBH({ coach }: Props) {
  return (
    <details className="rounded-lg border border-dashed border-border/70 px-3 py-1.5">
      <summary
        className="cursor-pointer list-none text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden"
        title="Heurística vs buy & hold del lote. No manda sobre las estrellas del TOP-3."
      >
        Comparativa vs buy & hold
        <span className="ml-1 opacity-70">· no decide el TOP ★</span>
      </summary>
      <div className="mt-1.5 space-y-1 border-t border-border/40 pt-1.5">
        <p className="text-xs text-foreground">{coach.headline}</p>
        <ul className="list-inside list-disc space-y-0.5 text-[11px] text-muted-foreground">
          {coach.bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}
