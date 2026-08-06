/**
 * Panel Valores (watchlist): carrusel de listas, filas, selección masiva.
 *
 * - **Visualizados**: espejo de pestañas; Por IO; columnas recomendación; Quitar cierra tabs.
 * - **Estudio**: banner Supervisión + Actualizar / Redescubrir.
 * - Foco buscar/pestaña: Cartera → Estudio → resto + scroll bajo cabecera sticky.
 *
 * @see docs/engineering/visualizados-list-ux-2026-08-06.md
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 * @see docs/adr/024-estudio-supervision-universe.md
 */

import { useEffect, useMemo, useState, useCallback, useRef } from 'react';

import {
  AlertTriangle,
  ArrowDownWideNarrow,
  Eraser,
  LineChart,
  ListMinus,
  ListPlus,
  RefreshCw,
  Search,
} from 'lucide-react';

import { useQuery, useQueryClient } from '@tanstack/react-query';

import { useNavigate } from 'react-router-dom';

import type { ExternalInstrumentSearchHitDto, PositionDto } from '@bolsa/shared';
import {
  ESTUDIO_LIST_ID,
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
import { resolvePreferredListIdForInstrument } from '@/lib/chart-list-membership';
import { scrollListInstrumentToTop } from '@/lib/scroll-list-instrument-into-view';
import { sortExternalSearchHits, rankCatalogInstrument } from '@/lib/search-ranking';
import { instrumentMatchesSearchQuery } from '@bolsa/shared';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { sortInstrumentList } from '@/lib/list-utils';
import { applyInstrumentSelection } from '@/features/trading/lists-tab/list-selection';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useVisualizationStore } from '@/stores/visualization-store';
import { useEstudioMembershipStore } from '@/stores/estudio-membership-store';

import { ListItemAccordion } from '@/features/trading/lists-tab/list-item-accordion';
import { ListColumnHeader } from '@/features/trading/lists-tab/list-column-header';
import { ListColumnLayoutProvider, useListColumnLayoutContext } from '@/features/trading/lists-tab/list-column-layout-context';
import {
  ListRecommendationScoresProvider,
  useListRecommendationScoresMap,
} from '@/features/trading/lists-tab/list-recommendation-scores-context';
import { sortInstrumentListWithRecommendation } from '@/lib/list-sort-with-recommendation';
import { PendingOrderListItem } from '@/features/trading/lists-tab/pending-order-list-item';
import { ListCarousel } from '@/features/trading/lists-tab/list-carousel';
import { useListInstrumentKeyboardNav } from '@/features/trading/lists-tab/use-list-instrument-keyboard-nav';
import {
  EstudioListSupervisionBanner,
  type EstudioBannerProgress,
} from '@/features/trading/estudio-supervision-panel';
import {
  emitEstudioLaneTick,
} from '@/features/trading/estudio-supervision';
import {
  emitEstudioProcessRunning,
  laneFromListAutoMode,
} from '@/features/trading/estudio-process-status';
import { touchEstudioLaneStamps } from '@/features/trading/estudio-lane-stamps';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';

