/**
 * V1.17 — ruta visual de posición: entrada → stop → T1/T2.
 */

import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import type { PositionDto } from "@bolsa/shared";
import { NO_OPERATIONAL_PLAN_COPY } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

type PositionRoutePanelProps = {
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  className?: string;
};

export function PositionRoutePanel({
  position,
  study,
  className,
}: PositionRoutePanelProps) {
  const op = position.operational;
  const hasPlan = study?.hasOperationalPlan === true;
  const entry = (study?.entry ?? op?.direction) ? position.avgCost : null;
  const stop = op?.currentStop ?? (hasPlan ? study?.stop : null);
  const t1 = op?.target1 ?? (hasPlan ? study?.target1 : null);
  const t2 = op?.target2 ?? (hasPlan ? study?.target2 : null);

  if (!hasPlan && stop == null && t1 == null) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        {NO_OPERATIONAL_PLAN_COPY}
      </p>
    );
  }

  const levels = [
    { label: "TP2", value: t2, kind: "target" as const },
    { label: "TP1", value: t1, kind: "target" as const },
    { label: "ENTRADA", value: entry, kind: "entry" as const },
    { label: "STOP", value: stop, kind: "stop" as const },
  ].filter((l) => l.value != null);

  return (
    <div
      className={cn("space-y-1", className)}
      data-testid={`position-route-${position.symbol}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Ruta de la operación
      </p>
      <div className="relative ml-2 border-l border-border/60 pl-3">
        {levels.map((level) => (
          <div key={level.label} className="relative py-1 text-xs">
            <span
              className={cn(
                "absolute -left-[13px] top-2 h-2 w-2 rounded-full border",
                level.kind === "stop" && "border-rose-500 bg-rose-500/30",
                level.kind === "entry" && "border-sky-500 bg-sky-500/30",
                level.kind === "target" &&
                  "border-emerald-500 bg-emerald-500/30",
              )}
            />
            <span className="font-medium">{level.label}</span>
            {" · "}
            <span className="tabular-nums">{formatPrice(level.value!)}</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted-foreground">
        PLAN — lo que debería ocurrir. Confirm es la firma humana.
      </p>
    </div>
  );
}
