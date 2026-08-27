/**
 * V1.17 — ruta visual viva: precio actual entre niveles con distancia/R.
 */

import type { DecisionJournalStudyViewV1, PositionDto } from "@bolsa/shared";
import {
  NO_OPERATIONAL_PLAN_COPY,
  buildInvestmentPositionAggregate,
  buildPositionRouteLevels,
} from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

type PositionRoutePanelProps = {
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  className?: string;
};

export function PositionRoutePanel({
  position,
  study,
  originStudy,
  className,
}: PositionRoutePanelProps) {
  const aggregate = buildInvestmentPositionAggregate({
    position,
    study,
    originStudy,
  });
  const op = position.operational;
  const hasPlan = study?.hasOperationalPlan === true;
  const stop = op?.currentStop ?? (hasPlan ? study?.stop : null);
  const t1 = op?.target1 ?? (hasPlan ? study?.target1 : null);

  if (!hasPlan && stop == null && t1 == null) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        {NO_OPERATIONAL_PLAN_COPY}
      </p>
    );
  }

  const levels = buildPositionRouteLevels(aggregate);

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
                level.kind === "price" && "border-amber-500 bg-amber-500/30",
                level.kind === "target" &&
                  "border-emerald-500 bg-emerald-500/30",
              )}
            />
            <span className="font-medium">{level.label}</span>
            {" · "}
            <span className="tabular-nums">{formatPrice(level.value)}</span>
            {level.distanceR != null ? (
              <span className="ml-1 text-muted-foreground tabular-nums">
                {level.distanceR >= 0 ? "+" : ""}
                {level.distanceR.toFixed(1)}R
              </span>
            ) : null}
            {level.reached ? (
              <span className="ml-1 text-emerald-600">✓</span>
            ) : null}
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted-foreground">
        PLAN — lo que debería ocurrir. Confirm es la firma humana.
      </p>
      {aggregate.originalPlanAvailable &&
      aggregate.originalPlan?.stop != null &&
      aggregate.currentPlan.stop != null &&
      aggregate.originalPlan.stop !== aggregate.currentPlan.stop ? (
        <p
          className="text-[10px] text-muted-foreground"
          data-testid={`position-stop-revision-${position.symbol}`}
        >
          Stop {formatPrice(aggregate.originalPlan.stop)} →{" "}
          {formatPrice(aggregate.currentPlan.stop)}
        </p>
      ) : null}
    </div>
  );
}
