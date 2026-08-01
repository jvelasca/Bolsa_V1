/**
 * Picker compacto Universo: pestañas Valor / Lista + búsqueda solo catálogo BD.
 *
 * Modo Lista: miembros con resumen AT (Finalistas / AUTO) + chip FA (`FUND 91 · HIGH`);
 * clic abre pestaña Valor (`openInstrumentInValor` en la página).
 *
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 * @see backtest-list-member-status.ts
 * @see backtest-list-member-fa.ts
 */

import { instrumentMatchesSearchQuery, type InstrumentWithMetaDto } from '@bolsa/shared';
import { LayoutList, Search, Shapes } from 'lucide-react';
import { useMemo, useState } from 'react';

import { LIST_AUTO_MAX_INSTRUMENTS } from '@/features/backtests/backtest-list-auto';
import {
  listMemberStatusClass,
  type ListMemberBacktestStatus,
} from '@/features/backtests/backtest-list-member-status';
import {
  type ListMemberFaChipView,
} from '@/features/backtests/backtest-list-member-fa';
import { rankCatalogInstrument } from '@/lib/search-ranking';
import { cn } from '@/lib/utils';

export type BacktestUniverseMode = 'single' | 'list';

type ListOption = {
  id: string;
  name: string;
  itemCount: number;
};

export type BacktestListMember = {
  id: string;
  symbol: string;
  name?: string | null;
  status?: ListMemberBacktestStatus | null;
  fa?: ListMemberFaChipView | null;
};

type Props = {
  mode: BacktestUniverseMode;
  onModeChange: (mode: BacktestUniverseMode) => void;
  instruments: InstrumentWithMetaDto[];
  instrumentId: string;
  onInstrumentIdChange: (id: string) => void;
  lists: ListOption[];
  listId: string;
  onListIdChange: (id: string) => void;
  listInstrumentCount?: number;
  listsLoading?: boolean;
  /** Miembros de la lista activa (quotes + resumen). Clic → abrir en Valor. */
  listMembers?: BacktestListMember[];
  listMembersLoading?: boolean;
  listStatusLoading?: boolean;
  onOpenListMember?: (instrumentId: string) => void;
};

const SEARCH_RESULT_LIMIT = 40;

