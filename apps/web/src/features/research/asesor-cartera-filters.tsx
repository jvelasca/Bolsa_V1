/**
 * Filtros de Cartera del Asesor — slice A3·b.
 *
 * Chips de estado (con su recuento) + «Solo con posición». El panel conserva el
 * estado del filtro y el orden; aquí solo se pinta la barra y se avisa del
 * cambio. Ningún chip promete una compra: son categorías de presentación.
 *
 * El marcado y los `data-testid` son los del panel original.
 */

import {
  ASESOR_CARTERA_STATES,
  type AsesorCarteraFilterV1,
  type AsesorCarteraSummaryV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

export function AsesorCarteraFilters({
  filter,
  onChange,
  countByState,
  total,
}: {
  filter: AsesorCarteraFilterV1;
  onChange: (next: AsesorCarteraFilterV1) => void;
  countByState: AsesorCarteraSummaryV1["byState"];
  total: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        aria-pressed={filter.state === "todos"}
        className={cn(
          "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
          filter.state === "todos"
            ? "border-primary/50 bg-primary/10 text-primary"
            : "border-border text-muted-foreground hover:bg-accent",
        )}
        onClick={() => onChange({ ...filter, state: "todos" })}
      >
        Todos ({total})
      </button>
      {ASESOR_CARTERA_STATES.map((state) => {
        const count = countByState[state.id] || 0;
        return (
          <button
            key={state.id}
            type="button"
            aria-pressed={filter.state === state.id}
            title={state.meaning}
            data-testid={`asesor-cartera-filter-${state.id}`}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
              filter.state === state.id
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
            onClick={() => onChange({ ...filter, state: state.id })}
          >
            {state.label} ({count})
          </button>
        );
      })}
      <label className="ml-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={filter.onlyWithPosition}
          onChange={(event) =>
            onChange({ ...filter, onlyWithPosition: event.target.checked })
          }
          data-testid="asesor-cartera-only-position"
        />
        Solo con posición
      </label>
    </div>
  );
}
