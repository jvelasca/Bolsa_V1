import type { InstrumentListSummaryDto, InstrumentWithMetaDto, PositionDto } from '@bolsa/shared';
import {
  VIRTUAL_LIST_LABELS,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
  type VirtualListId,
} from '@bolsa/shared';
import type { PendingOrderDto } from '@bolsa/shared';
import type { VisualizationSessionEntry } from '@/stores/visualization-store';

export function buildVirtualListSummaries(
  portfolioCount: number,
  pendingCount: number,
  visualizationCount: number,
): InstrumentListSummaryDto[] {
  const now = new Date().toISOString();
  return [
    {
      id: VIRTUAL_LIST_PORTFOLIO,
      name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_PORTFOLIO],
      source: 'virtual',
      itemCount: portfolioCount,
      updatedAt: now,
    },
    {
      id: VIRTUAL_LIST_PENDING_ORDERS,
      name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_PENDING_ORDERS],
      source: 'virtual',
      itemCount: pendingCount,
      updatedAt: now,
    },
    {
      id: VIRTUAL_LIST_VISUALIZATION,
      name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_VISUALIZATION],
      source: 'virtual',
      itemCount: visualizationCount,
      updatedAt: now,
    },
  ];
}

export function mergeCarouselLists(
  virtual: InstrumentListSummaryDto[],
  api: InstrumentListSummaryDto[],
): InstrumentListSummaryDto[] {
  const seen = new Set<string>();
  const merged: InstrumentListSummaryDto[] = [];
  for (const list of [...virtual, ...api]) {
    if (seen.has(list.id)) continue;
    seen.add(list.id);
    merged.push(list);
  }
  return merged;
}

export function positionToListItem(
  position: PositionDto,
  catalog: InstrumentWithMetaDto[],
): InstrumentWithMetaDto {
  const fromCatalog = catalog.find((item) => item.id === position.instrumentId);
  if (fromCatalog) return fromCatalog;

  return {
    id: position.instrumentId,
    symbol: position.symbol,
    yahooSymbol: position.symbol,
    name: position.name,
    exchange: 'BME',
    country: 'ES',
    currency: 'EUR',
    sector: null,
    isActive: true,
    meta: {
      barCount: 0,
      lastSync: null,
      lastClose: position.lastPrice,
      changePct: position.unrealizedPnlPct,
    },
  };
}

export function pendingOrderToListItem(
  order: PendingOrderDto,
  catalog: InstrumentWithMetaDto[],
): InstrumentWithMetaDto {
  const fromCatalog = catalog.find((item) => item.id === order.instrumentId);
  if (fromCatalog) return fromCatalog;

  return {
    id: order.instrumentId,
    symbol: order.symbol,
    yahooSymbol: order.symbol,
    name: order.symbol,
    exchange: 'BME',
    country: 'ES',
    currency: 'EUR',
    sector: null,
    isActive: true,
    meta: {
      barCount: 0,
      lastSync: null,
      lastClose: order.limitPrice,
      changePct: null,
    },
  };
}

export function resolveVirtualListId(id: string | undefined): VirtualListId | null {
  if (
    id === VIRTUAL_LIST_PORTFOLIO ||
    id === VIRTUAL_LIST_PENDING_ORDERS ||
    id === VIRTUAL_LIST_VISUALIZATION
  ) {
    return id;
  }
  return null;
}

export function visualizationEntryToListItem(
  entry: VisualizationSessionEntry,
  catalog: InstrumentWithMetaDto[],
): InstrumentWithMetaDto {
  const fromCatalog = catalog.find((item) => item.id === entry.instrumentId);
  if (fromCatalog) return fromCatalog;

  return {
    id: entry.instrumentId,
    symbol: entry.symbol,
    yahooSymbol: entry.symbol,
    name: entry.name,
    exchange: '—',
    country: '—',
    currency: 'EUR',
    sector: null,
    isActive: true,
    meta: {
      barCount: 0,
      lastSync: null,
      lastClose: null,
      changePct: null,
    },
  };
}
