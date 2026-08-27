/**
 * Vigilar — categoría WATCH del ranking (V1.23 Fase 4).
 * Sin CTAs de compra: aquí sólo se observa.
 */

import { Link } from "react-router-dom";
import type { OpportunityRankRowV1 } from "@bolsa/shared";
import { formatPriorityScore } from "@/features/mesa/mesa-opportunity-language";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";

const WATCH_LIMIT = 6;

export function MesaWatchList({
  rows,
}: {
  rows: ReadonlyArray<OpportunityRankRowV1>;
}) {
  if (rows.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Nada en vigilancia con análisis reciente.
      </p>
    );
  }

  return (
    <ul
      className="divide-y divide-border/50 rounded-md border border-border/60"
      data-testid="mesa-inbox-vigilar-list"
    >
      {rows.slice(0, WATCH_LIMIT).map((rankRow) => (
        <li
          key={`watch-${rankRow.symbol}`}
          className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2"
          data-testid={`mesa-inbox-watch-${rankRow.symbol}`}
        >
          <div>
            <p className="text-sm font-medium">{rankRow.symbol}</p>
            <p className="text-[11px] text-muted-foreground">
              {rankRow.categoryReason ?? "En vigilancia — sin acción hoy"}
            </p>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {formatPriorityScore(rankRow.quality)}
            </span>
            {rankRow.candidate.instrumentId ? (
              <Link
                to={mesaJournalTesisHref(rankRow.candidate.instrumentId, {
                  ficha: true,
                })}
                className="text-[11px] text-primary hover:underline"
              >
                Ver tesis
              </Link>
            ) : null}
          </div>
        </li>
      ))}
      {rows.length > WATCH_LIMIT ? (
        <li className="px-3 py-1.5 text-[11px] text-muted-foreground">
          +{rows.length - WATCH_LIMIT} más en vigilancia
        </li>
      ) : null}
    </ul>
  );
}
