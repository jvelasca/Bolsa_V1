/**
 * AUTO · ACTIVIDAD (AUTO UI REFACTOR 4.0 §P1) — el centro de actividad.
 *
 * Una única línea temporal: qué ha hecho AUTO, en orden, sin tener que reconstruir la historia
 * saltando entre el monitor, el journal y el libro. Compone el read-model puro
 * `buildAutoActivityFeed` (no re-deriva) y enlaza cada hecho a su operación canónica.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §2
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";
import {
  buildAutoActivityFeed,
  type AutoActivityKind,
} from "@/features/auto/auto-activity-feed";
import { autoOperacionHref } from "@/features/auto/auto-nav";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import { cn } from "@/lib/utils";

const KIND_DOT_CLASS: Record<AutoActivityKind, string> = {
  analysis: "bg-sky-500",
  signal: "bg-indigo-500",
  selection: "bg-violet-500",
  decision: "bg-fuchsia-500",
  reservation: "bg-amber-500",
  order: "bg-cyan-500",
  fill: "bg-emerald-500",
  settlement: "bg-teal-500",
  other: "bg-muted-foreground/50",
};

export function AutoActividadPage() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const feed = buildAutoActivityFeed({
    header: view?.header ?? null,
    cycles: view?.cycles ?? [],
  });

  return (
    <div className="space-y-6" data-testid="auto-actividad-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.actividad.title}
        description={AUTO_SECTION_COPY.actividad.description}
      />

      <section className="space-y-3" aria-labelledby="auto-actividad-feed">
        <AutoSectionBlockHeading id="auto-actividad-feed">
          Lo que ha pasado
        </AutoSectionBlockHeading>

        {isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-actividad-loading"
          >
            Cargando actividad…
          </p>
        ) : null}

        {isError ? (
          <p
            className="text-sm text-destructive"
            data-testid="auto-actividad-error"
          >
            No se pudo cargar la actividad de AUTO.
          </p>
        ) : null}

        {!isLoading && !isError && !feed.hasEntries ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-actividad-empty"
          >
            {feed.emptyLabel}
          </p>
        ) : null}

        {!isLoading && !isError && feed.hasEntries ? (
          <ol className="space-y-2" data-testid="auto-actividad-entries">
            {feed.entries.map((entry) => (
              <li
                key={entry.id}
                className={cn(
                  "flex flex-wrap items-baseline gap-x-3 gap-y-0.5 rounded-md border border-border/60 px-3 py-2",
                  AUTO_USER_TEXT,
                )}
                data-testid="auto-actividad-entry"
                data-kind={entry.kind}
              >
                <span className="tabular-nums text-muted-foreground">
                  {entry.atLabel}
                </span>
                <span
                  aria-hidden="true"
                  className={cn(
                    "inline-block size-2 shrink-0 rounded-full",
                    KIND_DOT_CLASS[entry.kind],
                  )}
                />
                <span className="font-medium">
                  {entry.symbol ? `${entry.symbol} · ` : ""}
                  {entry.label}
                </span>
                {entry.cycleId ? (
                  <Link
                    to={autoOperacionHref(entry.cycleId)}
                    className="ml-auto text-xs underline hover:text-primary"
                    data-testid="auto-actividad-operation-link"
                  >
                    Ver operación →
                  </Link>
                ) : null}
              </li>
            ))}
          </ol>
        ) : null}
      </section>
    </div>
  );
}
