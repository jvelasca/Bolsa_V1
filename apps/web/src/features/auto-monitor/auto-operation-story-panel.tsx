/**
 * AUTO UI REFACTOR 3.0 (S2) — la "operación única" en tres bloques.
 *
 * Pinta la historia ordenada de UN ciclo y la separa en el modelo mental del usuario:
 *
 *   1. HISTORIA DE ESTA OPERACIÓN — los hechos del ciclo (grupo `OPERATION`; `EXIT` plegado en
 *      `SETTLEMENT`): Señal → Selección → Decisión → Riesgo → Reserva → Orden → Ejecución →
 *      Posición → Protección → Liquidación → Resultado.
 *   2. CONTEXTO — lo que la originó (instrumento/estrategia/dirección + universo PIT/régimen/
 *      ranking declarados `NO MEDIDO`).
 *   3. ¿QUÉ APRENDEMOS? — la etapa `EXPLANATION` (DÍA-D/OOS), que es conocimiento **cross-ciclo**
 *      y por eso NO vive dentro de los hechos de la operación (grupo propio `EXPLANATION`).
 *
 * Read-only y puro: NO re-deriva cifras ni completa pasos; un hueco se rotula «Sin dato todavía»
 * en primer nivel (el rótulo técnico `NO MEDIDO` se conserva en `title`).
 *
 * La etapa `EXPLANATION` enlaza directo al heatmap DÍA-D del instrumento (un clic en vez de tres
 * saltos), preseleccionando símbolo y ventana en la URL. Los deep-links son **canónicos**
 * (`/auto/analisis?tab=dia-d...` y `/auto-monitor?mode=current&cycle=...`).
 */

import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  type AutoOperationStoryExplanationIdentity,
  type AutoOperationStoryExplanationInput,
  type AutoOperationStoryExplanationResolution,
  type AutoOperationStoryStage,
} from "@bolsa/shared";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { useAutoDiaDFeedbackList } from "@/features/auto-monitor/use-auto-dia-d-feedback";
import { buildOperationIdentity } from "@/features/auto/auto-operation-identity";
import {
  plainStageLabel,
  plainStateLabel,
} from "@/features/auto/auto-story-plain-labels";
import {
  autoDiaDHref,
  autoTechnicalDetailHref,
} from "@/features/auto/auto-nav";

type DiaDFeedbackValueDto = components["schemas"]["DiaDFeedbackValueDto"];
type DiaDFeedbackCycleDto = components["schemas"]["DiaDFeedbackCycleDto"];

/**
 * Resuelve la explicación DÍA-D de UN ciclo (pura). Precedencia DECLARADA:
 *
 *   1. por `cycleId` (exacta): el ciclo figura en el índice `cycles[]` del artefacto; se usa el
 *      valor de su instrumento y los ejes del índice (`entryDay`/estrategia).
 *   2. por instrumento (fallback PARCIAL): sin fila de ciclo; se resuelve por símbolo y se declara.
 *
 * Devuelve `null` si no hay valor para el instrumento (⇒ `NO MEDIDO`, como antes). NO re-deriva
 * cifras: copia el valor AGREGADO por instrumento y declara cómo lo ató al ciclo.
 */
export function resolveExplanationForCycle(input: {
  cycle: {
    cycleId: string;
    instrumentId: string | null;
    strategyVersion?: string | null;
    direction?: string | null;
    entryDay: string | null;
  } | null;
  values: readonly DiaDFeedbackValueDto[];
  cycles: readonly DiaDFeedbackCycleDto[];
}): AutoOperationStoryExplanationInput | null {
  const { cycle, values, cycles } = input;
  if (!cycle) return null;
  const cycleRef =
    cycles.find((item) => item.cycleId === cycle.cycleId) ?? null;
  const symbol = cycleRef?.symbol ?? cycle.instrumentId ?? null;
  if (!symbol) return null;
  const value = values.find((item) => item.symbol === symbol);
  if (!value) return null;
  const resolution: AutoOperationStoryExplanationResolution = cycleRef
    ? "cycleId"
    : "instrument";
  const identity: AutoOperationStoryExplanationIdentity = {
    cycleId: cycle.cycleId,
    instrument: symbol,
    strategyVersion: cycleRef?.strategyVersion ?? cycle.strategyVersion ?? null,
    direction: cycle.direction ?? null,
    entryDay: cycleRef?.entryDay ?? cycle.entryDay ?? null,
    timeframe: null,
    regime: null,
  };
  return {
    verdict: value.verdict,
    verdictReason: value.verdictReason ?? null,
    evidenceQuality: value.evidenceQuality,
    expectancyR: value.expectancyR ?? null,
    hitRate: value.hitRate ?? null,
    measuredCycles: value.measuredCycles ?? null,
    errorTotal: value.errorTotal ?? null,
    identity,
    resolution,
  };
}

export type AutoOperationSelection<T> = {
  /** Id pedido EXPLÍCITAMENTE (ruta canónica o `?cycle=`); `null` si no hay ninguno. */
  requestedCycleId: string | null;
  /** Ciclo a pintar; `null` si no hay selección ni fallback disponible. */
  selectedCycle: T | null;
  /** Id explícito que NO existe en la ventana (no se cae a `cycles[0]`). */
  notFound: boolean;
};