export function ListValuesPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [importingYahoo, setImportingYahoo] = useState<string | null>(null);
  const [sortingByIo, setSortingByIo] = useState(false);
  const listScrollRef = useRef<HTMLDivElement>(null);

  const focusInstrumentFromList = useWorkspaceStore((s) => s.focusInstrumentFromList);
  const focusInstrumentsFromList = useWorkspaceStore((s) => s.focusInstrumentsFromList);
  const chartListMembership = useWorkspaceStore((s) => s.chartListMembership);
  const listConfig = useWorkspaceStore((s) => s.workspace.list);
  const updateListConfig = useWorkspaceStore((s) => s.updateListConfig);
  const save = useWorkspaceStore((s) => s.save);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const { pendingOrders } = usePendingOrders();
  const visualizationEntries = useVisualizationStore((s) => s.entries);
  const estudioMemberIds = useEstudioMembershipStore((s) => s.members);
  const [selectedInstrumentIds, setSelectedInstrumentIds] = useState<Set<string>>(
    () => new Set(),
  );
  const selectionAnchorIndexRef = useRef<number | null>(null);

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

  /** Visualizados = pestañas abiertas (SoT charts), no el store/dump legacy. */
  const openChartInstrumentIds = useMemo(() => {
    const ids: string[] = [];
    const seen = new Set<string>();
    for (const tab of charts) {
      if (!tab.instrumentId || seen.has(tab.instrumentId)) continue;
      seen.add(tab.instrumentId);
      ids.push(tab.instrumentId);
    }
    return ids;
  }, [charts]);

  const virtualLists = useMemo(
    () =>
      buildVirtualListSummaries(
        positions.length,
        pendingBuyOrders.length,
        openChartInstrumentIds.length,
      ),
    [positions.length, pendingBuyOrders.length, openChartInstrumentIds.length],
  );

  const selectedListId = useMemo(
    () => resolveSelectedListId(listConfig.apiListId, apiLists),
    [listConfig.apiListId, apiLists],
  );
  const activeVirtual = resolveVirtualListId(selectedListId);

  useEffect(() => {
    setSelectedInstrumentIds(new Set());
    selectionAnchorIndexRef.current = null;
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

  const visualizationQuotesQuery = useQuery({
    queryKey: ['visualization-quotes', openChartInstrumentIds],
    queryFn: () => api.getInstrumentQuotes(openChartInstrumentIds),
    enabled:
      activeVirtual === VIRTUAL_LIST_VISUALIZATION && openChartInstrumentIds.length > 0,
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

  const visualizationListItems = useMemo(() => {
    const byId = new Map(visualizationEntries.map((e) => [e.instrumentId, e]));
    return openChartInstrumentIds.map((instrumentId) => {
      const quoted = visualizationQuotesById.get(instrumentId);
      if (quoted) return quoted;
      const tab = charts.find((t) => t.instrumentId === instrumentId);
      const entry = byId.get(instrumentId);
      if (entry) return visualizationEntryToListItem(entry, allInstruments);
      return visualizationEntryToListItem(
        {
          instrumentId,
          symbol: tab?.label ?? instrumentId,
          name: tab?.label ?? instrumentId,
          firstViewedAt: new Date(0).toISOString(),
          lastViewedAt: new Date(0).toISOString(),
          viewCount: 1,
        },
        allInstruments,
      );
    });
  }, [
    openChartInstrumentIds,
    visualizationQuotesById,
    visualizationEntries,
    charts,
    allInstruments,
  ]);

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

  const selectableIds = useMemo(() => {
    // Visualizados: el orden de pestañas es la verdad (el sort de columna las realinea).
    if (activeVirtual === VIRTUAL_LIST_VISUALIZATION) {
      return selectableItems.map((item) => item.id);
    }
    const sortState = selectedListId
      ? listConfig.sortByListId?.[selectedListId]
      : undefined;
    return sortInstrumentList(selectableItems, sortState).map((item) => item.id);
  }, [selectableItems, selectedListId, listConfig.sortByListId, activeVirtual]);

  const selectAllChecked =
    selectableIds.length > 0 && selectableIds.every((id) => selectedInstrumentIds.has(id));
  const selectAllIndeterminate =
    selectableIds.some((id) => selectedInstrumentIds.has(id)) && !selectAllChecked;
  const selectionEnabled = activeVirtual !== VIRTUAL_LIST_PENDING_ORDERS;

  function toggleSelectAll() {
    setSelectedInstrumentIds((prev) => {
      if (selectableIds.length === 0) return prev;
      if (selectableIds.every((id) => prev.has(id))) {
        selectionAnchorIndexRef.current = null;
        return new Set();
      }
      selectionAnchorIndexRef.current = 0;
      return new Set(selectableIds);
    });
  }

  function handleSelectClick(
    instrumentId: string,
    detail: {
      checked: boolean;
      ctrlKey: boolean;
      metaKey: boolean;
      shiftKey: boolean;
    },
  ) {
    const index = selectableIds.indexOf(instrumentId);
    if (index < 0) return;
    setSelectedInstrumentIds((prev) => {
      const result = applyInstrumentSelection({
        prev,
        instrumentId,
        index,
        orderedIds: selectableIds,
        modifiers: {
          ctrlKey: detail.ctrlKey,
          metaKey: detail.metaKey,
          shiftKey: detail.shiftKey,
        },
        anchorIndex: selectionAnchorIndexRef.current,
        checked: detail.checked,
      });
      selectionAnchorIndexRef.current = result.anchorIndex;
      return result.next;
    });
  }

  const viewingVisualizados = activeVirtual === VIRTUAL_LIST_VISUALIZATION;
  const viewingEstudio = selectedListId === ESTUDIO_LIST_ID;
  const [updatingSelected, setUpdatingSelected] = useState(false);
  const [estudioProgress, setEstudioProgress] = useState<EstudioBannerProgress | null>(
    null,
  );

  /**
   * Fuerza sync de la selección en Estudio.
   * - `rediscover: false` — velas + vigilia CORE-R + frescura Lab (`skip_fresh` posible).
   * - `rediscover: true` — embudo completo (`forceRescan`); confirma coste al usuario.
   */
  async function updateSelectedInstruments(opts: { rediscover: boolean }) {
    const ids = [...selectedInstrumentIds];
    if (ids.length === 0) return;
    if (opts.rediscover) {
      const ok = window.confirm(
        `Redescubrir en ${ids.length} valor${ids.length === 1 ? '' : 'es'}: embudo completo y búsqueda de nuevas estrategias (proceso costoso; puede tardar). ¿Continuar?`,
      );
      if (!ok) return;
    }
    setUpdatingSelected(true);
    const lane = laneFromListAutoMode(opts.rediscover);
    const symbolOf = (id: string) =>
      selectableItems.find((it) => it.id === id)?.symbol ?? id.slice(0, 8);
    const phase = opts.rediscover ? 'Redescubrir' : 'Actualizar';
    const publishKeepAlive = (index: number, detail: string) => {
      useListAutoActivityStore.getState().publish({
        active: true,
        paused: false,
        listId: ESTUDIO_LIST_ID,
        listName: 'Estudio',
        index,
        total: ids.length,
        symbol: symbolOf(ids[index] ?? ids[0] ?? ''),
        detail,
      });
    };
    try {
      setEstudioProgress({
        current: 0,
        total: ids.length,
        label: `${phase} · sync…`,
      });
      publishKeepAlive(0, `${phase} selección · velas…`);
      for (let i = 0; i < ids.length; i++) {
        const id = ids[i]!;
        const sym = symbolOf(id);
        setEstudioProgress({
          current: i + 1,
          total: ids.length,
          label: `${phase} · ${sym}`,
        });
        publishKeepAlive(i, `${phase} · ${sym}`);
        emitEstudioProcessRunning({ instrumentId: id, lane: 'freshness' });
        try {
          await api.syncInstrument(id, 5);
        } catch {
          // seguir con el resto
        }
      }
      touchEstudioLaneStamps(
        ids,
        opts.rediscover ? 'rediscover' : 'freshness',
      );
      setEstudioProgress({
        current: ids.length,
        total: ids.length,
        label: `${phase} · vigilia…`,
      });
      // Vigilia = CORE-R (mandato/PnL); «Actualizar» también la dispara para no dejar el 1º icono vacío.
      emitEstudioProcessRunning({
        instrumentId: ids[0] ?? null,
        lane: 'vigilance',
      });
      try {
        const { runCoreRSchedulerTick } = await import(
          '@/features/backtests/core-r-scheduler-tick'
        );
        await runCoreRSchedulerTick({ force: true, includePnl: true });
      } catch {
        // best-effort
      }
      // Sello local aunque CORE-R no encole (juicio OK / sin listId).
      touchEstudioLaneStamps(ids, 'vigilance');
      setEstudioProgress({
        current: ids.length,
        total: ids.length,
        label: `${phase} · Lab…`,
      });
      emitEstudioProcessRunning({ instrumentId: ids[0] ?? null, lane });
      emitEstudioLaneTick({
        listId: ESTUDIO_LIST_ID,
        lane: opts.rediscover ? 'rediscover' : 'freshness',
        forceRescan: opts.rediscover,
        skipConfirm: true,
        instrumentIds: ids,
        at: new Date().toISOString(),
      });
      void queryClient.invalidateQueries({ queryKey: ['list'] });
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      emitEstudioProcessRunning({ instrumentId: null, lane: null });
    } finally {
      setUpdatingSelected(false);
      setEstudioProgress(null);
      const snap = useListAutoActivityStore.getState();
      if (
        snap.active &&
        snap.listId === ESTUDIO_LIST_ID &&
        (snap.detail?.startsWith('Actualizar') || snap.detail?.startsWith('Redescubrir'))
      ) {
        snap.clear();
      }
    }
  }

  async function addSelectedToEstudio() {
    if (viewingEstudio) return;
    const byId = new Map(selectableItems.map((item) => [item.id, item]));
    const batch = [...selectedInstrumentIds]
      .map((id) => byId.get(id))
      .filter((item): item is (typeof selectableItems)[number] => Boolean(item));
    const { addToEstudioMembership } = await import('@/features/trading/estudio-membership');
    const added = await addToEstudioMembership(batch);
    if (added > 0) {
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      void queryClient.invalidateQueries({ queryKey: ['lists', 'memberships'] });
      void queryClient.invalidateQueries({ queryKey: ['list'] });
      void queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
      updateListConfig({
        apiListId: ESTUDIO_LIST_ID,
        name: 'Estudio',
        source: 'api',
      });
      setSelectedInstrumentIds(new Set());
      selectionAnchorIndexRef.current = null;
    }
  }

  async function removeSelectedFromCurrentList() {
    const ids = [...selectedInstrumentIds];
    if (viewingVisualizados) {
      // Un solo update: evita que el autosave reinyecte pestañas a medias.
      const { closeOpenChartsForInstruments } = await import(
        '@/lib/close-chart-on-list-removal'
      );
      closeOpenChartsForInstruments(ids);
      const { reconcileVisualizadosToOpenCharts } = await import(
        '@/features/trading/lists-tab/use-chart-visualization-sync'
      );
      reconcileVisualizadosToOpenCharts();
      setSelectedInstrumentIds(new Set());
      selectionAnchorIndexRef.current = null;
      return;
    }
    if (!viewingEstudio) {
      // Quitar de Estudio aunque estemos en otra lista (selección parcialmente en Estudio).
      const inEstudio = ids.filter((id) =>
        useEstudioMembershipStore.getState().contains(id),
      );
      if (inEstudio.length === 0) return;
      const { removeFromEstudioMembership } = await import(
        '@/features/trading/estudio-membership'
      );
      const { unsubscribeInstrumentFromSupervision } = await import(
        '@/features/trading/estudio-supervision'
      );
      await removeFromEstudioMembership(inEstudio);
      unsubscribeInstrumentFromSupervision(inEstudio);
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      void queryClient.invalidateQueries({ queryKey: ['lists', 'memberships'] });
      void queryClient.invalidateQueries({ queryKey: ['list'] });
      void queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
      setSelectedInstrumentIds(new Set());
      selectionAnchorIndexRef.current = null;
      return;
    }
    const { removeFromEstudioMembership } = await import(
      '@/features/trading/estudio-membership'
    );
    const { unsubscribeInstrumentFromSupervision } = await import(
      '@/features/trading/estudio-supervision'
    );
    await removeFromEstudioMembership(ids);
    unsubscribeInstrumentFromSupervision(ids);
    void queryClient.invalidateQueries({ queryKey: ['lists'] });
    void queryClient.invalidateQueries({ queryKey: ['lists', 'memberships'] });
    void queryClient.invalidateQueries({ queryKey: ['list'] });
    void queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
    setSelectedInstrumentIds(new Set());
    selectionAnchorIndexRef.current = null;
  }

  const selectedInEstudioCount = useMemo(() => {
    const set = new Set(estudioMemberIds.map((m) => m.instrumentId));
    let n = 0;
    for (const id of selectedInstrumentIds) {
      if (set.has(id)) n += 1;
    }
    return n;
  }, [selectedInstrumentIds, estudioMemberIds]);

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

  function openSelectedCharts() {
    const listId = selectedListId ?? listConfig.apiListId ?? listConfig.id;
    const byId = new Map(selectableItems.map((item) => [item.id, item]));
    const items = [...selectedInstrumentIds]
      .map((id) => byId.get(id))
      .filter((item): item is (typeof selectableItems)[number] => Boolean(item))
      .map((item) => ({ instrumentId: item.id, label: item.symbol }));
    if (items.length === 0) return;
    focusInstrumentsFromList(listId, items);
    const nextActiveId = useWorkspaceStore.getState().workspace.activeChartId;
    if (listId) setManualListSelection(listId, nextActiveId);
    ensureChartRoute(navigate);
    requestChartReflow();
  }

  async function reorderSelectedChartsByIo() {
    const ids = [...selectedInstrumentIds];
    if (ids.length < 2) return;
    setSortingByIo(true);
    try {
      const { orderInstrumentIdsByIo } = await import(
        '@/features/trading/lists-tab/sort-visualizados-by-io'
      );
      const {
        collectCachedFaScores,
        collectCachedTaScores,
        fetchIoByInstrumentIds,
      } = await import('@/features/trading/lists-tab/fetch-io-scores-for-sort');

      const ioByInstrument = await fetchIoByInstrumentIds(
        ids,
        {
          queryFundamentals: (instrumentIds) =>
            api.queryInstrumentFundamentals({ instrumentIds }),
          queryComposite: (instrumentIds) =>
            api.queryInstrumentComposite({
              instrumentIds,
              horizon: 'swing',
              regime: 'neutral',
            }),
        },
        {
          fa: collectCachedFaScores(queryClient),
          ta: collectCachedTaScores(queryClient),
        },
      );

      const scored = ids.filter((id) => ioByInstrument.get(id) != null).length;
      if (scored === 0) {
        window.alert(
          'No hay Índice Operativo (IO) disponible para la selección. Espera a que Operativa cargue scores o sincroniza fundamentals.',
        );
        return;
      }

      const symbolById = new Map(
        selectableItems
          .filter((item) => selectedInstrumentIds.has(item.id))
          .map((item) => [item.id, item.symbol] as const),
      );
      const ordered = orderInstrumentIdsByIo(ids, ioByInstrument, symbolById);
      useWorkspaceStore.getState().reorderChartTabsByInstrumentIds(ordered);
      requestChartReflow();
    } catch (err) {
      window.alert(
        err instanceof ApiError
          ? err.message
          : 'No se pudieron ordenar las pestañas por Índice Operativo.',
      );
    } finally {
      setSortingByIo(false);
    }
  }

  async function visualizeFromSearch(
    instrument: (typeof allInstruments)[number],
    options?: { searchQuery?: string; source?: 'search' | 'import' },
  ) {
    // Abrir pestaña (Visualizados = espejo). Lista visible: Cartera → Estudio → resto.
    useVisualizationStore.getState().addInstrument(instrument, {
      searchQuery: options?.searchQuery,
      source: options?.source ?? 'search',
    });
    const preferredListId =
      (chartListMembership
        ? resolvePreferredListIdForInstrument(instrument.id, chartListMembership)
        : null) ?? VIRTUAL_LIST_VISUALIZATION;
    updateListConfig(listConfigForSelection(preferredListId, apiLists));
    focusInstrumentFromList(preferredListId, instrument.id, instrument.symbol);
    ensureChartRoute(navigate);
    requestChartReflow();
    const { reconcileVisualizadosToOpenCharts } = await import(
      '@/features/trading/lists-tab/use-chart-visualization-sync'
    );
    reconcileVisualizadosToOpenCharts();
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

  // Al enfocar valor (pestaña / búsqueda): dejarlo arriba del viewport sin reordenar.
  useEffect(() => {
    if (!activeInstrumentId || isLoading) return;
    const timer = window.setTimeout(() => {
      scrollListInstrumentToTop(listScrollRef.current, activeInstrumentId);
    }, 80);
    return () => window.clearTimeout(timer);
  }, [activeInstrumentId, selectedListId, isLoading, selectableItems.length]);

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
        <ListRecommendationScoresProvider
          instrumentIds={selectableItems.map((item) => item.id)}
        >
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {viewingEstudio && !isLoading && listInstruments.length > 0 ? (
          <EstudioListSupervisionBanner progress={estudioProgress} />
        ) : null}
        <div ref={listScrollRef} className="scroll-area min-h-0 flex-1 overflow-auto">
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

        {viewingVisualizados && !isLoading && visualizationListItems.length === 0 && (
          <p className="p-4 text-center text-xs text-muted-foreground">
            Aquí solo aparecen los valores con pestaña de gráfico abierta. Busca arriba o
            abre un valor; al cerrar la pestaña sale de Visualizados. Desde aquí puedes
            «Pasar a Estudio».
          </p>
        )}

        {viewingEstudio && !isLoading && listInstruments.length === 0 && (
          <p className="p-4 text-center text-xs text-muted-foreground">
            Selecciona valores en Visualizados, IBEX u otra lista y pulsa «Pasar a Estudio».
            Aquí viven los valores supervisables. Activa Supervisión ON en el banner.
          </p>
        )}

        {viewingVisualizados && !isLoading && visualizationListItems.length > 0 && (
          <SortedVisualizationList
            items={visualizationListItems}
            activeInstrumentId={activeInstrumentId}
            isListSource={isListSourceRow}
            onOpenChart={focusInstrument}
            selectedIds={selectedInstrumentIds}
            onToggleSelect={handleSelectClick}
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
            onToggleSelect={handleSelectClick}
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
            onToggleSelect={handleSelectClick}
          />
        )}
        </div>
        </div>
        </ListRecommendationScoresProvider>
      </ListColumnLayoutProvider>

      {selectionEnabled && selectedInstrumentIds.size > 0 ? (
        <div
          className="z-20 flex shrink-0 flex-wrap items-center gap-1.5 border-t border-border bg-card px-2 py-2 text-[11px] shadow-[0_-4px_12px_rgba(0,0,0,0.06)]"
          data-testid="list-selection-actions"
          role="toolbar"
          aria-label="Acciones sobre la selección"
        >
          <span className="mr-1 tabular-nums text-muted-foreground">
            {selectedInstrumentIds.size} seleccionado
            {selectedInstrumentIds.size === 1 ? '' : 's'}
          </span>
          {!viewingEstudio ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded border border-primary/50 bg-primary/15 px-2 py-1.5 font-semibold text-primary hover:bg-primary/20"
              onClick={() => void addSelectedToEstudio()}
              title="Pasar la selección a Estudio (supervisión)"
            >
              <ListPlus className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
              A Estudio
            </button>
          ) : null}
          <button
            type="button"
            className={
              viewingEstudio || viewingVisualizados
                ? 'inline-flex items-center gap-1 rounded border border-destructive/40 bg-destructive/10 px-2 py-1.5 font-semibold text-destructive hover:bg-destructive/15 disabled:cursor-not-allowed disabled:opacity-40'
                : 'inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40'
            }
            onClick={() => void removeSelectedFromCurrentList()}
            disabled={
              viewingVisualizados
                ? selectedInstrumentIds.size === 0
                : viewingEstudio
                  ? selectedInstrumentIds.size === 0
                  : selectedInEstudioCount === 0
            }
            title={
              viewingVisualizados
                ? 'Cierra las pestañas de la selección (salen de Visualizados)'
                : viewingEstudio
                  ? 'Elimina de Estudio (sale de la cola de supervisión)'
                  : 'Quita la selección de Estudio'
            }
          >
            <ListMinus className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
            {viewingVisualizados
              ? 'Quitar'
              : viewingEstudio
                ? 'Eliminar'
                : 'Quitar'}
          </button>
          {viewingVisualizados ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
              disabled={selectedInstrumentIds.size < 2 || sortingByIo}
              onClick={() => void reorderSelectedChartsByIo()}
              title="Ordena pestañas por Índice Operativo (IO 0–100): mayor IO a la izquierda (#1 en Estudio = mejor IO). Usa caché de Operativa; si falta, carga en trozos pequeños."
            >
              <ArrowDownWideNarrow className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
              {sortingByIo ? 'IO…' : 'Por IO'}
            </button>
          ) : null}
          {/* En Visualizados sobra: esa lista ya es el espejo de pestañas abiertas. */}
          {!viewingVisualizados ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent"
              onClick={openSelectedCharts}
              title="Abrir gráficos de la selección"
            >
              <LineChart className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
              Abrir gráficos
            </button>
          ) : null}
          {viewingEstudio ? (
            <>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1.5 font-semibold text-foreground hover:bg-accent disabled:opacity-50"
                disabled={updatingSelected}
                title="Adelanta vigilia + frescura (velas + Lab). Funciona con Supervisión OFF."
                onClick={() => void updateSelectedInstruments({ rediscover: false })}
              >
                <RefreshCw className="h-3.5 w-3.5 opacity-70" aria-hidden />
                {updatingSelected ? 'Actualizando…' : 'Actualizar'}
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-amber-500/50 bg-amber-500/10 px-2.5 py-1.5 font-semibold text-amber-800 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-200"
                disabled={updatingSelected}
                title="Costoso: embudo completo y búsqueda de nuevas estrategias TOP. Pide confirmación."
                onClick={() => void updateSelectedInstruments({ rediscover: true })}
              >
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                Redescubrir
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="ml-auto inline-flex items-center gap-1 rounded px-2.5 py-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={() => {
              setSelectedInstrumentIds(new Set());
              selectionAnchorIndexRef.current = null;
            }}
            title="Quitar la selección"
          >
            <Eraser className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
            Limpiar
          </button>
        </div>
      ) : null}
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
  onToggleSelect: (
    instrumentId: string,
    detail: {
      checked: boolean;
      ctrlKey: boolean;
      metaKey: boolean;
      shiftKey: boolean;
    },
  ) => void;
}) {
  const { sortState } = useListColumnLayoutContext();
  const scores = useListRecommendationScoresMap();
  const sorted = useMemo(
    () => sortInstrumentListWithRecommendation(items, sortState, scores),
    [items, sortState, scores],
  );
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
          onToggleSelect={(detail) => onToggleSelect(item.id, detail)}
        />
      ))}
    </>
  );
}

