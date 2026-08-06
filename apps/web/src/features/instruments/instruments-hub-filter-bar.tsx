/**
 * Barra de filtros rápidos del hub Instrumentos + menú (…) de favoritos.
 * Estética alineada con ListCarouselMenu (Trading → Listas).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';
import type { InstrumentListSummaryDto } from '@bolsa/shared';
import { isEstudioListNameCollision } from '@bolsa/shared';
import { checkboxClassName } from '@/components/ui/dialog';
import { OpaqueMenuLabel, OpaqueMenuPanel } from '@/components/ui/opaque-menu-panel';
import { cn } from '@/lib/utils';
import type { InstrumentsHubScopeFilter } from '@/features/instruments/instruments-hub-model';

export type InstrumentsHubBuiltinFilterId = 'all' | 'estudio' | 'portfolio';

export const INSTRUMENTS_HUB_BUILTIN_FILTERS: Array<{
  id: InstrumentsHubBuiltinFilterId;
  label: string;
}> = [
  { id: 'all', label: 'Todos' },
  { id: 'estudio', label: 'Estudio' },
  { id: 'portfolio', label: 'Cartera' },
];

export const DEFAULT_INSTRUMENTS_HUB_FAVORITE_BUILTIN_FILTERS: InstrumentsHubBuiltinFilterId[] = [
  'all',
  'estudio',
  'portfolio',
];

export function normalizeFavoriteBuiltinFilters(
  value: unknown,
): InstrumentsHubBuiltinFilterId[] {
  const allowed = new Set(INSTRUMENTS_HUB_BUILTIN_FILTERS.map((f) => f.id));
  if (!Array.isArray(value)) return [...DEFAULT_INSTRUMENTS_HUB_FAVORITE_BUILTIN_FILTERS];
  const next = value.filter(
    (id): id is InstrumentsHubBuiltinFilterId =>
      typeof id === 'string' && allowed.has(id as InstrumentsHubBuiltinFilterId),
  );
  return next.length > 0 ? next : [...DEFAULT_INSTRUMENTS_HUB_FAVORITE_BUILTIN_FILTERS];
}

export function normalizeFavoriteListIds(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((id): id is string => typeof id === 'string' && id.trim().length > 0);
}

export function toggleFavoriteBuiltinFilter(
  current: InstrumentsHubBuiltinFilterId[],
  id: InstrumentsHubBuiltinFilterId,
): InstrumentsHubBuiltinFilterId[] {
  const set = new Set(current);
  if (set.has(id)) {
    // No dejar la barra sin ningún filtro built-in si tampoco hay listas.
    set.delete(id);
  } else {
    set.add(id);
  }
  // Conservar orden canónico.
  return INSTRUMENTS_HUB_BUILTIN_FILTERS.map((f) => f.id).filter((x) => set.has(x));
}

export function toggleFavoriteListId(current: string[], listId: string): string[] {
  const set = new Set(current);
  if (set.has(listId)) set.delete(listId);
  else set.add(listId);
  return [...set];
}

function FilterChip({
  label,
  title,
  active,
  badge,
  onClick,
}: {
  label: string;
  title?: string;
  active: boolean;
  badge?: string | number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title ?? label}
      onClick={onClick}
      className={cn(
        'inline-flex max-w-[9rem] items-center rounded-md border px-2 py-1 text-[11px] font-medium transition-colors',
        active
          ? 'border-primary/50 bg-primary/10 text-primary'
          : 'border-border text-muted-foreground hover:bg-accent hover:text-foreground',
      )}
    >
      <span className="truncate">{label}</span>
      {badge != null && badge !== '' ? (
        <span className="ml-1 tabular-nums opacity-70">{badge}</span>
      ) : null}
    </button>
  );
}

export function InstrumentsHubFilterBar({
  scopeFilter,
  scopeListId,
  favoriteBuiltinFilters,
  favoriteListIds,
  apiLists,
  estudioCount,
  onSelectBuiltin,
  onSelectList,
  onToggleBuiltinFavorite,
  onToggleListFavorite,
}: {
  scopeFilter: InstrumentsHubScopeFilter;
  scopeListId: string | null;
  favoriteBuiltinFilters: InstrumentsHubBuiltinFilterId[];
  favoriteListIds: string[];
  apiLists: InstrumentListSummaryDto[];
  estudioCount: number;
  onSelectBuiltin: (id: InstrumentsHubBuiltinFilterId) => void;
  onSelectList: (listId: string) => void;
  onToggleBuiltinFavorite: (id: InstrumentsHubBuiltinFilterId) => void;
  onToggleListFavorite: (listId: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const favoriteBuiltinSet = useMemo(
    () => new Set(favoriteBuiltinFilters),
    [favoriteBuiltinFilters],
  );
  const favoriteListSet = useMemo(() => new Set(favoriteListIds), [favoriteListIds]);

  /** Listas API elegibles: oculta homónimas de la virtual Estudio (evita chip duplicado). */
  const selectableApiLists = useMemo(
    () => apiLists.filter((l) => !isEstudioListNameCollision(l.name)),
    [apiLists],
  );

  const visibleBuiltins = useMemo(
    () => INSTRUMENTS_HUB_BUILTIN_FILTERS.filter((f) => favoriteBuiltinSet.has(f.id)),
    [favoriteBuiltinSet],
  );

  const visibleLists = useMemo(() => {
    const byId = new Map(selectableApiLists.map((l) => [l.id, l]));
    const pinned = favoriteListIds
      .map((id) => byId.get(id))
      .filter((l): l is InstrumentListSummaryDto => Boolean(l));
    // Si el filtro activo es una lista no favorita, mostrarla igual (transient).
    if (
      scopeFilter === 'list' &&
      scopeListId &&
      !favoriteListSet.has(scopeListId) &&
      byId.has(scopeListId)
    ) {
      return [...pinned, byId.get(scopeListId)!];
    }
    return pinned;
  }, [selectableApiLists, favoriteListIds, favoriteListSet, scopeFilter, scopeListId]);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  return (
    <div
      className="flex flex-wrap items-center gap-1"
      role="group"
      aria-label="Filtros rápidos"
    >
      {visibleBuiltins.map((chip) => (
        <FilterChip
          key={chip.id}
          label={chip.label}
          title={
            chip.id === 'estudio'
              ? `Filtrar lista Estudio (${estudioCount})`
              : chip.id === 'portfolio'
                ? 'Solo posiciones abiertas (cuenta activa)'
                : 'Catálogo completo'
          }
          active={scopeFilter === chip.id}
          badge={chip.id === 'estudio' && estudioCount > 0 ? estudioCount : undefined}
          onClick={() => onSelectBuiltin(chip.id)}
        />
      ))}
      {visibleLists.map((list) => (
        <FilterChip
          key={list.id}
          label={list.name}
          title={`Filtrar lista ${list.name}`}
          active={scopeFilter === 'list' && scopeListId === list.id}
          onClick={() => onSelectList(list.id)}
        />
      ))}

      <div ref={menuRef} className="relative shrink-0 border-l border-border/60 pl-0.5">
        <button
          type="button"
          title="Configurar filtros favoritos"
          aria-label="Configurar filtros favoritos"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
        {menuOpen ? (
          <OpaqueMenuPanel align="left" className="min-w-[200px] p-1">
            <OpaqueMenuLabel>Filtros</OpaqueMenuLabel>
            <div className="pb-1">
              {INSTRUMENTS_HUB_BUILTIN_FILTERS.map((f) => (
                <label
                  key={f.id}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-accent/50"
                >
                  <input
                    type="checkbox"
                    className={checkboxClassName}
                    checked={favoriteBuiltinSet.has(f.id)}
                    onChange={() => onToggleBuiltinFavorite(f.id)}
                  />
                  <span className="truncate">{f.label}</span>
                </label>
              ))}
            </div>
            <OpaqueMenuLabel>Listas</OpaqueMenuLabel>
            <div className="scroll-area max-h-48 overflow-auto">
              {selectableApiLists.length === 0 ? (
                <p className="px-2 py-1.5 text-[10px] text-muted-foreground">Sin listas API</p>
              ) : (
                selectableApiLists.map((list) => (
                  <label
                    key={list.id}
                    className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-accent/50"
                  >
                    <input
                      type="checkbox"
                      className={checkboxClassName}
                      checked={favoriteListSet.has(list.id)}
                      onChange={() => onToggleListFavorite(list.id)}
                    />
                    <span className="truncate">{list.name}</span>
                  </label>
                ))
              )}
            </div>
          </OpaqueMenuPanel>
        ) : null}
      </div>
    </div>
  );
}
