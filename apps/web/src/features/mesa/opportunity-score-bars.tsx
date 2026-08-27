/**
 * Calidad / Encaje / Operabilidad como barras (V1.23 Fase 4).
 * Tres barras se leen de un vistazo; tres números gemelos no.
 */

import type { OpportunityRankRowV1 } from "@bolsa/shared";
import { buildOpportunityScoreBars } from "@/features/mesa/mesa-opportunity-language";
import { cn } from "@/lib/utils";

function barTone(value: number): string {
  if (value >= 70) return "bg-emerald-500/70";
  if (value >= 40) return "bg-amber-500/70";
  return "bg-rose-500/60";
}

export function OpportunityScoreBars({
  rankRow,
  testId,
  className,
}: {
  rankRow: Pick<
    OpportunityRankRowV1,
    "quality" | "suitability" | "operability"
  >;
  testId?: string;
  className?: string;
}) {
  const bars = buildOpportunityScoreBars(rankRow);

  return (
    <ul
      className={cn("space-y-1", className)}
      data-testid={testId ?? "opportunity-score-bars"}
    >
      {bars.map((bar) => {
        const pct = Math.max(0, Math.min(100, Math.round(bar.value)));
        return (
          <li key={bar.id} className="flex items-center gap-2 text-[10px]">
            <span className="w-[74px] shrink-0 text-muted-foreground">
              {bar.label}
            </span>
            <span
              className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
              role="meter"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${bar.label} ${pct} de 100`}
              title={bar.hint}
              data-testid={`opportunity-score-bar-${bar.id}`}
              data-value={pct}
            >
              <span
                className={cn("block h-full rounded-full", barTone(pct))}
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="w-6 shrink-0 text-right tabular-nums text-muted-foreground">
              {pct}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
