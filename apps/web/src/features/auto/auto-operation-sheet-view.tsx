/**
 * AUTO UI REFACTOR 4.0 (P2) — presentación de la ficha universal de operación.
 *
 * Pinta el view-model de `auto-operation-sheet.ts` en el orden canónico, siempre los seis
 * bloques. No calcula: sólo presenta.
 */

import type { AutoOperationSheetV1 } from "@/features/auto/auto-operation-sheet";
import {
  AUTO_USER_TEXT,
  AUTO_USER_TITLE,
} from "@/features/auto/auto-typography";
import { cn } from "@/lib/utils";

export function AutoOperationSheetView({
  sheet,
}: {
  sheet: AutoOperationSheetV1;
}) {
  return (
    <article
      className="space-y-3 rounded-lg border border-border bg-card px-4 py-3"
      data-testid="auto-operation-sheet"
      data-cycle-id={sheet.cycleId}
      aria-label={`Ficha de la operación ${sheet.symbol}`}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <p className={cn("font-semibold", AUTO_USER_TITLE)}>{sheet.symbol}</p>
        <p
          className={cn(
            "text-xs uppercase tracking-wide text-muted-foreground",
          )}
        >
          {sheet.modeLabel}
        </p>
      </header>
      <dl className="space-y-1.5">
        {sheet.blocks.map((block) => (
          <div
            key={block.id}
            className={cn("flex flex-wrap gap-x-3 gap-y-0.5", AUTO_USER_TEXT)}
            data-testid={`auto-sheet-block-${block.id}`}
          >
            <dt className="w-36 shrink-0 text-muted-foreground">
              {block.label}
            </dt>
            <dd className="font-medium">{block.value}</dd>
            {block.detail ? (
              <dd className="text-muted-foreground">{block.detail}</dd>
            ) : null}
          </div>
        ))}
      </dl>
    </article>
  );
}
