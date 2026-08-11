import { Link } from "react-router-dom";
import { Bell, FlaskConical, Radar } from "lucide-react";
import { cn } from "@/lib/utils";

interface ListHubShortcutsSectionProps {
  listId: string;
  listName: string;
}

const shortcutClassName = cn(
  "flex min-w-0 flex-1 items-center gap-2 rounded-md border border-border/70 bg-background/80 px-2.5 py-2",
  "text-left text-xs transition-colors hover:bg-accent/60 hover:text-foreground",
);

/**
 * Accesos directos al mismo flujo que los menús generales, acotados a esta lista
 * cuando la sección lo soporta (Rastreadores vía ?listId=).
 */
export function ListHubShortcutsSection({
  listId,
  listName,
}: ListHubShortcutsSectionProps) {
  const encoded = encodeURIComponent(listId);
  const nameHint = listName.trim() || "esta lista";

  return (
    <section className="space-y-1.5" aria-label={`Accesos de ${nameHint}`}>
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Abrir en…
      </p>
      <div className="flex flex-col gap-1.5 sm:flex-row">
        <Link
          to={`/screeners?listId=${encoded}`}
          className={shortcutClassName}
          title={`Rastreadores con universo «${nameHint}»`}
        >
          <Radar className="h-3.5 w-3.5 shrink-0 text-primary" />
          <span className="min-w-0">
            <span className="block font-medium">Rastreadores</span>
            <span className="block truncate text-[10px] text-muted-foreground">
              Escaneo y señales de esta lista
            </span>
          </span>
        </Link>
        <Link
          to="/alerts"
          className={shortcutClassName}
          title="Alertas de precio y de señal"
        >
          <Bell className="h-3.5 w-3.5 shrink-0 text-primary" />
          <span className="min-w-0">
            <span className="block font-medium">Alertas</span>
            <span className="block truncate text-[10px] text-muted-foreground">
              Precio y estrategia
            </span>
          </span>
        </Link>
        <Link
          to={`/backtests?tab=run&listId=${encoded}`}
          className={shortcutClassName}
          title={`Backtesting con universo «${nameHint}»`}
        >
          <FlaskConical className="h-3.5 w-3.5 shrink-0 text-primary" />
          <span className="min-w-0">
            <span className="block font-medium">Backtesting</span>
            <span className="block truncate text-[10px] text-muted-foreground">
              Lista AUTO / embudo de esta lista
            </span>
          </span>
        </Link>
      </div>
    </section>
  );
}
