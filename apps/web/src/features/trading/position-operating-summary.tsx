/**
 * V1.36 — Resumen operativo diario en cockpit Mercado (fase POSICIÓN).
 * Próximo evento ≠ protección; frase humana ≠ permiso.
 */

import type { PositionDto } from "@bolsa/shared";
import {
  buildPositionDecisionFromDto,
  formatNextEventLabel,
  formatPositionDecisionPhrase,
  formatProtectionLabel,
  mapReconStatusToHealth,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

export function PositionOperatingSummary({
  position,
  portfolioReconStatus,
  className,
}: {
  position: PositionDto;
  portfolioReconStatus?: string | null;
  className?: string;
}) {
  const decision = buildPositionDecisionFromDto(position, {
    portfolioReconStatus,
  });
  if (!decision) return null;

  const reconHealth = mapReconStatusToHealth(portfolioReconStatus);

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-2",
        className,
      )}
      data-testid="position-operating-summary"
      data-action={decision.action}
      data-next-event={decision.nextEvent}
      data-protection={decision.protection}
    >
      <p
        className="text-[11px] leading-snug text-foreground"
        data-testid="position-operating-phrase"
      >
        {formatPositionDecisionPhrase(decision)}
      </p>
      <dl className="grid gap-1 text-[10px]">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Próximo evento</dt>
          <dd
            className="font-medium tabular-nums"
            data-testid="position-operating-next-event"
          >
            {formatNextEventLabel(decision.nextEvent)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Protección</dt>
          <dd
            className={cn(
              "font-medium",
              decision.protection === "ACTIVE"
                ? "text-emerald-800 dark:text-emerald-200"
                : "text-amber-800 dark:text-amber-200",
            )}
            data-testid="position-operating-protection"
          >
            {formatProtectionLabel(decision.protection)}
          </dd>
        </div>
        {reconHealth !== "CLEAN" ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Reconciliación</dt>
            <dd className="font-medium text-rose-800 dark:text-rose-200">
              {reconHealth === "CRITICAL" ? "Bloqueada" : "Atención"}
            </dd>
          </div>
        ) : null}
      </dl>
      <p className="text-[9px] text-muted-foreground">
        Stop operativo registrado ≠ orden stop de broker. Confirm = firma.
      </p>
    </div>
  );
}
