/**
 * PositionRoutePanel — envuelve OperationalPlanView (continuidad V1.21)
 * + ruta de niveles para detalle.
 */

import type { DecisionJournalStudyViewV1, PositionDto } from "@bolsa/shared";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildPositionRouteLevels,
} from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";

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
  const plan = buildOperationalPlanFromPosition({
    aggregate,
    markPrice: position.lastPrice ?? null,
  });
  const levels = plan.hasPlan ? buildPositionRouteLevels(aggregate) : [];

  return (
    <div
      className={cn("space-y-2", className)}
      data-testid={`position-route-${position.symbol}`}
    >
      <OperationalPlanView
        plan={plan}
        testId={`operational-plan-${position.symbol}`}
      />
      {levels.length > 0 ? (
        <div className="relative ml-2 border-l border-border/60 pl-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Ruta
          </p>
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
      ) : null}
    </div>
  );
}
