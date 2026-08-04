import { useMemo, useState, Fragment } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { InstrumentListSummaryDto } from '@bolsa/shared';
import {
  isVirtualListId,
  VIRTUAL_LIST_LABELS,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
  visibleListColumns,
} from '@bolsa/shared';
import { Plus } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import {
  buildVirtualListSummaries,
  positionToListItem,
  visualizationEntryToListItem,
} from '@/lib/default-lists';
import { resolveListColumnLayout } from '@/lib/list-column-layout';
import { patchToggleCarouselList, isListPinnedInCarousel } from '@/lib/list-carousel-config';
import {
  resolveListHubSort,
  sortListSummaries,
} from '@/lib/list-hub-column-layout';
import { exportInstrumentsCsv } from '@/lib/list-utils';
import { isInstrumentInList } from '@/lib/chart-list-membership';
import { listConfigForSelection, resolveSelectedListId, syncAfterListDeleted } from '@/lib/list-sync';
import { setManualListSelection } from '@/lib/list-selection-guard';
import { Button } from '@/components/ui/button';
import { FieldRow, inputClassName } from '@/components/ui/dialog';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useVisualizationStore } from '@/stores/visualization-store';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { openVisualizationLog } from '@/features/trading/lists-tab/visualization-log-dialog';
import { ListHubColumnHeader } from '@/features/trading/lists-tab/list-hub-column-header';
import { ListHubColumnLayoutProvider } from '@/features/trading/lists-tab/list-hub-column-layout-context';
import {
  ListHubInstrumentPicker,
  ListHubRow,
} from '@/features/trading/lists-tab/list-hub-row';
import { ListHubIndexSearch } from '@/features/trading/lists-tab/list-hub-index-search';

function listTypeLabel(list: InstrumentListSummaryDto): string {
  if (isVirtualListId(list.id)) return 'sistema';
  if (list.source === 'catalog' || list.kind === 'linked_universe') return 'índice';
  if (list.kind === 'snapshot') return 'copia';
  return 'personal';
}

type ListHubFamilyId = 'sistema' | 'indices' | 'personales';

const LIST_HUB_FAMILY_ORDER: ListHubFamilyId[] = ['sistema', 'indices', 'personales'];

const LIST_HUB_FAMILY_LABEL: Record<ListHubFamilyId, string> = {
  sistema: 'Sistema',
  indices: 'Índices',
  personales: 'Personales',
};

function listHubFamily(list: InstrumentListSummaryDto): ListHubFamilyId {
  if (isVirtualListId(list.id)) return 'sistema';
  if (list.source === 'catalog' || list.kind === 'linked_universe') return 'indices';
  return 'personales';
}

function groupListsByFamily(
  sorted: InstrumentListSummaryDto[],
): { id: ListHubFamilyId; label: string; lists: InstrumentListSummaryDto[] }[] {
  const buckets: Record<ListHubFamilyId, InstrumentListSummaryDto[]> = {
    sistema: [],
    indices: [],
    personales: [],
  };
  for (const list of sorted) {
    buckets[listHubFamily(list)].push(list);
  }
  return LIST_HUB_FAMILY_ORDER.filter((id) => buckets[id].length > 0).map((id) => ({
    id,
    label: LIST_HUB_FAMILY_LABEL[id],
    lists: buckets[id],
  }));
}

