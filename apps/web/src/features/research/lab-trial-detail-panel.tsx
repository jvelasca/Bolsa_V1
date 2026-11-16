/**
 * Asesor → Laboratorio · detalle del experimento — slice A3.
 *
 * Tarjeta derecha del Laboratorio: el experimento seleccionado con su bloque de
 * resultado (`research-trial-result-block.tsx`) y el `TechnicalDetail` de
 * guardado (parámetros y referencia del manifiesto).
 *
 * El `testId` del disclosure de parámetros era el duplicado de
 * `research-trial-technical` (H-14): ahora la ÚNICA emisión de ese id vive en
 * `research-trial-result-block.tsx`, su dueño natural.
 */

import { Link } from "react-router-dom";
import type { ResearchTrialDto } from "@bolsa/shared";
import { ResearchTrialResultBlock } from "@/features/research/research-trial-result-block";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { TechnicalDetail } from "@/components/technical-detail";
import { cn } from "@/lib/utils";
import { SectionTitle } from "@/features/research/asesor-ui";

type Props = {
  selectedTrialId: string | null;
  isLoading: boolean;
  selected: ResearchTrialDto | undefined;
  className?: string;
};

export function LabTrialDetailPanel({
  selectedTrialId,
  isLoading,
  selected,
  className,
}: Props) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-2">
        <SectionTitle>Detalle</SectionTitle>
        <CardDescription>Registro del experimento</CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedTrialId && (
          <p className="text-sm text-muted-foreground">
            Selecciona un experimento en la tabla.
          </p>
        )}
        {selectedTrialId && isLoading && (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        )}
        {selected && (
          <div className="space-y-3">
            <ResearchTrialResultBlock trial={selected} />
            {selected.backtestRunId && (
              <Link
                to={`/backtests?tab=run&runId=${encodeURIComponent(selected.backtestRunId)}`}
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                )}
              >
                Abrir análisis de la prueba
              </Link>
            )}
            {!selected.backtestRunId && selected.optimizationRunId && (
              <p className="text-xs text-muted-foreground">
                Origen optimizador — sin prueba vinculada.
              </p>
            )}
            <TechnicalDetail
              className="space-y-2"
              testId="research-trial-params-technical"
            >
              <div className="rounded-md border border-border bg-muted/30 p-2">
                <p className="text-[10px] font-medium uppercase text-muted-foreground">
                  Parámetros
                </p>
                <pre className="mt-1 max-h-40 overflow-auto text-[10px] text-muted-foreground">
                  {JSON.stringify(selected.params, null, 2)}
                </pre>
              </div>
              {selected.manifestRef && (
                <div className="rounded-md border border-border bg-muted/30 p-2">
                  <p className="text-[10px] font-medium uppercase text-muted-foreground">
                    Referencia del manifiesto
                  </p>
                  <pre className="mt-1 max-h-32 overflow-auto text-[10px] text-muted-foreground">
                    {JSON.stringify(selected.manifestRef, null, 2)}
                  </pre>
                </div>
              )}
            </TechnicalDetail>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
