import { useRef, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';
import { cn } from '@/lib/utils';

export type StrategyFilterChip = {
  id: string;
  label: string;
  count: number;
  disabled?: boolean;
  title?: string;
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
 * Cada chip muestra `label (count)`.
 */
export function StrategyFilterCarousel({
  chips,
  value,
  onChange,
  ariaLabel = 'Filtro de estrategias',
  className,
  trailing,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  function scrollBy(delta: number) {
    scrollRef.current?.scrollBy({ left: delta, behavior: 'smooth' });
  }

  return (
    <div className={cn('flex min-w-0 items-center gap-0.5', className)} role="tablist" aria-label={ariaLabel}>
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
          return (
            <button
              key={chip.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              disabled={chip.disabled}
              title={chip.title ?? `${chip.label} (${chip.count})`}
              onClick={() => onChange(chip.id)}
              className={cn(
                'shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                isActive
                  ? 'border-emerald-500 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                  : 'border-border bg-muted/30 text-muted-foreground hover:border-primary/40 hover:text-foreground',
              )}
            >
              <span className="max-w-[9rem] truncate">{chip.label}</span>
              <span className="ml-1 tabular-nums opacity-70">({chip.count})</span>
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
