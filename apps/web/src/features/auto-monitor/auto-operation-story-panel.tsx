/**
 * AUTO UI REFACTOR 1.0 — PILOTO de la "operación única".
 *
 * Pinta la historia ordenada de UN ciclo y reutiliza los paneles actuales como detalle experto.
 * Separa los HECHOS de la operación (`group: OPERATION`, 13 etapas) del CONTEXTO que la originó
 * (`OPPORTUNITY` + universo PIT/régimen/ranking declarados `NO MEDIDO`). Read-only: NO re-deriva
 * cifras ni completa pasos; un hueco se rotula `NO MEDIDO` (nunca `0`).
 *
 * La etapa `EXPLANATION` enlaza directo al heatmap DÍA-D del instrumento (un clic en vez de tres
 * saltos), preseleccionando símbolo y ventana en la URL.
 */

import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  MeasurementValue,
  measurementTone,
} from "@/components/measurement-value";
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
  const [searchParams, setSearchParams] = useSearchParams();

  const cycles = view?.cycles ?? [];
  const cycleParam = searchParams.get("cycle");
  const selected =
    cycles.find((cycle) => cycle.cycleId === cycleParam) ?? cycles[0] ?? null;

  const selectCycle = (cycleId: string) => {
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        params.set("cycle", cycleId);
        return params;
      },
      { replace: true },
    );
  };

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

  // Los hechos de la operación (sin OPPORTUNITY) vs el contexto que la originó.
  const operationStages = story.stages.filter(
    (stage) => stage.group === "OPERATION",
  );
  const opportunity = story.stages.find((stage) => stage.id === "OPPORTUNITY");

  const symbol = selected?.instrumentId ?? null;
  const latestWindow = feedbackList.data?.latest ?? null;
  const openDiaDHeatmap = () => {
    if (!symbol) return;
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        params.set("mode", "dia-d");
        params.set("view", "feedback");
        if (latestWindow) params.set("window", latestWindow);
        params.set("symbol", symbol);
        return params;
      },
      { replace: false },
    );
  };

  return (
    <div className="space-y-4" data-testid="auto-operation-story-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Operación única</CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Una historia, catorce etapas. Cada etapa se copia de su traza
            durable o se declara <strong>NO MEDIDO</strong>; nunca se rellena
            con 0.
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
                  onClick={() => selectCycle(cycle.cycleId)}
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
            {operationStages.map((stage) => (
              <li
                key={stage.id}
                data-testid="auto-operation-story-stage"
                data-stage={stage.id}
                data-kind={stage.kind}
                data-group={stage.group}
                data-state={stage.state}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-border/40 pt-1 text-[11px] first:border-t-0"
              >
                <span
                  className={cn(
                    "mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full",
                    stage.dotTone,
                  )}
                />
                <span className="w-28 shrink-0 font-medium">{stage.label}</span>
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
                    <MeasurementValue
                      value={fact.value}
                      measurement={fact.measurement}
                    />
                  </span>
                ))}
                {stage.note ? (
                  <span className="text-[10px] text-amber-600 dark:text-amber-400">
                    {stage.note}
                  </span>
                ) : null}
                {stage.id === "EXPLANATION" && symbol && latestWindow ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid="auto-operation-story-open-heatmap"
                    className="h-6 rounded px-2 text-[10px]"
                    onClick={openDiaDHeatmap}
                  >
                    Ver heatmap de {symbol}
                  </Button>
                ) : null}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card
        className="rounded-xl border border-dashed border-border bg-card"
        data-testid="auto-operation-story-context"
      >
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Contexto que la originó</CardTitle>
          <p className="text-[10px] text-muted-foreground">
            {opportunity?.note ??
              "No es un hecho del ciclo: se declara lo que no se materializa."}
          </p>
        </CardHeader>
        <CardContent>
          <dl
            className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-3"
            data-testid="auto-operation-story-context-items"
          >
            {story.context.map((item) => (
              <div
                key={item.id}
                data-testid="auto-operation-story-context-item"
                data-context-id={item.id}
                data-measurement={item.measurement}
                title={item.note ?? undefined}
              >
                <dt className="text-muted-foreground">{item.label}</dt>
                <dd
                  className={cn(
                    "font-medium",
                    measurementTone(item.measurement),
                  )}
                >
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
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
