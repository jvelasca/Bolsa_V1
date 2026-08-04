import { useEffect, useMemo, useState, useCallback } from 'react';

import { Search } from 'lucide-react';

import { useQuery, useQueryClient } from '@tanstack/react-query';

import { useNavigate } from 'react-router-dom';

import type { ExternalInstrumentSearchHitDto } from '@bolsa/shared';
import {
  isVirtualListId,
  looksLikeIsinQuery,
  normalizeIsin,
  VIRTUAL_LIST_LABELS,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
} from '@bolsa/shared';

import { api, ApiError } from '@/lib/api';

import { ensureChartRoute } from '@/components/layout/chart-tab-bar';
import { requestChartReflow } from '@/features/charts/chart-utils';
import {
  buildVirtualListSummaries,
  pendingOrderToListItem,
  positionToListItem,
  resolveVirtualListId,
  visualizationEntryToListItem,
} from '@/lib/default-lists';
import {
  listConfigForSelection,
  reconcileCarouselListIds,
  resolveSelectedListId,
} from '@/lib/list-sync';
import {
  clearManualListSelectionIfChartChanged,
  getManualListSelection,
  setManualListSelection,
} from '@/lib/list-selection-guard';
import { sortExternalSearchHits, rankCatalogInstrument } from '@/lib/search-ranking';
import { instrumentMatchesSearchQuery } from '@bolsa/shared';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { sortInstrumentList } from '@/lib/list-utils';

import { useWorkspaceStore } from '@/stores/workspace-store';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useVisualizationStore } from '@/stores/visualization-store';

import { ListItemAccordion } from '@/features/trading/lists-tab/list-item-accordion';
import { ListColumnHeader } from '@/features/trading/lists-tab/list-column-header';
import { ListColumnLayoutProvider, useListColumnLayoutContext } from '@/features/trading/lists-tab/list-column-layout-context';
import { PendingOrderListItem } from '@/features/trading/lists-tab/pending-order-list-item';
import { ListCarousel } from '@/features/trading/lists-tab/list-carousel';
import { useListInstrumentKeyboardNav } from '@/features/trading/lists-tab/use-list-instrument-keyboard-nav';

