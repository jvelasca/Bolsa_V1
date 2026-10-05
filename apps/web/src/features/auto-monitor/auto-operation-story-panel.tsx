/**
 * AUTO UI REFACTOR 1.0 — PILOTO de la "operación única".
 *
 * Pinta la historia ordenada (OPPORTUNITY → … → EXPLANATION) de UN ciclo y reutiliza los
 * paneles actuales como detalle experto. Read-only: NO re-deriva cifras ni completa pasos;
 * un hueco se rotula `NO MEDIDO` (nunca `0`). No sustituye ninguna pantalla existente.
 */

import { useMemo, useState } from "react";
import type { components } from "@/api/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  buildAutoOperationStory,
  type AutoOperationStoryExplanationInput,
} from "@bolsa/shared";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { useAutoDiaDFeedbackList } from "@/features/auto-monitor/use-auto-dia-d-feedback";
import { AutoReservationPanel } from "@/features/auto-monitor/auto-reservation-panel";
import { AutoConcurrencyPanel } from "@/features/auto-monitor/auto-concurrency-panel";

type DiaDFeedbackValueDto = components["schemas"]["DiaDFeedbackValueDto"];

function toExplanation(
  value: DiaDFeedbackValueDto | undefined,
): AutoOperationStoryExplanationInput | null {
  if (!value) return null;
  return {
    verdict: value.verdict,
    verdictReason: value.verdictReason ?? null,
    evidenceQuality: value.evidenceQuality,
    expectancyR: value.expectancyR ?? null,
    hitRate: value.hitRate ?? null,
    measuredCycles: value.measuredCycles ?? null,
    errorTotal: value.errorTotal ?? null,
  };
}

export function AutoOperationStoryPanel() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const feedbackList = useAutoDiaDFeedbackList();
  const [cycleId, setCycleId] = useState<string | null>(null);

  const cycles = view?.cycles ?? [];
  const selected =
    cycles.find((cycle) => cycle.cycleId === cycleId) ?? cycles[0] ?? null;

  const explanation = useMemo(() => {
    const artifact = feedbackList.data?.artifact;
    const symbol = selected?.instrumentId ?? null;
    if (!artifact?.available || !symbol) return null;
    return toExplanation(
      (artifact.values ?? []).find((item) => item.symbol === symbol),
    );
  }, [feedbackList.data, selected]);

  const story = useMemo(
    () => buildAutoOperationStory({ cycle: selected, explanation }),
    [selected, explanation],
  );

  return (
    <div className="space-y-4" data-testid="auto-operation-story-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Operación única</CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Una historia, trece etapas. Cada etapa se copia de su traza durable
            o se declara <strong>NO MEDIDO</strong>; nunca se rellena con 0.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {cycles.length > 0 ? (
            <div
              className="flex flex-wrap gap-1.5"
              data-testid="auto-operation-story-cycles"
            >
              {cycles.map((cycle) => (
                <button
                  key={cycle.cycleId}
                  type="button"
                  data-testid="auto-operation-story-cycle"
                  data-cycle-id={cycle.cycleId}
                  aria-pressed={selected?.cycleId === cycle.cycleId}
                  onClick={() => setCycleId(cycle.cycleId)}
                  className={cn(
                    "h-6 rounded border px-2 text-[10px] tabular-nums",
                    selected?.cycleId === cycle.cycleId
                      ? "border-foreground/30 bg-background text-foreground shadow-sm"
                      : "border-border text-muted-foreground",
                  )}
                >
                  {cycle.instrumentId ?? cycle.cycleId}
                </button>
              ))}
            </div>
          ) : null}

          {isLoading ? (
            <p
              className="text-sm text-muted-foreground"
              data-testid="auto-operation-story-loading"
            >
              Cargando operación…
            </p>
          ) : null}
          {isError ? (
            <p
              className="text-sm text-destructive"
              data-testid="auto-operation-story-error"
            >
              No se pudo cargar la operación.
            </p>
          ) : null}
          {!isLoading && !isError && cycles.length === 0 ? (
            <p
              className="text-xs text-muted-foreground"
              data-testid="auto-operation-story-empty"
            >
              Sin ciclos en la ventana.
            </p>
          ) : null}

          <ol className="space-y-1" data-testid="auto-operation-story">
            {story.stages.map((stage) => (
              <li
                key={stage.id}
                data-testid="auto-operation-story-stage"
                data-stage={stage.id}
                data-state={stage.state}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-border/40 pt-1 text-[11px] first:border-t-0"
              >
                <span
                  className={cn(
                    "mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full",
                    stage.dotTone,
                  )}
                />
                <span className="w-24 shrink-0 font-medium">{stage.label}</span>
                <span className={cn("uppercase tracking-wide", stage.tone)}>
                  {stage.stateLabel}
                </span>
                {stage.at ? (
                  <span className="tabular-nums text-muted-foreground">
                    {stage.at}
                  </span>
                ) : null}
                {stage.facts.map((fact) => (
                  <span
                    key={`${stage.id}-${fact.label}`}
                    className="text-muted-foreground"
                  >
                    {fact.label}:{" "}
                    <span className="text-foreground/80">{fact.value}</span>
                  </span>
                ))}
                {stage.note ? (
                  <span className="text-[10px] text-amber-600 dark:text-amber-400">
                    {stage.note}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {view ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <AutoReservationPanel reservations={view.reservations} />
          <AutoConcurrencyPanel concurrency={view.concurrency} />
        </div>
      ) : null}
    </div>
  );
}
