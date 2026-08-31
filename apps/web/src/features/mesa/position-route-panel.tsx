/**
 * PositionRoutePanel — envuelve OperationalPlanView (continuidad V1.21)
 * + ruta de niveles para detalle.
 * V1.40 — ExitRouteView canónica (Entrada → Stop / T1 / T2).
 */

import type { DecisionJournalStudyViewV1, PositionDto } from "@bolsa/shared";
import { buildOperationalTruth } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import { PositionOperatingSummary } from "@/features/trading/position-operating-summary";
import { ExitRouteView } from "@/features/trading/exit-route-view";

type PositionRoutePanelProps = {
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  portfolioReconStatus?: string | null;
  className?: string;
};

export function PositionRoutePanel({
  position,
  study,
  originStudy,
  portfolioReconStatus,
  className,
}: PositionRoutePanelProps) {
  const truth = buildOperationalTruth({
    position,
    study,
    originStudy,
    portfolioReconStatus,
  });
  const plan = truth?.plan;

  return (
    <div
      className={cn("space-y-2", className)}
      data-testid={`position-route-${position.symbol}`}
    >
      <PositionOperatingSummary
        truth={truth}
        position={position}
        portfolioReconStatus={portfolioReconStatus}
      />
      {plan?.hasPlan ? (
        <OperationalPlanView
          plan={plan}
          omitLiveMetrics
          testId={`operational-plan-${position.symbol}`}
        />
      ) : null}
      <ExitRouteView
        truth={truth}
        position={position}
        study={study}
        originStudy={originStudy}
      />
    </div>
  );
}
