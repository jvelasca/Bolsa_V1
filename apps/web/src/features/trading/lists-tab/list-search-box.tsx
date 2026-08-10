import { Search } from 'lucide-react';

import type { ExternalInstrumentSearchHitDto, InstrumentWithMetaDto } from '@bolsa/shared';

/**
 * Caja de búsqueda del panel Valores: input + dropdown de resultados (catálogo / Yahoo).
 *
 * Presentacional (Diseño B): la lógica de búsqueda (debounce, queries, importación) y sus
 * acciones viven en el orquestador `ListValuesPanel`, que inyecta aquí los datos y callbacks.
 * Se traslada fielmente el bloque `<form>` original; no se mueve lógica de ciclo ni de estado.
 */
export interface ListSearchBoxResults {
  catalog: InstrumentWithMetaDto[];
  external: ExternalInstrumentSearchHitDto[];
}

export function ListSearchBox({
  query,
  debouncedQuery,
  onQueryChange,
  remoteSearchFetching,
  results,
  importingYahoo,
  showDropdown,
  hasResults,
  onSubmit,
  onSelectCatalog,
  onSelectExternal,
}: {
  query: string;
  /** Valor debounced (desfasado al escribir) para el aviso de búsqueda remota. */
  debouncedQuery: string;
  onQueryChange: (next: string) => void;
  /** `true` mientras la búsqueda remota (Yahoo) está en marcha. */
  remoteSearchFetching: boolean;
  results: ListSearchBoxResults;
  importingYahoo: string | null;
  showDropdown: boolean;
  hasResults: boolean;
  onSubmit: (event: React.FormEvent) => void;
  onSelectCatalog: (item: InstrumentWithMetaDto) => void;
  onSelectExternal: (hit: ExternalInstrumentSearchHitDto) => void;
}) {
  return (
    <form onSubmit={onSubmit} className="shrink-0 border-b border-border p-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Buscar activo (ticker, nombre o ISIN)…"
          className="w-full rounded border border-border bg-background py-1 pl-7 pr-2 text-xs outline-none ring-primary focus:ring-1"
        />
      </div>

      {showDropdown && (
        <div className="scroll-area mt-1 max-h-36 overflow-auto rounded border border-border bg-background text-xs">
          {remoteSearchFetching && debouncedQuery.length >= 2 && (
            <p className="px-2 py-1 text-muted-foreground">Buscando en Yahoo…</p>
          )}
          {!hasResults && !remoteSearchFetching && (
            <p className="px-2 py-1 text-muted-foreground">Sin resultados</p>
          )}
          {results.catalog.map((item) => (
            <button
              key={item.id}
              type="button"
              className="flex w-full px-2 py-1 text-left hover:bg-accent"
              onClick={() => onSelectCatalog(item)}
            >
              <span className="font-medium">{item.symbol}</span>
              <span className="ml-2 truncate text-muted-foreground">
                {item.name}
                {item.isin ? <span className="ml-1 opacity-70">· {item.isin}</span> : null}
              </span>
            </button>
          ))}
          {results.external.length > 0 && (
            <p className="border-t border-border/60 px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
              Yahoo
            </p>
          )}
          {results.external.map((item) => (
            <button
              key={item.yahooSymbol}
              type="button"
              className="flex w-full flex-col px-2 py-1 text-left hover:bg-accent/70 sm:flex-row sm:items-center"
              disabled={importingYahoo === item.yahooSymbol}
              onClick={() => onSelectExternal(item)}
            >
              <span className="font-medium">
                {item.symbol}
                <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">
                  {item.yahooSymbol}
                </span>
              </span>
              <span className="truncate text-muted-foreground sm:ml-2">
                {item.name}
                <span className="ml-1 opacity-60">
                  · {item.exchange} · {item.currency}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
