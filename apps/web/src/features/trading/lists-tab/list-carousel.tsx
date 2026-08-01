import { useEffect, useMemo, useRef } from 'react';

import type { InstrumentListSummaryDto } from '@bolsa/shared';

import { CATALOG_IBEX_LIST_ID, isVirtualListId } from '@bolsa/shared';

import { ChevronLeft, ChevronRight } from 'lucide-react';

import { cn } from '@/lib/utils';

import { IconButton } from '@/components/ui/icon-button';

import { useWorkspaceStore } from '@/stores/workspace-store';

import { ListCarouselMenu } from '@/features/trading/lists-tab/list-carousel-menu';

import { reconcileCarouselListIds } from '@/lib/list-sync';



interface ListCarouselProps {

  virtualLists: InstrumentListSummaryDto[];

  apiLists: InstrumentListSummaryDto[];

  apiListsReady: boolean;

  selectedId?: string;

  onSelect: (listId: string) => void;

}



function resolveCarouselLists(

  virtualLists: InstrumentListSummaryDto[],

  apiLists: InstrumentListSummaryDto[],

  pinnedApiIds: string[],

  hiddenIds: string[] = [],

) {

  const seen = new Set<string>();

  const hidden = new Set(hiddenIds);

  const items: InstrumentListSummaryDto[] = [];



  for (const list of virtualLists) {

    if (hidden.has(list.id)) continue;

    if (!seen.has(list.id)) {

      seen.add(list.id);

      items.push(list);

    }

  }



  for (const id of pinnedApiIds) {

    if (isVirtualListId(id) || hidden.has(id)) continue;

    const list = apiLists.find((entry) => entry.id === id);

    if (list && !seen.has(list.id)) {

      seen.add(list.id);

      items.push(list);

    }

  }



  return items;

}



export function ListCarousel({

  virtualLists,

  apiLists,

  apiListsReady,

  selectedId,

  onSelect,

}: ListCarouselProps) {

  const scrollRef = useRef<HTMLDivElement>(null);

  const hydrated = useWorkspaceStore((s) => s.hydrated);

  const listConfig = useWorkspaceStore((s) => s.workspace.list);

  const updateListConfig = useWorkspaceStore((s) => s.updateListConfig);

  const chartListContext = useWorkspaceStore((s) => s.workspace.chartListContext);

  const activeInstrumentId = useWorkspaceStore(

    (s) => s.workspace.charts.find((tab) => tab.id === s.workspace.activeChartId)?.instrumentId,

  );



  const pinnedIds = listConfig.carouselListIds ?? [];

  const pinnedNames = listConfig.carouselPinnedListNames ?? [];

  const hiddenIds = listConfig.carouselHiddenListIds ?? [];



  useEffect(() => {

    if (!hydrated || !apiListsReady) return;



    const reconciled = reconcileCarouselListIds(pinnedIds, pinnedNames, apiLists);

    const reconciledNames = reconciled

      .map((id) => apiLists.find((list) => list.id === id)?.name)

      .filter((name): name is string => Boolean(name));



    if (

      reconciled.join('|') !== pinnedIds.join('|') ||

      reconciledNames.join('|') !== pinnedNames.join('|')

    ) {

      updateListConfig({

        carouselListIds: reconciled,

        carouselPinnedListNames: reconciledNames,

        carouselInitialized: true,

      });

      return;

    }



    if (listConfig.carouselInitialized) return;

    // Ya hay pines (p. ej. desde Listas) → no pisar con IBEX; solo marcar inicializado.
    if (pinnedIds.length > 0 || pinnedNames.length > 0) {
      updateListConfig({ carouselInitialized: true });
      return;
    }

    if ((listConfig.carouselHiddenListIds?.length ?? 0) > 0) {
      updateListConfig({ carouselInitialized: true });
      return;
    }

    const ibex =
      apiLists.find((list) => list.id === CATALOG_IBEX_LIST_ID) ??
      apiLists.find((list) => list.name === 'IBEX 35') ??
      apiLists.find((list) => list.source === 'catalog');

    updateListConfig({
      carouselListIds: ibex ? [ibex.id] : [],
      carouselPinnedListNames: ibex ? [ibex.name] : [],
      carouselInitialized: true,
    });
  }, [
    apiLists,

    apiListsReady,

    hydrated,

    pinnedIds,

    pinnedNames,

    listConfig.carouselInitialized,

    listConfig.carouselHiddenListIds,

    updateListConfig,

  ]);



  const carouselLists = useMemo(

    () => resolveCarouselLists(virtualLists, apiLists, pinnedIds, hiddenIds),

    [virtualLists, apiLists, pinnedIds, hiddenIds],

  );



  function scrollBy(delta: number) {

    scrollRef.current?.scrollBy({ left: delta, behavior: 'smooth' });

  }



  return (

    <div className="flex items-center gap-0.5">

      <IconButton

        icon={ChevronLeft}

        title="Desplazar listas"

        className="shrink-0 opacity-70"

        onClick={() => scrollBy(-120)}

      />



      <div

        ref={scrollRef}

        className="scroll-area flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-0.5"

      >

        {carouselLists.length === 0 && (

          <span className="px-2 text-[11px] text-muted-foreground">Sin listas</span>

        )}

        {carouselLists.map((list) => {

          const isActive = list.id === selectedId;

          const isChartSource =

            chartListContext?.listId === list.id &&

            chartListContext.instrumentId === activeInstrumentId;

          const isVirtual = isVirtualListId(list.id);

          return (

            <button

              key={list.id}

              type="button"

              onClick={() => onSelect(list.id)}

              className={cn(

                'shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',

                isActive

                  ? 'border-emerald-500 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'

                  : 'border-border bg-muted/30 text-muted-foreground hover:border-primary/40 hover:text-foreground',

                isChartSource && 'ring-2 ring-primary/50',

                isVirtual && !isActive && 'border-amber-500/30',

              )}

              title={`${list.name} (${list.itemCount})${isChartSource ? ' · lista del gráfico activo' : ''}`}

            >

              <span className="max-w-[96px] truncate">{list.name}</span>

              <span className="ml-1 opacity-60">{list.itemCount}</span>

            </button>

          );

        })}

      </div>



      <IconButton

        icon={ChevronRight}

        title="Desplazar listas"

        className="shrink-0 opacity-70"

        onClick={() => scrollBy(120)}

      />



      <ListCarouselMenu virtualLists={virtualLists} apiLists={apiLists} />

    </div>

  );

}