export function BacktestUniversePicker({
  mode,
  onModeChange,
  instruments,
  instrumentId,
  onInstrumentIdChange,
  lists,
  listId,
  onListIdChange,
  listInstrumentCount,
  listsLoading,
  listMembers = [],
  listMembersLoading,
  listStatusLoading,
  onOpenListMember,
}: Props) {
  const [query, setQuery] = useState('');
  const [listFilter, setListFilter] = useState('');

  const sortedInstruments = useMemo(
    () =>
      [...instruments].sort((a, b) =>
        a.symbol.localeCompare(b.symbol, 'es', { sensitivity: 'base' }),
      ),
    [instruments],
  );

  const selectedInstrument = useMemo(
    () => sortedInstruments.find((item) => item.id === instrumentId) ?? null,
    [sortedInstruments, instrumentId],
  );

  const searchHits = useMemo(() => {
    const q = query.trim();
    if (!q) return [];
    return sortedInstruments
      .filter((item) => instrumentMatchesSearchQuery(item, q))
      .sort((a, b) => rankCatalogInstrument(b, q) - rankCatalogInstrument(a, q))
      .slice(0, SEARCH_RESULT_LIMIT);
  }, [sortedInstruments, query]);

  const filteredMembers = useMemo(() => {
    const q = listFilter.trim().toLowerCase();
    const sorted = [...listMembers].sort((a, b) => {
      const scoreDiff = (b.status?.rankScore ?? -1) - (a.status?.rankScore ?? -1);
      if (scoreDiff !== 0) return scoreDiff;
      return a.symbol.localeCompare(b.symbol, 'es', { sensitivity: 'base' });
    });
    if (!q) return sorted;
    return sorted.filter(
      (m) =>
        m.symbol.toLowerCase().includes(q) ||
        (m.name ?? '').toLowerCase().includes(q) ||
        (m.status?.primary ?? '').toLowerCase().includes(q) ||
        (m.fa?.primary ?? '').toLowerCase().includes(q) ||
        (m.fa?.secondary ?? '').toLowerCase().includes(q),
    );
  }, [listMembers, listFilter]);

  const showDropdown = mode === 'single' && query.trim().length > 0;

  const statusCounts = useMemo(() => {
    let withTop = 0;
    let pending = 0;
    for (const m of listMembers) {
      if ((m.status?.rankScore ?? 0) > 0) withTop += 1;
      else pending += 1;
    }
    return { withTop, pending, total: listMembers.length };
  }, [listMembers]);

  function pickInstrument(item: InstrumentWithMetaDto) {
    onInstrumentIdChange(item.id);
    setQuery('');
  }

  return (
    <div className="space-y-2">
      <div
        className="grid grid-cols-2 gap-1 rounded-md border border-border bg-muted/20 p-0.5"
        role="tablist"
        aria-label="Universo"
      >
        {(
          [
            { id: 'single' as const, label: 'Valor', icon: Shapes },
            { id: 'list' as const, label: 'Lista valores', icon: LayoutList },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mode === id}
            className={cn(
              'inline-flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] font-medium transition-colors',
              mode === id
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => onModeChange(id)}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            {label}
          </button>
        ))}
      </div>

      {mode === 'single' ? (
        <div className="space-y-1.5">
          <p className="text-[10px] leading-snug text-muted-foreground">
            Busca solo en valores ya importados en tu BD (nombre o ticker, parcial o completo). No
            consulta Yahoo.
          </p>

          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar ticker o nombre…"
              className="w-full rounded-md border border-border bg-background py-1.5 pl-7 pr-2 text-xs outline-none ring-primary focus:ring-1"
              autoComplete="off"
              aria-autocomplete="list"
              aria-expanded={showDropdown}
            />
          </div>

          {showDropdown && (
            <div
              className="scroll-area max-h-36 overflow-auto rounded border border-border bg-background text-xs"
              role="listbox"
              aria-label="Coincidencias en BD"
            >
              {searchHits.length === 0 ? (
                <p className="px-2 py-1.5 text-muted-foreground">
                  Sin resultados en BD. Impórtalo desde Instrumentos o la watchlist.
                </p>
              ) : (
                searchHits.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="option"
                    aria-selected={item.id === instrumentId}
                    className={cn(
                      'flex w-full px-2 py-1 text-left hover:bg-accent',
                      item.id === instrumentId && 'bg-accent/60',
                    )}
                    onClick={() => pickInstrument(item)}
                  >
                    <span className="font-medium">{item.symbol}</span>
                    <span className="ml-2 truncate text-muted-foreground">
                      {item.name}
                      {item.isin ? <span className="ml-1 opacity-70">· {item.isin}</span> : null}
                    </span>
                  </button>
                ))
              )}
              {searchHits.length >= SEARCH_RESULT_LIMIT && (
                <p className="border-t border-border/60 px-2 py-1 text-[10px] text-muted-foreground">
                  Mostrando {SEARCH_RESULT_LIMIT} primeros · afina el texto
                </p>
              )}
            </div>
          )}

          {selectedInstrument && !showDropdown && (
            <p className="rounded border border-border/70 bg-muted/20 px-2 py-1 text-[11px]">
              <span className="font-medium text-foreground">{selectedInstrument.symbol}</span>
              <span className="ml-1.5 text-muted-foreground">{selectedInstrument.name}</span>
            </p>
          )}

          <label className="block text-[11px] font-medium text-foreground">
            Catálogo (A–Z)
            <select
              value={instrumentId}
              onChange={(e) => onInstrumentIdChange(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
            >
              <option value="">Selecciona…</option>
              {sortedInstruments.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.symbol} — {inst.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <div className="space-y-1.5">
          <label className="block text-[11px] font-medium text-foreground">
            Lista
            <select
              value={listId}
              onChange={(e) => {
                onListIdChange(e.target.value);
                setListFilter('');
              }}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
            >
              <option value="">Selecciona una lista…</option>
              {lists.map((list) => (
                <option key={list.id} value={list.id}>
                  {list.name} ({list.itemCount})
                </option>
              ))}
            </select>
          </label>
          {listInstrumentCount != null && (
            <p className="text-[10px] font-normal text-muted-foreground">
              {listInstrumentCount} valor(es)
              {listInstrumentCount > LIST_AUTO_MAX_INSTRUMENTS
                ? ` · Play pedirá confirmación y usará los primeros ${LIST_AUTO_MAX_INSTRUMENTS}`
                : ''}
              {statusCounts.total > 0
                ? ` · ${statusCounts.withTop} con Finalistas · ${statusCounts.pending} pendientes`
                : ''}
              {onOpenListMember ? ' · clic para abrir en Valor' : ''}
            </p>
          )}
          {listsLoading && (
            <p className="text-[10px] font-normal text-muted-foreground">Cargando listas…</p>
          )}

          {listId ? (
            <div className="space-y-1">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={listFilter}
                  onChange={(e) => setListFilter(e.target.value)}
                  placeholder="Filtrar ticker, nombre o estado…"
                  className="w-full rounded-md border border-border bg-background py-1 pl-7 pr-2 text-[11px] outline-none ring-primary focus:ring-1"
                  autoComplete="off"
                />
              </div>
              <div
                className="scroll-area max-h-56 overflow-auto rounded border border-border bg-background text-[11px]"
                role="listbox"
                aria-label="Valores de la lista con estado"
              >
                {listMembersLoading && listMembers.length === 0 ? (
                  <p className="px-2 py-1.5 text-muted-foreground">Cargando valores…</p>
                ) : filteredMembers.length === 0 ? (
                  <p className="px-2 py-1.5 text-muted-foreground">
                    {listFilter.trim()
                      ? 'Sin coincidencias en esta lista.'
                      : 'Esta lista no tiene valores.'}
                  </p>
                ) : (
                  filteredMembers.map((m) => {
                    const selected = m.id === instrumentId;
                    const status = m.status;
                    const fa = m.fa;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        title="Abrir en pestaña Valor"
                        disabled={!onOpenListMember}
                        className={cn(
                          'flex w-full flex-col gap-0.5 border-b border-border/40 px-2 py-1.5 text-left last:border-0',
                          onOpenListMember && 'hover:bg-accent/70',
                          selected && 'bg-accent/70',
                          !onOpenListMember && 'cursor-default',
                        )}
                        onClick={() => onOpenListMember?.(m.id)}
                      >
                        <span className="flex min-w-0 items-baseline gap-2">
                          <span className="shrink-0 font-semibold tracking-wide text-foreground">
                            {m.symbol}
                          </span>
                          {m.name ? (
                            <span className="min-w-0 truncate text-muted-foreground">{m.name}</span>
                          ) : null}
                          {fa ? (
                            <span
                              className={cn(
                                'ml-auto shrink-0 text-[10px] font-medium tabular-nums',
                                fa.toneClass,
                              )}
                              title={fa.secondary}
                            >
                              {fa.primary}
                              <span className="font-normal text-muted-foreground">
                                {' '}
                                · {fa.secondary}
                              </span>
                            </span>
                          ) : null}
                        </span>
                        {status ? (
                          <span
                            className={cn(
                              'min-w-0 truncate text-[10px] leading-snug',
                              listMemberStatusClass(status.tone),
                            )}
                          >
                            {status.primary}
                            {status.secondary ? (
                              <span className="text-muted-foreground"> · {status.secondary}</span>
                            ) : null}
                          </span>
                        ) : listStatusLoading ? (
                          <span className="text-[10px] text-muted-foreground">Cargando estado…</span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">Sin Finalistas</span>
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
