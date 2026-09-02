/**
 * Badge G2 — fase operativa en fila de lista (DISPARADA / Propuesta / T1).
 */

import { useListOperativaRow } from "@/features/trading/lists-tab/list-operativa-phase-context";
import type { ListOperativaBadgeKind } from "@/features/trading/operativa-phase-toast";
import { cn } from "@/lib/utils";

function badgeTone(kind: ListOperativaBadgeKind): string {
  switch (kind) {
    case "disparada":
      return "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-50";
    case "propuesta":
      return "border-amber-700/40 bg-amber-500/10 text-amber-950 dark:text-amber-50";
    case "t1":
      return "border-sky-600/40 bg-sky-500/10 text-sky-950 dark:text-sky-50";
  }
}

export function ListOperativaPhaseBadge({
  instrumentId,
}: {
  instrumentId: string;
}) {
  const row = useListOperativaRow(instrumentId);
  if (!row) return null;

  return (
    <>
      {row.badge ? (
        <span
          className={cn(
            "inline-flex max-w-full truncate rounded border px-1 py-px text-[9px] font-semibold tracking-wide",
            badgeTone(row.badge.kind),
          )}
          data-testid="list-operativa-phase-badge"
          data-phase={row.phase}
          data-badge={row.badge.kind}
          title={
            row.badge.kind === "t1"
              ? "T1 alcanzado · pendiente de gestión (tocado ≠ reducido)"
              : row.badge.label
          }
        >
          {row.badge.label}
        </span>
      ) : null}
      <span
        data-testid="list-operativa-phase"
        data-phase={row.phase}
        className="sr-only"
        aria-hidden
      />
    </>
  );
}