export function ListHubPanel() {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);
  const { pendingOrders } = usePendingOrders();
  const queryClient = useQueryClient();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showNewList, setShowNewList] = useState(false);
  const [newName, setNewName] = useState('');
  const [newInstrumentIds, setNewInstrumentIds] = useState<Set<string>>(new Set());
  const [searchNew, setSearchNew] = useState('');
  const [error, setError] = useState<string | null>(null);
  const accountScope = useActiveAccountQueryKey();

  const listsQuery = useQuery({ queryKey: ['lists'], queryFn: api.getLists });
  const catalogQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
    enabled: showNewList,
    staleTime: 60_000,
  });
  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
  });

  const apiLists = listsQuery.data?.data ?? [];
  const catalog = catalogQuery.data?.data ?? [];
  const positions = portfolioQuery.data?.data.positions ?? [];
  const pendingBuyCount = pendingOrders.filter((order) => order.side === 'buy').length;
  const visualizationEntries = useVisualizationStore((state) => state.entries);

  const virtualLists = useMemo(
    () =>
      buildVirtualListSummaries(
        positions.length,
        pendingBuyCount,
        visualizationEntries.length,
      ),
    [positions.length, pendingBuyCount, visualizationEntries.length],
  );

  const activeListId = resolveSelectedListId(listConfig.apiListId, apiLists);
  const charts = useWorkspaceStore((state) => state.workspace.charts);
  const activeChartId = useWorkspaceStore((state) => state.workspace.activeChartId);
  const chartListMembership = useWorkspaceStore((state) => state.chartListMembership);
  const activeChartTab = charts.find((tab) => tab.id === activeChartId);
  const chartInstrumentId = activeChartTab?.instrumentId;
  const chartInstrumentLabel = activeChartTab?.label;

  function selectList(list: InstrumentListSummaryDto) {
    setManualListSelection(list.id, activeChartId);
    updateListConfig({
      ...listConfigForSelection(list.id, apiLists),
      watchlistTab: 'values',
    });
    void queryClient.invalidateQueries({ queryKey: ['list-quotes', list.id] });
    save();
  }

  function toggleCarousel(listId: string) {
    updateListConfig(patchToggleCarouselList(listId, listConfig, apiLists));
    save();
  }

  async function exportList(list: InstrumentListSummaryDto) {
    const columns = visibleListColumns(resolveListColumnLayout(listConfig, list.id));

    if (list.id === VIRTUAL_LIST_PENDING_ORDERS) {
      window.alert('Las órdenes pendientes no se exportan a CSV.');
      return;
    }

    if (list.id === VIRTUAL_LIST_PORTFOLIO) {
      if (positions.length === 0) {
        window.alert('No hay posiciones para exportar.');
        return;
      }
      exportInstrumentsCsv(
        positions.map((pos) => positionToListItem(pos, catalog)),
        columns,
        list.name,
      );
      return;
    }

    if (list.id === VIRTUAL_LIST_VISUALIZATION) {
      if (visualizationEntries.length === 0) {
        window.alert('No hay valores en Estudio.');
        return;
      }
      exportInstrumentsCsv(
        visualizationEntries.map((entry) => visualizationEntryToListItem(entry, catalog)),
        columns,
        list.name,
      );
      return;
    }

    try {
      const response = await api.getListQuotes(list.id);
      if (response.data.length === 0) {
        window.alert('La lista está vacía.');
        return;
      }
      exportInstrumentsCsv(response.data, columns, list.name);
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'No se pudo exportar');
    }
  }

  const deleteMutation = useMutation({
    mutationFn: (listId: string) => api.deleteList(listId),
    onSuccess: (_data, listId) => {
      const patch = syncAfterListDeleted(queryClient, listId, listConfig);
      updateListConfig(patch);
      if (expandedId === listId) setExpandedId(null);
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      setError(null);
      save();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'No se pudo eliminar la lista');
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createList({
        name: newName.trim(),
        instrumentIds: [...newInstrumentIds],
        source: 'custom',
      }),
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      const summary: InstrumentListSummaryDto = {
        id: response.data.id,
        name: response.data.name,
        source: response.data.source,
        itemCount: response.data.instrumentIds.length,
        updatedAt: response.data.updatedAt,
        kind: response.data.kind,
      };
      const carouselListIds = [...new Set([...(listConfig.carouselListIds ?? []), summary.id])];
      const carouselPinnedListNames = [
        ...new Set([...(listConfig.carouselPinnedListNames ?? []), summary.name]),
      ];
      updateListConfig({
        ...listConfigForSelection(summary.id, [...apiLists, summary]),
        carouselListIds,
        carouselPinnedListNames,
        carouselInitialized: true,
        watchlistTab: 'values',
      });
      setManualListSelection(summary.id, activeChartId);
      setNewName('');
      setNewInstrumentIds(new Set());
      setShowNewList(false);
      setError(null);
      save();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear la lista');
    },
  });

  const freezeCopyMutation = useMutation({
    mutationFn: async (list: InstrumentListSummaryDto) => {
      const detail = await api.getList(list.id);
      const day = new Date().toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
      });
      return api.createList({
        name: `Copia ${list.name} (${day})`,
        instrumentIds: detail.data.instrumentIds,
        source: 'custom',
        kind: 'snapshot',
      });
    },
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['lists'] });
      const summary: InstrumentListSummaryDto = {
        id: response.data.id,
        name: response.data.name,
        source: response.data.source,
        itemCount: response.data.instrumentIds.length,
        updatedAt: response.data.updatedAt,
        kind: response.data.kind ?? 'snapshot',
      };
      const carouselListIds = [...new Set([...(listConfig.carouselListIds ?? []), summary.id])];
      const carouselPinnedListNames = [
        ...new Set([...(listConfig.carouselPinnedListNames ?? []), summary.name]),
      ];
      updateListConfig({
        ...listConfigForSelection(summary.id, [...apiLists, summary]),
        carouselListIds,
        carouselPinnedListNames,
        carouselInitialized: true,
        watchlistTab: 'values',
      });
      setManualListSelection(summary.id, activeChartId);
      setError(null);
      save();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'No se pudo congelar la copia');
    },
  });

  const allLists = [...virtualLists, ...apiLists];
  const metaById = Object.fromEntries(
    allLists.map((list) => [
      list.id,
      {
        typeLabel: listTypeLabel(list),
        carouselPinned: isListPinnedInCarousel(list.id, listConfig),
      },
    ]),
  );
  const sortedLists = sortListSummaries(allLists, resolveListHubSort(listConfig), metaById);
  const listFamilies = groupListsByFamily(sortedLists);

  const activeLabel = isVirtualListId(activeListId)
    ? VIRTUAL_LIST_LABELS[activeListId as keyof typeof VIRTUAL_LIST_LABELS]
    : apiLists.find((list) => list.id === activeListId)?.name ?? '—';

  return (
    <ListHubColumnLayoutProvider>
      <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-2 py-1.5">
        <p className="min-w-0 truncate text-[10px] text-muted-foreground">
          {allLists.length} listas · activa:{' '}
          <span className="font-medium text-foreground">{activeLabel}</span>
          {chartInstrumentLabel && (
            <>
              {' '}
              · gráfico:{' '}
              <span className="font-medium text-foreground">{chartInstrumentLabel}</span>
            </>
          )}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => setShowNewList((v) => !v)}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Nueva
        </Button>
      </div>

      {showNewList && (
        <section className="shrink-0 space-y-2 border-b border-border bg-muted/10 p-2">
          <p className="text-xs font-medium">Nueva lista personalizada</p>
          <FieldRow label="Nombre">
            <input
              type="text"
              className={inputClassName}
              value={newName}
              placeholder="Ej. Energía, Favoritos…"
              onChange={(event) => setNewName(event.target.value)}
            />
          </FieldRow>
          <FieldRow label="Buscar">
            <input
              type="search"
              className={inputClassName}
              value={searchNew}
              onChange={(event) => setSearchNew(event.target.value)}
            />
          </FieldRow>
          <ListHubInstrumentPicker
            catalog={catalog}
            selectedIds={newInstrumentIds}
            onChange={setNewInstrumentIds}
            filter={searchNew}
          />
          <Button
            type="button"
            size="sm"
            disabled={!newName.trim() || newInstrumentIds.size === 0 || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Creando…' : 'Crear lista'}
          </Button>
        </section>
      )}

      <ListHubIndexSearch apiLists={apiLists} onError={setError} />

      <ListHubColumnHeader chartInstrumentLabel={chartInstrumentLabel} />

      <div className="scroll-area min-h-0 flex-1 overflow-auto">
        {listsQuery.isLoading && (
          <p className="p-2 text-xs text-muted-foreground">Cargando listas…</p>
        )}
        {listFamilies.map((family) => (
          <Fragment key={family.id}>
            <div className="sticky top-0 z-[1] border-b border-border/60 bg-muted/40 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground backdrop-blur-sm">
              {family.label}
              <span className="ml-1 font-normal normal-case tracking-normal">
                ({family.lists.length})
              </span>
            </div>
            {family.lists.map((list) => {
              const canMutate = !isVirtualListId(list.id);
              const isExpandable = !isVirtualListId(list.id);
              const isExpanded = expandedId === list.id && isExpandable;
              return (
                <ListHubRow
                  key={list.id}
                  list={list}
                  isActive={activeListId === list.id}
                  isPinned={isListPinnedInCarousel(list.id, listConfig)}
                  carouselLocked={false}
                  canMutate={canMutate}
                  expanded={isExpanded}
                  onToggleExpand={() => {
                    if (!isExpandable) return;
                    setExpandedId((current) => (current === list.id ? null : list.id));
                  }}
                  onSelect={() => selectList(list)}
                  onToggleCarousel={() => toggleCarousel(list.id)}
                  onExport={() => void exportList(list)}
                  onDelete={() => {
                    const isIndex = list.source === 'catalog' || list.kind === 'linked_universe';
                    const ok = window.confirm(
                      isIndex
                        ? `¿Desuscribir el índice «${list.name}»?\n\nDesaparece de tus listas; puedes volver a suscribirlo desde el buscador. No borra velas ni Finalistas.`
                        : `¿Eliminar la lista «${list.name}»? Esta acción no se puede deshacer.`,
                    );
                    if (ok) {
                      deleteMutation.mutate(list.id);
                    }
                  }}
                  onFreezeCopy={
                    list.source === 'catalog' || list.kind === 'linked_universe'
                      ? () => {
                          if (freezeCopyMutation.isPending) return;
                          freezeCopyMutation.mutate(list);
                        }
                      : undefined
                  }
                  onShowLog={
                    list.id === VIRTUAL_LIST_VISUALIZATION
                      ? () => openVisualizationLog()
                      : undefined
                  }
                  chartInstrumentLabel={chartInstrumentLabel}
                  chartMembershipKnown={chartListMembership != null}
                  containsChartInstrument={
                    chartInstrumentId && chartListMembership
                      ? isInstrumentInList(list.id, chartInstrumentId, chartListMembership)
                      : false
                  }
                />
              );
            })}
          </Fragment>
        ))}
      </div>

      {error && <p className="shrink-0 px-2 py-1 text-xs text-destructive">{error}</p>}
      </div>
    </ListHubColumnLayoutProvider>
  );
}
