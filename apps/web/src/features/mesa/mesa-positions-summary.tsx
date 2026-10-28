/**
 * Resumen comprimido de posiciones (NIVEL 4).
 */

import { Link } from "react-router-dom";
import type { DecisionJournalStudyViewV1, ProtectPlanV1 } from "@bolsa/shared";
import type { PositionDto } from "@bolsa/shared";
import { pickPositionStudies } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  MesaPositionRow,
  mesaPositionShowsRoute,
} from "@/features/mesa/mesa-position-row";
import { mesaOperationsHref } from "@/features/mesa/mesa-nav-links";
import { CollectionAbsence } from "@/components/collection-absence";
import {
  isCollectionAbsent,
  type CollectionReadState,
} from "@/components/query-absence";

export function MesaPositionsSummary({
  positions,
  protectPlanByInstrument,
  studiesByInstrument,
  studiesByDecisionId,
  portfolioReconStatus,
  portfolioState,
}: {
  positions: PositionDto[];
  protectPlanByInstrument: Map<string, ProtectPlanV1>;
  studiesByInstrument: Map<string, DecisionJournalStudyViewV1>;
  studiesByDecisionId: Map<string, DecisionJournalStudyViewV1>;
  portfolioReconStatus?: string | null;
  /**
   * P1-06 — estado de lectura de la cartera. Sin lectura, «Sin posiciones» sería
   * una afirmación sobre un dato inexistente.
   */
  portfolioState?: CollectionReadState;
}) {
  return (
    <Card data-testid="mesa-positions-summary">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Posiciones</h2>
          <CardDescription>
            Una acción principal por posición — Confirm es la firma
          </CardDescription>
        </div>
        <Link
          to={mesaOperationsHref()}
          className="text-xs text-primary hover:underline"
        >
          Ver en Cartera
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        {portfolioState && isCollectionAbsent(portfolioState) ? (
          <CollectionAbsence
            state={portfolioState}
            subject="la cartera"
            testId="mesa-positions-absence"
            className="py-6 text-center"
          />
        ) : positions.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">
            Sin posiciones
          </p>
        ) : (
          positions.map((position) => {
            const { originStudy, evolutionStudy } = pickPositionStudies(
              position,
              studiesByDecisionId,
              studiesByInstrument,
            );
            return (
              <MesaPositionRow
                key={position.id}
                position={position}
                protectPlan={protectPlanByInstrument.get(position.instrumentId)}
                study={evolutionStudy}
                originStudy={originStudy}
                showRoute={mesaPositionShowsRoute(position, evolutionStudy)}
                portfolioReconStatus={portfolioReconStatus}
              />
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
