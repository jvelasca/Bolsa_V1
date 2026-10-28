/**
 * AUTO · OPERAR — cockpit de la operación (ADR-044 + UI Contract 5.0).
 *
 * Dos bloques, en el orden de las preguntas del usuario básico:
 * 1. **Oportunidades** — el TOP3 que AUTO situó en los primeros puestos de su último análisis
 *    (subconjunto del universo completo de `Hoy → Oportunidades`; `UI5-07`). El ranking se copia
 *    ya producido, no se recalcula.
 * 2. **Operaciones** — la operación única es el objeto canónico. Cada fila lleva la **insignia de
 *    modo** (`AUTO · SIMULADO`, `UI5-10`) y su **peldaño** de la escalera universal
 *    (`UI5-09`/`UI5-20`), en lenguaje humano, y enlaza a su historia canónica.
 *
 * Read-only: un hueco se declara «Sin dato todavía», nunca 0. Estados propios (carga/error/vacío)
 * en vez de presentar la ausencia de datos como lista vacía.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-07 §UI5-09 §UI5-10 §UI5-17
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { ModeBadge } from "@/components/mode-badge";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { buildOperationIdentity } from "@/features/auto/auto-operation-identity";
import { operationLadderRungFromCycle } from "@/features/auto/auto-operation-ladder";
import {
  autoOperacionHref,
  AUTO_ACTIVIDAD_PATH,
} from "@/features/auto/auto-nav";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";
import { AutoTop3Panel } from "@/features/auto/auto-top3-panel";
import { AutoHoldSummaryLine } from "@/features/auto/auto-hold-declarations-panel";
import { AutoOperarVerifyAction } from "@/features/auto/auto-operar-verify-action";
import { useAutoTop3Opportunities } from "@/features/auto/use-auto-top3-opportunities";
import { AUTO_OPERATION_MODE } from "@/features/operations/operation-mode";
import { mesaOportunidadesHref } from "@/features/mesa/mesa-nav-links";
import { OPERATIONAL_CONSOLE_PATH } from "@/features/confirm/daily-nav";

/** Sin cuenta activa la query no se ejecuta: no hay operaciones ni HOLD que afirmar. */
const AUTO_OPERAR_NOT_CONSULTED =
  "Sin cuenta activa: no se pudieron leer las operaciones ni las declaraciones de HOLD.";

