/**
 * Presentación de la tarjeta. El view-model vive en `auto-operation-card.ts`.
 */

import { Link } from "react-router-dom";
import { autoTechnicalDetailHref } from "@/features/auto/auto-nav";
import type { AutoOperationCardV1 } from "@/features/auto/auto-operation-card";
import {
  AUTO_USER_TEXT,
  AUTO_USER_TITLE,
} from "@/features/auto/auto-typography";
import { cn } from "@/lib/utils";

export function AutoOperationCardView({ card }: { card: AutoOperationCardV1 }) {
  return (
    <article
      className="space-y-3 rounded-lg border border-border bg-card px-4 py-3"
      data-testid="auto-operation-card"
      data-cycle-id={card.cycleId}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <p className={cn("font-semibold", AUTO_USER_TITLE)}>{card.symbol}</p>
        <p className={cn("font-medium", AUTO_USER_TEXT)}>{card.headline}</p>
      </header>
      <ul className="space-y-1">
        {card.slots.map((slot) => (
          <li
            key={slot.id}
            className={cn("flex flex-wrap gap-x-3 gap-y-0.5", AUTO_USER_TEXT)}
            data-testid={`auto-card-slot-${slot.id}`}
          >
            <span className="w-28 text-muted-foreground">{slot.label}</span>
            <span className="font-medium">{slot.state}</span>
            {slot.detail ? (
              <span className="text-muted-foreground">{slot.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
      <Link
        to={autoTechnicalDetailHref(card.cycleId)}
        className={cn(
          "inline-block underline hover:text-primary",
          AUTO_USER_TEXT,
        )}
        data-testid="auto-operation-card-details"
      >
        Ver detalles
      </Link>
    </article>
  );
}