/**
 * Resuelve el ciclo de la operación a partir de una selección EXPLÍCITA (ruta canónica
 * `/auto/operar/operacion/:cycleId` o `?cycle=`). Un id explícito que NO existe en la ventana
 * NO cae silenciosamente a `cycles[0]`: se declara `notFound` para que el panel muestre
 * «Operación no encontrada». Sin id explícito se conserva el fallback histórico a `cycles[0]`.
 *
 * Durante la carga (`hasLoaded === false`) un id no resuelto NO se declara `notFound`: evita un
 * falso negativo en el primer render (los ciclos aún no han llegado).
 */
export function resolveAutoOperationSelection<
  T extends { cycleId: string },
>(input: {
  cycles: readonly T[];
  overrideCycleId?: string | null;
  queryCycleId?: string | null;
  hasLoaded: boolean;
}): AutoOperationSelection<T> {
  const requestedCycleId =
    input.overrideCycleId?.trim() || input.queryCycleId?.trim() || null;
  const resolved = requestedCycleId
    ? (input.cycles.find((cycle) => cycle.cycleId === requestedCycleId) ?? null)
    : null;
  const notFound =
    requestedCycleId !== null && input.hasLoaded && resolved === null;
  return {
    requestedCycleId,
    notFound,
    selectedCycle: notFound ? null : (resolved ?? input.cycles[0] ?? null),
  };
}

/**
 * Fila de una etapa: lenguaje de usuario en primer nivel; el término técnico se conserva en el
 * `title` (tooltip) para no perder vocabulario de auditoría (spec 3.0 §1.7/§4).
 */
function StoryStageRow({
  stage,
  testId = "auto-operation-story-stage",
  children,
}: {
  stage: AutoOperationStoryStage;
  testId?: string;
  children?: React.ReactNode;
}) {
  return (
    <li
      data-testid={testId}
      data-stage={stage.id}
      data-kind={stage.kind}
      data-group={stage.group}
      data-state={stage.state}
      className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-border/40 pt-1 text-sm first:border-t-0"
    >
      <span
        className={cn(
          "mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full",
          stage.dotTone,
        )}
      />
      <span className="w-40 shrink-0 font-medium">
        {plainStageLabel(stage.id, stage.label)}
      </span>
      <span
        className={cn("uppercase tracking-wide", stage.tone)}
        title={stage.stateLabel}
      >
        {plainStateLabel(stage.state, stage.stateLabel)}
      </span>
      {stage.at ? (
        <span className="tabular-nums text-muted-foreground">{stage.at}</span>
      ) : null}
      {stage.facts.map((fact) => (
        <span
          key={`${stage.id}-${fact.label}`}
          className="text-muted-foreground"
        >
          {fact.label}:{" "}
          <MeasurementValue value={fact.value} measurement={fact.measurement} />
        </span>
      ))}
      {stage.note ? (
        <span className="text-xs text-amber-600 dark:text-amber-400">
          {stage.note}
        </span>
      ) : null}
      {children}
    </li>
  );
}

