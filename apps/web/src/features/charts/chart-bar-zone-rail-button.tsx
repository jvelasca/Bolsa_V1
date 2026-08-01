import { ChevronDown, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

/** Botón de acceso directo en la barra (sin menú). */
export function ChartBarZoneChipButton({
  label,
  hint,
  isActive,
  disabled,
  onActivate,
  children,
  className,
  buttonClassName,
}: {
  label?: string;
  hint: string;
  isActive?: boolean;
  disabled?: boolean;
  onActivate: () => void;
  children?: ReactNode;
  className?: string;
  buttonClassName?: string;
}) {
  return (
    <button
      type="button"
      title={hint}
      disabled={disabled}
      onClick={onActivate}
      className={cn(
        'inline-flex h-[1.375rem] shrink-0 items-center rounded px-1.5 text-[11px] font-medium leading-none',
        'hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40',
        children ? 'min-w-0 justify-start overflow-hidden' : 'min-w-[2.25rem] justify-center tabular-nums',
        isActive && 'bg-accent text-primary ring-1 ring-primary/40',
        !isActive && 'text-muted-foreground hover:text-foreground',
        className,
        buttonClassName,
      )}
    >
      {children ?? <span className="truncate">{label}</span>}
    </button>
  );
}

/** Icono de familia/zona con muesca para menú y favoritos. */
export function ChartBarZoneIconAnchor({
  icon: Icon,
  hint,
  title,
  badgeLabel,
  isMenuOpen,
  showMenu,
  containerRef,
  onOpenMenu,
}: {
  icon: LucideIcon;
  hint: string;
  title: string;
  /** Valor activo en zonas de selección (p. ej. 1D, Velas). */
  badgeLabel?: string;
  isMenuOpen?: boolean;
  showMenu: boolean;
  containerRef?: (el: HTMLDivElement | null) => void;
  onOpenMenu: () => void;
}) {
  const hasBadge = Boolean(badgeLabel);

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative h-[1.375rem] shrink-0',
        hasBadge ? 'min-w-[1.375rem]' : showMenu ? 'w-[1.625rem]' : 'w-[1.375rem]',
        showMenu && hasBadge && 'pr-1',
      )}
    >
      <button
        type="button"
        title={hint}
        onClick={() => {
          if (showMenu) onOpenMenu();
        }}
        className={cn(
          'flex h-[1.375rem] max-w-full items-center rounded transition-colors hover:bg-accent',
          hasBadge ? 'gap-0.5 px-1' : 'w-[1.375rem] justify-center',
          isMenuOpen && 'bg-accent text-primary ring-1 ring-primary/40',
          !isMenuOpen && 'text-primary',
        )}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {hasBadge ? (
          <span className="max-w-[4.5rem] truncate text-[11px] font-medium leading-none tabular-nums">
            {badgeLabel}
          </span>
        ) : null}
        <span className="sr-only">{title}</span>
      </button>
      {showMenu && (
        <button
          type="button"
          title="Más opciones y favoritos"
          aria-label={`${title}: más opciones y favoritos`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenMenu();
          }}
          className={cn(
            'absolute bottom-0 right-0 z-20 flex h-2.5 w-2.5 items-center justify-center rounded-tl-sm border border-border/60 bg-card/95 text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground',
            isMenuOpen && 'bg-accent text-primary',
          )}
        >
          <ChevronDown className="h-1.5 w-1.5" strokeWidth={3} />
        </button>
      )}
    </div>
  );
}

export type BarZoneDisplayIdsOptions = {
  /** Modo display (Valor/Cursor): incluye ancla aunque no esté en favoritos. */
  includeActive?: boolean;
};

/** Ordena favoritos visibles según grupos del menú. */
export function resolveBarZoneDisplayIds<T extends string>(
  favorites: T[],
  activeId: T,
  menuGroups: T[][],
  options?: BarZoneDisplayIdsOptions,
): T[] {
  const set = new Set(favorites);
  if (options?.includeActive) {
    set.add(activeId);
  }
  const ordered: T[] = [];
  for (const group of menuGroups) {
    for (const id of group) {
      if (set.has(id) && !ordered.includes(id)) ordered.push(id);
    }
  }
  for (const id of set) {
    if (!ordered.includes(id)) ordered.push(id);
  }
  if (ordered.length > 0) return ordered;
  return options?.includeActive ? [activeId] : [];
}

/** @deprecated Usar ChartBarZoneChipButton */
export const ChartBarZoneRailButton = ChartBarZoneChipButton;