function SortedVisualizationList({
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
  onToggleSelect: (
    instrumentId: string,
    detail: {
      checked: boolean;
      ctrlKey: boolean;
      metaKey: boolean;
      shiftKey: boolean;
    },
  ) => void;
}) {
  const { sortState } = useListColumnLayoutContext();
  const scores = useListRecommendationScoresMap();
  const sorted = useMemo(
    () => sortInstrumentListWithRecommendation(items, sortState, scores),
    [items, sortState, scores],
  );

  // Con sort activo: alinear pestañas (izq = arriba). Sin sort: orden de pestañas.
  useEffect(() => {
    if (!sortState || sorted.length === 0) return;
    const orderedIds = sorted.map((item) => item.id);
    const charts = useWorkspaceStore.getState().workspace.charts;
    const openIds = [
      ...new Set(
        charts
          .filter((tab) => Boolean(tab.instrumentId))
          .map((tab) => tab.instrumentId as string),
      ),
    ];
    if (
      openIds.length === orderedIds.length &&
      openIds.every((id, index) => id === orderedIds[index])
    ) {
      return;
    }
    useWorkspaceStore.getState().reorderChartTabsByInstrumentIds(orderedIds);
  }, [sortState, sorted]);

  useListInstrumentKeyboardNav(sorted, activeInstrumentId, onOpenChart);
  return (
    <>
      {sorted.map((item) => (
        <ListItemAccordion
          key={item.id}
          item={item}
          processSubtitle
          isChartActive={activeInstrumentId === item.id}
          isListSource={isListSource(item.id)}
          onOpenChart={() => onOpenChart(item.id, item.symbol)}
          selected={selectedIds.has(item.id)}
          onToggleSelect={(detail) => onToggleSelect(item.id, detail)}
        />
      ))}
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
  positions: PositionDto[];
  allInstruments: import('@bolsa/shared').InstrumentWithMetaDto[];
  selectedIds: Set<string>;
  onToggleSelect: (
    instrumentId: string,
    detail: {
      checked: boolean;
      ctrlKey: boolean;
      metaKey: boolean;
      shiftKey: boolean;
    },
  ) => void;
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
            onToggleSelect={(detail) => onToggleSelect(item.id, detail)}
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
