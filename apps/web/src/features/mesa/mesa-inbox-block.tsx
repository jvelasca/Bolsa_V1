/**
 * Bloque del inbox de Hoy (V1.23 Fase 4).
 * Colapsa cuando está vacío: un inbox vacío es una respuesta, no un hueco.
 */

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function MesaInboxBlock({
  title,
  description,
  count,
  emptyLabel,
  testId,
  headerRight,
  children,
}: {
  title: string;
  description?: string;
  /** null = el bloque no cuenta ítems (p. ej. «Sin acción»). */
  count: number | null;
  emptyLabel?: string;
  testId: string;
  headerRight?: ReactNode;
  children: ReactNode;
}) {
  const [openedByUser, setOpenedByUser] = useState(false);
  const collapsible = count === 0;
  const open = openedByUser;
  const expanded = !collapsible || openedByUser;

  return (
    <section
      className="space-y-3"
      data-testid={testId}
      data-count={count ?? ""}
      data-collapsed={collapsible && !open ? "true" : "false"}
      aria-labelledby={`${testId}-title`}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-1.5">
        <div className="flex items-baseline gap-2">
          {collapsible ? (
            <button
              type="button"
              onClick={() => setOpenedByUser((v) => !v)}
              aria-expanded={open}
              className="flex items-baseline gap-1.5 text-left"
              data-testid={`${testId}-toggle`}
            >
              {open ? (
                <ChevronDown className="h-3.5 w-3.5 translate-y-0.5 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 translate-y-0.5 text-muted-foreground" />
              )}
              <h2
                id={`${testId}-title`}
                className="text-sm font-semibold text-muted-foreground"
              >
                {title}
              </h2>
              <span className="text-xs text-muted-foreground">
                {emptyLabel ?? "Nada pendiente"}
              </span>
            </button>
          ) : (
            <>
              <h2 id={`${testId}-title`} className="text-sm font-semibold">
                {title}
              </h2>
              {count != null ? (
                <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium tabular-nums text-primary">
                  {count}
                </span>
              ) : null}
            </>
          )}
        </div>
        {headerRight}
      </header>
      {description && expanded ? (
        <p className={cn("-mt-1 text-xs text-muted-foreground")}>
          {description}
        </p>
      ) : null}
      {expanded ? <div className="space-y-3">{children}</div> : null}
    </section>
  );
}
