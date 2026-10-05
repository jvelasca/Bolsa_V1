/**
 * AUTO · OPERAR — lista de operaciones + la operación seleccionada (ADR-044).
 *
 * La operación única es el objeto canónico del espacio. La lista enlaza a la
 * ruta dedicada `/auto/operar/operacion/:cycleId` (selección en la URL). Read-only:
 * un hueco se declara NO MEDIDO, nunca 0.
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { AutoOperationStoryPanel } from "@/features/auto-monitor/auto-operation-story-panel";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { autoOperacionHref } from "@/features/auto/auto-nav";
import { OPERATIONAL_CONSOLE_PATH } from "@/features/confirm/daily-nav";

export function AutoOperarPage() {
  const { view } = useAutoOperationalMonitor();
  const cycles = view?.cycles ?? [];

  return (
    <div className="space-y-6" data-testid="auto-operar-page">
      <AutoSectionHeading
        title="Operar"
        description="Oportunidades, operaciones y la operación seleccionada. Read-only: un paso sin traza durable se declara NO MEDIDO; nunca se rellena con 0."
      />

      <section className="space-y-2" aria-labelledby="auto-operar-list-heading">
        <AutoSectionBlockHeading id="auto-operar-list-heading">
          Operaciones
        </AutoSectionBlockHeading>
        {cycles.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin operaciones en la ventana.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {cycles.map((cycle) => (
              <li key={cycle.cycleId}>
                <Link
                  to={autoOperacionHref(cycle.cycleId)}
                  data-testid="auto-operar-operation-link"
                  data-cycle-id={cycle.cycleId}
                  className="inline-flex h-7 items-center rounded border border-border px-2 text-xs hover:bg-accent hover:text-foreground"
                >
                  {cycle.instrumentId ?? cycle.cycleId}
                </Link>
              </li>
            ))}
          </ul>
        )}
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

      <section
        className="space-y-2"
        aria-labelledby="auto-operar-story-heading"
      >
        <AutoSectionBlockHeading id="auto-operar-story-heading">
          Operación seleccionada
        </AutoSectionBlockHeading>
        <AutoOperationStoryPanel />
      </section>
    </div>
  );
}
