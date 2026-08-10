import { useRef, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

export type StrategyFilterChip = {
  id: string;
  label: string;
  count: number;
  disabled?: boolean;
  title?: string;
  /**
   * Hay estrategias de este cajón en la selección de Probar + coach.
   * Se puede encender aunque el chip no sea el filtro activo.
   */
  hasSelection?: boolean;
  /** Cuántas del cajón están marcadas (tooltip / accesibilidad). */
  selectedCount?: number;
};

type Props = {
  chips: StrategyFilterChip[];
  value: string;
  onChange: (id: string) => void;
  /** aria-label del grupo */
  ariaLabel?: string;
  className?: string;
  /** Slot tras el chevron derecho (p. ej. menú … de favoritos). */
  trailing?: ReactNode;
};

/**
 * Carrusel horizontal de filtros de estrategias (mismo patrón visual que
 * el carrusel de listas en Trading: chips pill + chevrons + scroll + …).
 *
 * Verde = filtro activo y/o cajón con estrategias seleccionadas para probar.
 */
export function StrategyFilterCarousel({
  chips,
  value,
  onChange,
  ariaLabel = "Filtro de estrategias",
  className,
  trailing,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  function scrollBy(delta: number) {
    scrollRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  }

  return (
    <div
      className={cn("flex min-w-0 items-center gap-0.5", className)}
      role="tablist"
      aria-label={ariaLabel}
    >
      <IconButton
        icon={ChevronLeft}
        title="Desplazar filtros"
        className="shrink-0 opacity-70"
        onClick={() => scrollBy(-140)}
      />
      <div
        ref={scrollRef}
        className="scroll-area flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-0.5"
      >
        {chips.map((chip) => {
          const isActive = chip.id === value;
          const hasSelection = Boolean(chip.hasSelection);
          const lit = isActive || hasSelection;
          const selectedN = chip.selectedCount ?? 0;
          const titleParts = [
            chip.title ?? `${chip.label} (${chip.count})`,
            hasSelection && selectedN > 0
              ? `${selectedN} seleccionada${selectedN === 1 ? "" : "s"} para probar`
              : null,
            isActive ? "Filtro activo" : null,
          ].filter(Boolean);
          return (
            <button
              key={chip.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-pressed={hasSelection || undefined}
              disabled={chip.disabled}
              title={titleParts.join(" · ")}
              onClick={() => onChange(chip.id)}
              className={cn(
                "shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
                isActive &&
                  "border-emerald-500 bg-emerald-500/20 text-emerald-800 ring-1 ring-emerald-500/40 dark:text-emerald-300",
                !isActive &&
                  hasSelection &&
                  "border-emerald-500/80 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
                !lit &&
                  "border-border bg-muted/30 text-muted-foreground hover:border-primary/40 hover:text-foreground",
              )}
            >
              <span className="max-w-[9rem] truncate">{chip.label}</span>
              <span className="ml-1 tabular-nums opacity-70">
                ({chip.count})
              </span>
              {hasSelection && selectedN > 0 ? (
                <span className="ml-1 tabular-nums font-semibold text-emerald-600 dark:text-emerald-400">
                  ·{selectedN}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <IconButton
        icon={ChevronRight}
        title="Desplazar filtros"
        className="shrink-0 opacity-70"
        onClick={() => scrollBy(140)}
      />
      {trailing}
    </div>
  );
}