export function ListValuesPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [importingYahoo, setImportingYahoo] = useState<string | null>(null);

  const focusInstrumentFromList = useWorkspaceStore((s) => s.focusInstrumentFromList);
  const listConfig = useWorkspaceStore((s) => s.workspace.list);
  const updateListConfig = useWorkspaceStore((s) => s.updateListConfig);
  const save = useWorkspaceStore((s) => s.save);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const { pendingOrders } = usePendingOrders();
  const visualizationEntries = useVisualizationStore((s) => s.entries);
  const addToVisualization = useVisualizationStore((s) => s.addInstrument);
  const removeFromVisualization = useVisualizationStore((s) => s.removeInstrument);
  const [selectedInstrumentIds, setSelectedInstrumentIds] = useState<Set<string>>(
    () => new Set(),
  );

  const activeInstrumentId = charts.find((tab) => tab.id === activeChartId)?.instrumentId;
  const chartListContext = useWorkspaceStore((s) => s.workspace.chartListContext);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 280);
    return () => window.clearTimeout(timer);
  }, [query]);

  const accountScope = useActiveAccountQueryKey();

  const listsQuery = useQuery({ queryKey: ['lists'], queryFn: api.getLists });
  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  const remoteSearchQuery = useQuery({
    queryKey: ['instrument-search', debouncedQuery],
    queryFn: () => api.searchInstruments(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  });

  const apiLists = listsQuery.data?.data ?? [];
  const positions = portfolioQuery.data?.data.positions ?? [];
  const pendingBuyOrders = useMemo(
    () => pendingOrders.filter((order) => order.side === 'buy'),
    [pendingOrders],
  );

  const virtualLists = useMemo(
    () =>
      buildVirtualListSummaries(
        positions.length,
        pendingBuyOrders.length,
        visualizationEntries.length,
      ),
    [positions.length, pendingBuyOrders.length, visualizationEntries.length],
  );

  const selectedListId = useMemo(
    () => resolveSelectedListId(listConfig.apiListId, apiLists),
    [listConfig.apiListId, apiLists],
  );
  const activeVirtual = resolveVirtualListId(selectedListId);

  useEffect(() => {
    setSelectedInstrumentIds(new Set());
  }, [selectedListId]);

  // Full catalog with meta is expensive; skip while browsing a normal list (quotes cover the table).
  const needsFullCatalog =
    debouncedQuery.length >= 2 ||
    activeVirtual === VIRTUAL_LIST_PORTFOLIO ||
    activeVirtual === VIRTUAL_LIST_PENDING_ORDERS ||
    activeVirtual === VIRTUAL_LIST_VISUALIZATION;

  const allInstrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
    enabled: needsFullCatalog,
    staleTime: 60_000,
  });
  const allInstruments = allInstrumentsQuery.data?.data ?? [];

  useEffect(() => {
    clearManualListSelectionIfChartChanged(activeChartId);
  }, [activeChartId]);

  useEffect(() => {
    if (!chartListContext || listsQuery.isLoading) return;
    const targetId = chartListContext.listId;
    const manualId = getManualListSelection();
    if (manualId != null && manualId !== targetId) {
      return;
    }
    if (selectedListId === targetId) return;
    updateListConfig(listConfigForSelection(targetId, apiLists));
  }, [activeChartId, chartListContext, listsQuery.isLoading, selectedListId, apiLists, updateListConfig]);

  useEffect(() => {
    if (listsQuery.isLoading || !listsQuery.isSuccess) return;
    const storedId = listConfig.apiListId;
    if (!storedId || isVirtualListId(storedId)) return;
    if (apiLists.some((list) => list.id === storedId)) return;

    const carouselListIds = reconcileCarouselListIds(
      listConfig.carouselListIds,
      listConfig.carouselPinnedListNames,
      apiLists,
    );
    const carouselPinnedListNames = carouselListIds
      .map((id) => apiLists.find((list) => list.id === id)?.name)
      .filter((name): name is string => Boolean(name));
    updateListConfig({
      ...listConfigForSelection(selectedListId, apiLists),
      carouselListIds,
      carouselPinnedListNames,
    });
  }, [
    apiLists,
    listConfig.apiListId,
    listConfig.carouselListIds,
    listConfig.carouselPinnedListNames,
    listsQuery.isLoading,
    listsQuery.isSuccess,
    selectedListId,
    updateListConfig,
  ]);

  function isListSourceRow(instrumentId: string) {
    return (
      activeInstrumentId === instrumentId &&
      chartListContext?.instrumentId === instrumentId &&
      chartListContext.listId === selectedListId
    );
  }

  const quotesQuery = useQuery({
    queryKey: ['list-quotes', selectedListId],
    queryFn: () => api.getListQuotes(selectedListId!),
    enabled: Boolean(selectedListId) && !activeVirtual,
    staleTime: 15_000,
  });

  const visualizationInstrumentIds = useMemo(
    () => visualizationEntries.map((entry) => entry.instrumentId),
    [visualizationEntries],
  );

  const visualizationQuotesQuery = useQuery({
    queryKey: ['visualization-quotes', visualizationInstrumentIds],
    queryFn: () => api.getInstrumentQuotes(visualizationInstrumentIds),
    enabled:
      activeVirtual === VIRTUAL_LIST_VISUALIZATION && visualizationInstrumentIds.length > 0,
    staleTime: 15_000,
  });

  const visualizationQuotesById = useMemo(() => {
    const map = new Map<string, (typeof allInstruments)[number]>();
    for (const item of visualizationQuotesQuery.data?.data ?? []) {
      map.set(item.id, item);
    }
    return map;
  }, [visualizationQuotesQuery.data]);

  const listInstruments = activeVirtual ? [] : (quotesQuery.data?.data ?? []);

  const visualizationListItems = useMemo(
    () =>
      visualizationEntries.map((entry) => {
        const quoted = visualizationQuotesById.get(entry.instrumentId);
        if (quoted) return quoted;
        return visualizationEntryToListItem(entry, allInstruments);
      }),
    [visualizationEntries, visualizationQuotesById, allInstruments],
  );

  const portfolioListItems = useMemo(
    () => positions.map((pos) => positionToListItem(pos, allInstruments)),
    [positions, allInstruments],
  );

  const selectableItems = useMemo(() => {
    if (activeVirtual === VIRTUAL_LIST_PENDING_ORDERS) return [];
    if (activeVirtual === VIRTUAL_LIST_VISUALIZATION) return visualizationListItems;
    if (activeVirtual === VIRTUAL_LIST_PORTFOLIO) return portfolioListItems;
    return listInstruments;
  }, [
    activeVirtual,
    visualizationListItems,
    portfolioListItems,
    listInstruments,
  ]);

  const selectableIds = useMemo(
    () => selectableItems.map((item) => item.id),
    [selectableItems],
  );

  const selectAllChecked =
    selectableIds.length > 0 && selectableIds.every((id) => selectedInstrumentIds.has(id));
  const selectAllIndeterminate =
    selectableIds.some((id) => selectedInstrumentIds.has(id)) && !selectAllChecked;
  const selectionEnabled = activeVirtual !== VIRTUAL_LIST_PENDING_ORDERS;

  function toggleSelectAll() {
    setSelectedInstrumentIds((prev) => {
      if (selectableIds.length === 0) return prev;
      if (selectableIds.every((id) => prev.has(id))) {
        return new Set();
      }
      return new Set(selectableIds);
    });
  }

  function toggleSelectOne(instrumentId: string) {
    setSelectedInstrumentIds((prev) => {
      const next = new Set(prev);
      if (next.has(instrumentId)) next.delete(instrumentId);
      else next.add(instrumentId);
      return next;
    });
  }

  function addSelectedToEstudio() {
    const byId = new Map(selectableItems.map((item) => [item.id, item]));
    let added = 0;
    for (const id of selectedInstrumentIds) {
      const item = byId.get(id);
      if (!item) continue;
      addToVisualization(item, { source: 'list' });
      added += 1;
    }
    if (added > 0) {
      updateListConfig({
        apiListId: VIRTUAL_LIST_VISUALIZATION,
        name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_VISUALIZATION],
        source: 'virtual',
      });
      setSelectedInstrumentIds(new Set());
    }
  }

  function removeSelectedFromEstudio() {
    for (const id of selectedInstrumentIds) {
      removeFromVisualization(id);
    }
    setSelectedInstrumentIds(new Set());
  }

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { catalog: [], external: [] };

    if (debouncedQuery.length >= 2 && remoteSearchQuery.data) {
      return {
        catalog: [...remoteSearchQuery.data.catalog].sort(
          (a, b) => rankCatalogInstrument(b, debouncedQuery) - rankCatalogInstrument(a, debouncedQuery),
        ),
        external: sortExternalSearchHits(remoteSearchQuery.data.external, debouncedQuery),
      };
    }

    return {
      catalog: allInstruments
        .filter((item) => instrumentMatchesSearchQuery(item, query))
        .slice(0, 8),
      external: [],
    };
  }, [allInstruments, debouncedQuery.length, query, remoteSearchQuery.data]);

  const focusInstrument = useCallback(
    (instrumentId: string, symbol: string) => {
      const listId = selectedListId ?? listConfig.apiListId ?? listConfig.id;
      focusInstrumentFromList(listId, instrumentId, symbol);
      ensureChartRoute(navigate);
      requestChartReflow();
    },
    [
      selectedListId,
      listConfig.apiListId,
      listConfig.id,
      focusInstrumentFromList,
      navigate,
    ],
  );

  function visualizeFromSearch(
    instrument: (typeof allInstruments)[number],
    options?: { searchQuery?: string; source?: 'search' | 'import' },
  ) {
    addToVisualization(instrument, options);
    updateListConfig({
      apiListId: VIRTUAL_LIST_VISUALIZATION,
      name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_VISUALIZATION],
      source: 'virtual',
    });
    focusInstrument(instrument.id, instrument.symbol);
    setQuery('');
  }

  async function handleExternalHit(hit: ExternalInstrumentSearchHitDto) {
    const searchIsin = looksLikeIsinQuery(query.trim()) ? normalizeIsin(query.trim()) : null;
    const isin = hit.isin?.trim() || searchIsin || undefined;

    const match = allInstruments.find(
      (item) => item.yahooSymbol.toUpperCase() === hit.yahooSymbol.toUpperCase(),
    );

    if (match) {
      if (isin && !match.isin) {
        try {
          await api.importInstrument({
            yahooSymbol: match.yahooSymbol,
            symbol: match.symbol,
            name: match.name,
            exchange: match.exchange,
            currency: match.currency || 'EUR',
            sync: false,
            isin,
          });
          await queryClient.invalidateQueries({ queryKey: ['instruments'] });
        } catch (error) {
          console.warn('No se pudo guardar el ISIN del activo', error);
        }
      }
      visualizeFromSearch(
        isin && !match.isin ? { ...match, isin } : match,
        { searchQuery: query.trim(), source: 'search' },
      );
      return;
    }

    setImportingYahoo(hit.yahooSymbol);
    try {
      const result = await api.importInstrument({
        yahooSymbol: hit.yahooSymbol,
        symbol: hit.symbol,
        name: hit.name,
        exchange: hit.exchange,
        currency: hit.currency || 'USD',
        sync: false,
        isin,
      });
      await queryClient.invalidateQueries({ queryKey: ['instruments'] });
      try {
        visualizeFromSearch(result.data, { searchQuery: hit.yahooSymbol, source: 'import' });
      } catch (vizError) {
        console.warn('No se pudo registrar la visualización del activo importado', vizError);
        focusInstrument(result.data.id, result.data.symbol);
        setQuery('');
      }
      void api.syncInstrument(result.data.id, 5).then(() => {
        void queryClient.invalidateQueries({ queryKey: ['instruments'] });
        void queryClient.invalidateQueries({ queryKey: ['ohlcv', result.data.id] });
        void queryClient.invalidateQueries({ queryKey: ['visualization-quotes'] });
        void queryClient.invalidateQueries({ queryKey: ['instrument-profile', result.data.id] });
      });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'No se pudo importar el activo';
      window.alert(`${hit.symbol} (${hit.exchange}): ${message}`);
    } finally {
      setImportingYahoo(null);
    }
  }

  function handleSearchSubmit(event: React.FormEvent) {
    event.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q) return;

    const searchableItems =
      activeVirtual === VIRTUAL_LIST_PORTFOLIO
        ? portfolioListItems
        : activeVirtual === VIRTUAL_LIST_PENDING_ORDERS
          ? pendingBuyOrders.map((o) => pendingOrderToListItem(o, allInstruments))
          : activeVirtual === VIRTUAL_LIST_VISUALIZATION
            ? visualizationListItems
            : listInstruments;

    const inList = searchableItems.find((item) => {
      const instrument = allInstruments.find((entry) => entry.id === item.id);
      return (
        item.symbol.toLowerCase() === q ||
        item.name.toLowerCase().includes(q) ||
        item.id === q ||
        (instrument ? instrumentMatchesSearchQuery(instrument, q) : false)
      );
    });
    if (inList) {
      visualizeFromSearch(inList, { searchQuery: q, source: 'search' });
      return;
    }

    const inCatalog =
      searchResults.catalog[0] ??
      allInstruments.find(
        (item) =>
          item.symbol.toLowerCase() === q ||
          instrumentMatchesSearchQuery(item, q),
      );
    if (inCatalog) {
      visualizeFromSearch(inCatalog, { searchQuery: q, source: 'search' });
      return;
    }

    const external = searchResults.external[0];
    if (external) {
      void handleExternalHit(external);
      return;
    }

    window.alert('No se encontró ningún activo con ese criterio.');
  }

  function selectList(listId: string) {
    setManualListSelection(listId, activeChartId);
    if (isVirtualListId(listId)) {
      updateListConfig({
        apiListId: listId,
        name: VIRTUAL_LIST_LABELS[listId],
        source: 'virtual',
      });
      save();
      return;
    }

    const selected = apiLists.find((list) => list.id === listId);
    if (!selected) return;

    updateListConfig({ apiListId: selected.id, name: selected.name, source: 'api' });
    save();
  }

  const showDropdown = query.trim().length > 0;
  const hasResults = searchResults.catalog.length > 0 || searchResults.external.length > 0;

  const isLoading =
    listsQuery.isLoading ||
    (activeVirtual === VIRTUAL_LIST_PORTFOLIO && portfolioQuery.isLoading) ||
    (!activeVirtual && quotesQuery.isLoading);

  const isError =
    (activeVirtual === VIRTUAL_LIST_PORTFOLIO && portfolioQuery.isError) ||
    (!activeVirtual && quotesQuery.isError);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <form onSubmit={handleSearchSubmit} className="shrink-0 border-b border-border p-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar activo (ticker, nombre o ISIN)…"
            className="w-full rounded border border-border bg-background py-1 pl-7 pr-2 text-xs outline-none ring-primary focus:ring-1"
          />
        </div>

        {showDropdown && (
          <div className="scroll-area mt-1 max-h-36 overflow-auto rounded border border-border bg-background text-xs">
            {remoteSearchQuery.isFetching && debouncedQuery.length >= 2 && (
              <p className="px-2 py-1 text-muted-foreground">Buscando en Yahoo…</p>
            )}
            {!hasResults && !remoteSearchQuery.isFetching && (
              <p className="px-2 py-1 text-muted-foreground">Sin resultados</p>
            )}
            {searchResults.catalog.map((item) => (
              <button
                key={item.id}
                type="button"
                className="flex w-full px-2 py-1 text-left hover:bg-accent"
                onClick={() => visualizeFromSearch(item, { searchQuery: query.trim(), source: 'search' })}
              >
                <span className="font-medium">{item.symbol}</span>
                <span className="ml-2 truncate text-muted-foreground">
                  {item.name}
                  {item.isin ? <span className="ml-1 opacity-70">· {item.isin}</span> : null}
                </span>
              </button>
            ))}
            {searchResults.external.length > 0 && (
              <p className="border-t border-border/60 px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                Yahoo
              </p>
            )}
            {searchResults.external.map((item) => (
              <button
                key={item.yahooSymbol}
                type="button"
                className="flex w-full flex-col px-2 py-1 text-left hover:bg-accent/70 sm:flex-row sm:items-center"
                disabled={importingYahoo === item.yahooSymbol}
                onClick={() => void handleExternalHit(item)}
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

      <div className="shrink-0 border-b border-border px-2 py-1.5">
        <ListCarousel
          virtualLists={virtualLists}
          apiLists={apiLists}
          apiListsReady={listsQuery.isSuccess}
          selectedId={selectedListId}
          onSelect={selectList}
        />
      </div>

      <ListColumnLayoutProvider listId={selectedListId}>
        <div className="scroll-area min-h-0 flex-1 overflow-auto">
          {isLoading && <p className="p-2 text-xs text-muted-foreground">Cargando…</p>}
          {isError && <p className="p-2 text-xs text-destructive">Error al cargar lista</p>}

          {activeVirtual !== VIRTUAL_LIST_PENDING_ORDERS &&
            !isLoading &&
            (portfolioListItems.length > 0 ||
              listInstruments.length > 0 ||
              visualizationListItems.length > 0) && (
              <ListColumnHeader
                selectAllChecked={selectionEnabled ? selectAllChecked : undefined}
                selectAllIndeterminate={selectionEnabled ? selectAllIndeterminate : undefined}
                onSelectAllToggle={selectionEnabled ? toggleSelectAll : undefined}
              />
            )}

        {selectionEnabled && selectedInstrumentIds.size > 0 && (
          <div className="flex shrink-0 items-center gap-2 border-b border-border bg-muted/30 px-2 py-1.5 text-[11px]">
            <span className="text-muted-foreground">
              {selectedInstrumentIds.size} seleccionado
              {selectedInstrumentIds.size === 1 ? '' : 's'}
            </span>
            {activeVirtual === VIRTUAL_LIST_VISUALIZATION ? (
              <button
                type="button"
                className="rounded border border-border px-2 py-0.5 font-medium text-foreground hover:bg-accent"
                onClick={removeSelectedFromEstudio}
              >
                Quitar de Estudio
              </button>
            ) : (
              <button
                type="button"
                className="rounded border border-primary/40 bg-primary/10 px-2 py-0.5 font-medium text-primary hover:bg-primary/15"
                onClick={addSelectedToEstudio}
              >
                A Estudio
              </button>
            )}
            <button
              type="button"
              className="ml-auto text-muted-foreground hover:text-foreground"
              onClick={() => setSelectedInstrumentIds(new Set())}
            >
              Limpiar
            </button>
          </div>
        )}

        {activeVirtual === VIRTUAL_LIST_PORTFOLIO && !isLoading && positions.length === 0 && (
          <p className="p-4 text-center text-xs text-muted-foreground">
            Sin posiciones en cartera — ejecuta una compra desde el diálogo de operación.
          </p>
        )}

        {activeVirtual === VIRTUAL_LIST_PENDING_ORDERS &&
          !isLoading &&
          pendingBuyOrders.length === 0 && (
            <p className="p-4 text-center text-xs text-muted-foreground">
              Sin compras pendientes — crea una orden limitada desde el diálogo de operación.
            </p>
          )}

        {activeVirtual === VIRTUAL_LIST_VISUALIZATION && !isLoading && visualizationListItems.length === 0 && (
          <p className="p-4 text-center text-xs text-muted-foreground">
            Busca un valor, ábrelo en el gráfico o selecciona filas de otra lista y pulsa «A
            Estudio». SEMI/AUTO exigen pertenencia a Estudio. Los miembros se guardan en el espacio
            de trabajo.
          </p>
        )}

        {activeVirtual === VIRTUAL_LIST_VISUALIZATION && !isLoading && visualizationListItems.length > 0 && (
          <SortedVisualizationList
            items={visualizationListItems}
            entries={visualizationEntries}
            activeInstrumentId={activeInstrumentId}
            isListSource={isListSourceRow}
            onOpenChart={focusInstrument}
            selectedIds={selectedInstrumentIds}
            onToggleSelect={toggleSelectOne}
          />
        )}

        {activeVirtual === VIRTUAL_LIST_PORTFOLIO && (
          <PortfolioKeyboardList
            items={portfolioListItems}
            activeInstrumentId={activeInstrumentId}
            isListSource={isListSourceRow}
            onOpenChart={focusInstrument}
            positions={positions}
            allInstruments={allInstruments}
            selectedIds={selectedInstrumentIds}
            onToggleSelect={toggleSelectOne}
          />
        )}

        {activeVirtual === VIRTUAL_LIST_PENDING_ORDERS && (
          <PendingOrdersKeyboardList
            orders={pendingBuyOrders}
            activeInstrumentId={activeInstrumentId}
            onOpenChart={focusInstrument}
          />
        )}

        {!activeVirtual && (
          <SortedApiList
            items={listInstruments}
            activeInstrumentId={activeInstrumentId}
            isListSource={isListSourceRow}
            onOpenChart={focusInstrument}
            selectedIds={selectedInstrumentIds}
            onToggleSelect={toggleSelectOne}
          />
        )}
        </div>
      </ListColumnLayoutProvider>
    </div>
  );
}

function SortedApiList({
  items,
  activeInstrumentId,
  isListSource,
  onOpenChart,
  selectedIds,
  onToggleSelect,
}: {
  items: import('@bolsa/shared').InstrumentWithMetaDto[];
  activeInstrumentId: string | undefined;
  isListSource: (instrumentId: string) => boolean;
  onOpenChart: (instrumentId: string, symbol: string) => void;
  selectedIds: Set<string>;
  onToggleSelect: (instrumentId: string) => void;
}) {
  const { sortState } = useListColumnLayoutContext();
  const sorted = useMemo(() => sortInstrumentList(items, sortState), [items, sortState]);
  useListInstrumentKeyboardNav(sorted, activeInstrumentId, onOpenChart);
  return (
    <>
      {sorted.map((item) => (
        <ListItemAccordion
          key={item.id}
          item={item}
          isChartActive={activeInstrumentId === item.id}
          isListSource={isListSource(item.id)}
          onOpenChart={() => onOpenChart(item.id, item.symbol)}
          selected={selectedIds.has(item.id)}
          onToggleSelect={() => onToggleSelect(item.id)}
        />
      ))}
    </>
  );
}

function SortedVisualizationList({
  items,
  entries,
  activeInstrumentId,
  isListSource,
  onOpenChart,
  selectedIds,
  onToggleSelect,
}: {
  items: import('@bolsa/shared').InstrumentWithMetaDto[];
  entries: ReturnType<typeof useVisualizationStore.getState>['entries'];
  activeInstrumentId: string | undefined;
  isListSource: (instrumentId: string) => boolean;
  onOpenChart: (instrumentId: string, symbol: string) => void;
  selectedIds: Set<string>;
  onToggleSelect: (instrumentId: string) => void;
}) {
  const { sortState } = useListColumnLayoutContext();
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const openIds = useMemo(
    () => new Set(charts.map((tab) => tab.instrumentId).filter(Boolean) as string[]),
    [charts],
  );
  const sorted = useMemo(() => sortInstrumentList(items, sortState), [items, sortState]);
  useListInstrumentKeyboardNav(sorted, activeInstrumentId, onOpenChart);
  return (
    <>
      {sorted.map((item) => {
        const entry = entries.find((e) => e.instrumentId === item.id);
        const open = openIds.has(item.id);
        const subtitle = entry
          ? `${open ? 'gráfico abierto' : 'en Estudio'} · visto ${entry.viewCount}× · ${new Date(entry.lastViewedAt).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
          : open
            ? 'gráfico abierto'
            : 'en Estudio';
        return (
          <ListItemAccordion
            key={item.id}
            item={item}
            subtitle={subtitle}
            isChartActive={activeInstrumentId === item.id}
            isListSource={isListSource(item.id)}
            onOpenChart={() => onOpenChart(item.id, item.symbol)}
            selected={selectedIds.has(item.id)}
            onToggleSelect={() => onToggleSelect(item.id)}
          />
        );
      })}
    </>
  );
}

function PortfolioKeyboardList({
  items,
  activeInstrumentId,
  isListSource,
  onOpenChart,
  positions,
  allInstruments,
  selectedIds,
  onToggleSelect,
}: {
  items: import('@bolsa/shared').InstrumentWithMetaDto[];
  activeInstrumentId: string | undefined;
  isListSource: (instrumentId: string) => boolean;
  onOpenChart: (instrumentId: string, symbol: string) => void;
  positions: Array<{
    id: string;
    quantity: number;
    avgCost: number;
    unrealizedPnl?: number | null;
    unrealizedPnlPct?: number | null;
  }>;
  allInstruments: import('@bolsa/shared').InstrumentWithMetaDto[];
  selectedIds: Set<string>;
  onToggleSelect: (instrumentId: string) => void;
}) {
  useListInstrumentKeyboardNav(items, activeInstrumentId, onOpenChart, items.length > 0);
  if (items.length === 0) return null;
  return (
    <>
      {positions.map((pos) => {
        const item = positionToListItem(pos, allInstruments);
        const pnl =
          pos.unrealizedPnl != null
            ? `${formatPrice(pos.unrealizedPnl)}${
                pos.unrealizedPnlPct != null ? ` (${formatPct(pos.unrealizedPnlPct)})` : ''
              }`
            : null;
        const subtitle = `${pos.quantity} uds · coste ${formatPrice(pos.avgCost)}${
          pnl ? ` · P&L ${pnl}` : ''
        }`;
        return (
          <ListItemAccordion
            key={pos.id}
            item={item}
            subtitle={subtitle}
            isChartActive={activeInstrumentId === item.id}
            isListSource={isListSource(item.id)}
            onOpenChart={() => onOpenChart(item.id, item.symbol)}
            selected={selectedIds.has(item.id)}
            onToggleSelect={() => onToggleSelect(item.id)}
          />
        );
      })}
    </>
  );
}

function PendingOrdersKeyboardList({
  orders,
  activeInstrumentId,
  onOpenChart,
}: {
  orders: ReturnType<typeof usePendingOrders>['pendingOrders'];
  activeInstrumentId: string | undefined;
  onOpenChart: (instrumentId: string, symbol: string) => void;
}) {
  const navItems = useMemo(
    () =>
      orders.map((order) => ({
        id: order.instrumentId,
        symbol: order.symbol,
      })),
    [orders],
  );
  useListInstrumentKeyboardNav(navItems, activeInstrumentId, onOpenChart, navItems.length > 0);
  if (orders.length === 0) return null;
  return (
    <>
      {orders.map((order) => (
        <PendingOrderListItem
          key={order.id}
          order={order}
          isChartActive={activeInstrumentId === order.instrumentId}
          onOpenChart={() => onOpenChart(order.instrumentId, order.symbol)}
        />
      ))}
    </>
  );
}