export function AutoOperarPage() {
  const { view, isLoading, isError, readState } = useAutoOperationalMonitor();
  const top3 = useAutoTop3Opportunities();
  const cycles = view?.cycles ?? [];
  const hasOperations = cycles.length > 0;
  // B-5 — declaraciones de HOLD de la ACTIVE: «no evaluable» no se presenta como «sin señal» y
  // la ausencia de declaraciones no se presenta como «no hubo HOLD».
  const holdsCount = view?.signalHolds?.length ?? 0;
  // Sin cuenta activa la query no se ejecuta: ni «sin operaciones» ni «sin HOLD» son afirmables.
  const holdNotConsulted = readState === "not_consulted";

  return (
    <div className="space-y-6" data-testid="auto-operar-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.operar.title}
        description={AUTO_SECTION_COPY.operar.description}
      />

      <section
        className="space-y-2 rounded-lg border border-border bg-card p-4"
        aria-labelledby="auto-operar-opportunities-heading"
        data-testid="auto-operar-opportunities"
      >
        <AutoSectionBlockHeading id="auto-operar-opportunities-heading">
          Oportunidades
        </AutoSectionBlockHeading>
        <AutoTop3Panel
          view={top3.view}
          isLoading={top3.isLoading}
          isError={top3.isError}
          testId="auto-operar-top3"
        />
        <p className="text-sm text-muted-foreground">
          Este TOP3 es el subconjunto de oportunidades que AUTO situó en los
          primeros puestos de su último análisis. El universo completo y su
          explicación viven en{" "}
          <Link
            to={mesaOportunidadesHref()}
            data-testid="auto-operar-opportunities-link"
            className="underline hover:text-primary"
          >
            Hoy → Oportunidades
          </Link>
          .
        </p>
        {/* `ranking ≠ decisión` ya lo declara el propio panel del TOP3 (`AUTO_TOP3_RANK_NOTE`):
            aquí no se repite (evita afirmar el mismo hecho dos veces en el primer nivel). */}
        <p className="text-sm text-muted-foreground">
          <Link
            to={AUTO_ACTIVIDAD_PATH}
            className="underline hover:text-primary"
            data-testid="auto-operar-activity-link"
          >
            Ver toda la actividad de AUTO
          </Link>
        </p>
      </section>

      <section
        className="space-y-2 rounded-lg border border-border bg-card p-4"
        aria-labelledby="auto-operar-list-heading"
      >
        <AutoSectionBlockHeading id="auto-operar-list-heading">
          Operaciones
        </AutoSectionBlockHeading>

        {/* B-5 — la señal (por qué no se abrió nada) se declara SIEMPRE en el mismo sitio: la
            primera línea de Operaciones, antes de la lista. Un hecho, una posición, un rótulo
            distinto solo según haya o no operaciones en la ventana. */}
        {!isLoading && !isError && !holdNotConsulted && !hasOperations ? (
          <AutoHoldSummaryLine
            holds={view?.signalHolds ?? []}
            testId="auto-operar-silence"
          />
        ) : null}
        {!isLoading && !isError && hasOperations && holdsCount > 0 ? (
          <AutoHoldSummaryLine
            holds={view?.signalHolds ?? []}
            testId="auto-operar-hold-summary"
          />
        ) : null}

        {isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-operar-loading"
          >
            Cargando operaciones…
          </p>
        ) : null}

        {isError ? (
          <p
            className="text-sm text-destructive"
            data-testid="auto-operar-error"
          >
            No se pudieron cargar las operaciones.
          </p>
        ) : null}

        {!isLoading && !isError && holdNotConsulted ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-operar-not-consulted"
          >
            {AUTO_OPERAR_NOT_CONSULTED}
          </p>
        ) : null}

        {!isLoading && !isError && !holdNotConsulted && !hasOperations ? (
          <div className="space-y-1" data-testid="auto-operar-empty-block">
            <p
              className="text-sm text-muted-foreground"
              data-testid="auto-operar-empty"
            >
              Sin operaciones en la ventana.
            </p>
            {/* B-5 — el vacío no es mudo: declara que no hay operaciones y ofrece el siguiente
                paso. El desglose de la señal ya se declaró en la primera línea del bloque. */}
            <p className="text-sm text-muted-foreground">
              <Link
                to={AUTO_ACTIVIDAD_PATH}
                className="underline hover:text-primary"
                data-testid="auto-operar-why-link"
              >
                Ver por qué AUTO no operó
              </Link>
            </p>
          </div>
        ) : null}

        {hasOperations ? (
          <ul className="space-y-1.5">
            {cycles.map((cycle) => {
              const ladder = operationLadderRungFromCycle(cycle);
              // Un término = un significado (`UI5-20`): la fila usa el peldaño canónico, no
              // el `statusLabel` local del monitor.
              const identity = buildOperationIdentity({
                ...cycle,
                statusLabel: ladder.label,
              });
              return (
                <li
                  key={cycle.cycleId}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
                >
                  <Link
                    to={autoOperacionHref(cycle.cycleId)}
                    data-testid="auto-operar-operation-link"
                    data-cycle-id={cycle.cycleId}
                    title={identity.label}
                    className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-0.5 hover:text-foreground"
                  >
                    <span className="font-medium">{identity.label}</span>
                    <ModeBadge
                      badge={AUTO_OPERATION_MODE}
                      testId={`auto-operar-mode-${cycle.cycleId}`}
                    />
                    {ladder.note ? (
                      <span className="text-[10px] text-muted-foreground">
                        {ladder.note}
                      </span>
                    ) : null}
                    <span className="ml-auto text-xs text-muted-foreground">
                      Ver operación →
                    </span>
                  </Link>
                  {/* P2 — entrada descubrible a la verificación DÍA-D desde el listado:
                      solo aparece si la estrategia EJECUTADA del ciclo se resuelve. */}
                  <AutoOperarVerifyAction cycle={cycle} />
                </li>
              );
            })}
          </ul>
        ) : null}

        <p className="text-xs text-muted-foreground">
          Diagnóstico avanzado de la cadena compleja en la{" "}
          <Link
            to={OPERATIONAL_CONSOLE_PATH}
            className="underline hover:text-primary"
          >
            Consola avanzada
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
