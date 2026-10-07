/**
 * AUTO · OPERAR — cockpit de la operación (ADR-044).
 *
 * Dos bloques, en el orden de las preguntas del usuario básico:
 * 1. **Oportunidades** — *lanzadera honesta* a la Mesa. El ranking vive en Mesa
 *    (`mesaOportunidadesHref()`); aquí NO se recalcula para no fabricar una segunda cifra.
 * 2. **Operaciones** — la operación única es el objeto canónico. Cada fila se identifica en
 *    lenguaje humano (`AAPL · 03 oct · Largo · Precio aplicado`) y enlaza a su historia canónica.
 *
 * Read-only: un hueco se declara NO MEDIDO, nunca 0. Estados propios (carga/error/vacío) en vez
 * de presentar la ausencia de datos como lista vacía.
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { buildOperationIdentity } from "@/features/auto/auto-operation-identity";
import {
  autoOperacionHref,
  AUTO_ACTIVIDAD_PATH,
} from "@/features/auto/auto-nav";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";
import { AutoTop3Panel } from "@/features/auto/auto-top3-panel";
import { useAutoTop3Opportunities } from "@/features/auto/use-auto-top3-opportunities";
import { mesaOportunidadesHref } from "@/features/mesa/mesa-nav-links";
import { OPERATIONAL_CONSOLE_PATH } from "@/features/confirm/daily-nav";

export function AutoOperarPage() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const top3 = useAutoTop3Opportunities();
  const cycles = view?.cycles ?? [];
  const hasOperations = cycles.length > 0;

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
          El ranking completo y su explicación viven en la Mesa: allí se rankean
          y se decide. Aquí se copia el TOP3 ya producido por AUTO, sin repetir
          el cálculo para que no existan dos cifras distintas.
        </p>
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Ranking ≠ orden: estar arriba en la lista no equivale a comprar ya.
        </p>
        <Link
          to={mesaOportunidadesHref()}
          data-testid="auto-operar-opportunities-link"
          className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm font-medium hover:bg-accent hover:text-foreground"
        >
          Ver oportunidades en la Mesa
        </Link>
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

      <section className="space-y-2" aria-labelledby="auto-operar-list-heading">
        <AutoSectionBlockHeading id="auto-operar-list-heading">
          Operaciones
        </AutoSectionBlockHeading>

        {isLoading ? (
          <p
            className="text-xs text-muted-foreground"
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

        {!isLoading && !isError && !hasOperations ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="auto-operar-empty"
          >
            Sin operaciones en la ventana.
          </p>
        ) : null}

        {hasOperations ? (
          <ul className="space-y-1.5">
            {cycles.map((cycle) => {
              const identity = buildOperationIdentity(cycle);
              return (
                <li key={cycle.cycleId}>
                  <Link
                    to={autoOperacionHref(cycle.cycleId)}
                    data-testid="auto-operar-operation-link"
                    data-cycle-id={cycle.cycleId}
                    title={identity.label}
                    className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent hover:text-foreground"
                  >
                    <span className="font-medium">{identity.label}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      Ver historia →
                    </span>
                  </Link>
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
