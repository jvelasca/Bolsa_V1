/**
 * Teaser TOP del ranking en el inbox de Hoy (V1.23 Fase 4).
 * Prioridad, no Opportunity. Prioridad ≠ orden: la firma vive en Confirmar.
 */

import { Link } from "react-router-dom";
import type { OpportunityRankRowV1 } from "@bolsa/shared";
import {
  PRIORITY_NOT_AN_ORDER,
  formatPriorityScore,
  opportunityResultLabel,
  opportunityResultTone,
} from "@/features/mesa/mesa-opportunity-language";
import { OpportunityScoreBars } from "@/features/mesa/opportunity-score-bars";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { cn } from "@/lib/utils";

const TEASER_LIMIT = 3;

export function MesaOpportunitiesTeaser({
  rows,
  entriesBlocked,
  operableCount,
  verTodasHref,
}: {
  rows: ReadonlyArray<OpportunityRankRowV1>;
  entriesBlocked: boolean;
  operableCount: number;
  verTodasHref: string;
}) {
  const visible = rows.slice(0, TEASER_LIMIT);

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/10 px-4 py-3"
      data-testid="mesa-inbox-oportunidades-teaser"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">
          {rows.length} con prioridad alta
          {operableCount > 0 ? ` · ${operableCount} operables` : ""}
        </p>
        <span
          className="rounded border border-border/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
          data-testid="mesa-inbox-oportunidades-disclaimer"
        >
          {PRIORITY_NOT_AN_ORDER}
        </span>
      </div>

      {visible.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Nada con prioridad alta hoy. No operar también es decidir.
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {visible.map((rankRow) => {
            const result = opportunityResultLabel(rankRow, entriesBlocked);
            return (
              <li
                key={`${rankRow.symbol}-${rankRow.category}`}
                className="rounded border border-border/50 bg-background/40 px-3 py-2"
                data-testid={`mesa-inbox-opp-${rankRow.symbol}`}
                data-result={result}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-medium">
                    {rankRow.rank != null ? `#${rankRow.rank} ` : ""}
                    {rankRow.symbol}
                    <span
                      className={cn(
                        "ml-2 text-[10px] font-semibold uppercase tracking-wide",
                        opportunityResultTone(result),
                      )}
                    >
                      {result}
                    </span>
                  </p>
                  <p className="text-xs font-semibold tabular-nums">
                    {formatPriorityScore(rankRow.quality)}
                  </p>
                </div>
                <OpportunityScoreBars
                  rankRow={rankRow}
                  className="mt-1.5"
                  testId={`mesa-inbox-opp-bars-${rankRow.symbol}`}
                />
                {rankRow.candidate.instrumentId ? (
                  <Link
                    to={mesaJournalTesisHref(rankRow.candidate.instrumentId, {
                      ficha: true,
                    })}
                    className="mt-1 inline-block text-[11px] text-primary hover:underline"
                  >
                    Ver tesis →
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <Link
        to={verTodasHref}
        className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
        data-testid="mesa-inbox-oportunidades-ver-todas"
      >
        Ver todas →
      </Link>
    </div>
  );
}
