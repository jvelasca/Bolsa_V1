/**
 * Resumen comprimido de posiciones (NIVEL 4).
 */

import { Link } from "react-router-dom";
import type { DecisionJournalStudyViewV1, ProtectPlanV1 } from "@bolsa/shared";
import type { PositionDto } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MesaPositionRow } from "@/features/mesa/mesa-position-row";
import { mesaOperationsHref } from "@/features/mesa/mesa-nav-links";

export function MesaPositionsSummary({
  positions,
  protectPlanByInstrument,
  studiesByInstrument,
}: {
  positions: PositionDto[];
  protectPlanByInstrument: Map<string, ProtectPlanV1>;
  studiesByInstrument: Map<string, DecisionJournalStudyViewV1>;
}) {
  return (
    <Card data-testid="mesa-positions-summary">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <div>
          <CardTitle className="text-base">Posiciones</CardTitle>
          <CardDescription>
            HOLD / PROTECT / REDUCE / EXIT — CTAs encolan Confirm
          </CardDescription>
        </div>
        <Link
          to={mesaOperationsHref()}
          className="text-xs text-primary hover:underline"
        >
          Ver en Libro
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        {positions.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">
            Sin posiciones abiertas
          </p>
        ) : (
          positions.map((position) => (
            <MesaPositionRow
              key={position.id}
              position={position}
              protectPlan={protectPlanByInstrument.get(position.instrumentId)}
              study={studiesByInstrument.get(position.instrumentId) ?? null}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