export function AutoOperationStoryPanel({
  cycleIdOverride,
  onSelectCycle,
}: {
  /** Fuerza el ciclo mostrado (ruta canónica `/auto/operar/operacion/:cycleId`). */
  cycleIdOverride?: string | null;
  /** Sustituye la escritura de `?cycle=` (p. ej. navegar a la ruta canónica). */
  onSelectCycle?: (cycleId: string) => void;
} = {}) {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const feedbackList = useAutoDiaDFeedbackList();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const cycles = view?.cycles ?? [];
  const cycleParam = searchParams.get("cycle");
  const hasLoaded = !isLoading && !isError && view != null;
  const {
    requestedCycleId,
    selectedCycle: selected,
    notFound,
  } = resolveAutoOperationSelection({
    cycles,
    overrideCycleId: cycleIdOverride,
    queryCycleId: cycleParam,
    hasLoaded,
  });

  const selectCycle = (cycleId: string) => {
    if (onSelectCycle) {
      onSelectCycle(cycleId);
      return;
    }
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
    if (!artifact?.available || !selected) return null;
    // Identidad explícita: a QUÉ operación responde la explicación. `entryDay` se copia del sello
    // temporal de la SEÑAL (no se re-deriva); timeframe/régimen no los materializa el artefacto.
    // La resolución la decide `resolveExplanationForCycle`: por `cycleId` (índice `cycles[]`) o,
    // si el artefacto no trae la clave, por instrumento (fallback declarado como PARCIAL).
    const signalAt =
      selected.steps.find((step) => step.id === "SIGNAL")?.at ?? null;
    return resolveExplanationForCycle({
      cycle: {
        cycleId: selected.cycleId,
        instrumentId: selected.instrumentId ?? null,
        strategyVersion: selected.strategyVersion ?? null,
        direction: selected.direction ?? null,
        entryDay: signalAt ? signalAt.slice(0, 10) : null,
      },
      values: artifact.values ?? [],
      cycles: artifact.cycles ?? [],
    });
  }, [feedbackList.data, selected]);

  const story = useMemo(
    () => buildAutoOperationStory({ cycle: selected, explanation }),
    [selected, explanation],
  );

  // Tres bloques: hechos de la operación (sin `EXPLANATION`, que es cross-ciclo), contexto que la
  // originó y aprendizaje. Una etapa plegada (EXIT → SETTLEMENT) no se pinta como fila propia.
  const operationStages = story.stages.filter(
    (stage) => stage.group === "OPERATION" && stage.foldedInto === null,
  );
  const opportunity = story.stages.find((stage) => stage.id === "OPPORTUNITY");
  const explanationStage = story.stages.find(
    (stage) => stage.id === "EXPLANATION",
  );

  const symbol = selected?.instrumentId ?? null;
  const latestWindow = feedbackList.data?.latest ?? null;
  const identityLabel = selected
    ? buildOperationIdentity(selected).label
    : null;

  // Destino canónico: el DÍA-D vive en el workspace AUTO (`/auto/analisis?tab=dia-d`),
  // NO en la URL del monitor. Escribir `mode=dia-d` sobre la ruta actual era inerte.
  const openDiaDHeatmap = () => {
    if (!symbol) return;
    navigate(autoDiaDHref({ window: latestWindow, symbol }));
  };

  // La operación es el resumen/interpretación; el crudo (header, timeline, reservas,
  // concurrencia) vive en la vista experta `current` del monitor experto, sin duplicar
  // paneles. El `cycle` viaja para que el monitor enfoque el ciclo de esta operación.
  const openTechnicalDetail = () => {
    navigate(autoTechnicalDetailHref(selected?.cycleId));
  };

  return (
    <div className="space-y-4" data-testid="auto-operation-story-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-base">
              {identityLabel ?? "Operación"}
            </CardTitle>
            {selected ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                data-testid="auto-operation-story-open-technical"
                className="h-7 rounded px-2 text-xs"
                onClick={openTechnicalDetail}
              >
                Detalle técnico (ventana actual)
              </Button>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            ¿Por qué se abrió? → ¿Qué hizo AUTO? → ¿Cómo va? → ¿Qué aprendemos?
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {cycles.length > 0 ? (
            <div
              className="flex flex-wrap gap-1.5"
              data-testid="auto-operation-story-cycles"
            >
              {cycles.map((cycle) => {
                const identity = buildOperationIdentity(cycle);
                return (
                  <button
                    key={cycle.cycleId}
                    type="button"
                    data-testid="auto-operation-story-cycle"
                    data-cycle-id={cycle.cycleId}
                    title={identity.label}
                    aria-pressed={selected?.cycleId === cycle.cycleId}
                    onClick={() => selectCycle(cycle.cycleId)}
                    className={cn(
                      "h-7 rounded border px-2 text-xs tabular-nums",
                      selected?.cycleId === cycle.cycleId
                        ? "border-foreground/30 bg-background text-foreground shadow-sm"
                        : "border-border text-muted-foreground",
                    )}
                  >
                    {identity.label}
                  </button>
                );
              })}
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
              className="text-sm text-muted-foreground"
              data-testid="auto-operation-story-empty"
            >
              Sin ciclos en la ventana.
            </p>
          ) : null}
          {notFound ? (
            <p
              className="text-sm text-destructive"
              data-testid="auto-operation-story-not-found"
              data-cycle-id={requestedCycleId ?? undefined}
            >
              Operación no encontrada. El ciclo{" "}
              <span className="font-medium">{requestedCycleId}</span> no está en
              la ventana actual del monitor.
            </p>
          ) : null}

          {selected ? (
            <>
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Historia de esta operación
                </p>
                <ol className="space-y-1" data-testid="auto-operation-story">
                  {operationStages.map((stage) => (
                    <StoryStageRow key={stage.id} stage={stage} />
                  ))}
                </ol>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      {selected ? (
        <Card
          className="rounded-xl border border-dashed border-border bg-card"
          data-testid="auto-operation-story-context"
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Contexto</CardTitle>
            <p className="text-xs text-muted-foreground">
              {opportunity?.note ??
                "No es un hecho del ciclo: se declara lo que no se materializa."}
            </p>
          </CardHeader>
          <CardContent>
            <dl
              className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3"
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
      ) : null}

      {selected && explanationStage ? (
        <Card
          className="rounded-xl border border-border bg-card"
          data-testid="auto-operation-story-learning"
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">¿Qué aprendemos?</CardTitle>
            <p className="text-xs text-muted-foreground">
              DÍA-D es conocimiento de todos los ciclos del instrumento: no es
              un hecho de esta operación.
            </p>
          </CardHeader>
          <CardContent>
            <ol className="space-y-1">
              <StoryStageRow
                stage={explanationStage}
                testId="auto-operation-story-explanation"
              >
                {symbol && latestWindow ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid="auto-operation-story-open-heatmap"
                    className="h-7 rounded px-2 text-xs"
                    onClick={openDiaDHeatmap}
                  >
                    Ver heatmap de {symbol}
                  </Button>
                ) : null}
              </StoryStageRow>
            </ol>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
