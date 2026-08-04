/**
 * Preferencia Estudio al resolver lista de una pestaña de gráfico.
 */

import { describe, expect, it } from 'vitest';
import { VIRTUAL_LIST_VISUALIZATION } from '@bolsa/shared';
import type { ChartTabState, WorkspaceDocument } from '@bolsa/shared';
import {
  resolveValidSourceListIdForTab,
  type ChartListMembershipSnapshot,
} from '@/lib/chart-list-membership';

function emptyWorkspace(overrides: Partial<WorkspaceDocument> = {}): WorkspaceDocument {
  return {
    version: 1,
    id: 'ws',
    name: 'test',
    charts: [],
    activeChartId: null,
    list: {
      id: 'ibex35',
      apiListId: 'ibex35',
      name: 'IBEX 35',
      source: 'catalog',
    },
    preferences: {} as WorkspaceDocument['preferences'],
    chartListContext: null,
    chartStateByListInstrument: {},
    ...overrides,
  } as WorkspaceDocument;
}

describe('resolveValidSourceListIdForTab', () => {
  it('prefers Estudio over IBEX when the instrument is in both', () => {
    const instrumentId = 'inst-san';
    const tab = {
      id: 'chart-1',
      instrumentId,
      label: 'SAN',
      sourceListId: 'ibex35',
    } as ChartTabState;

    const membership: ChartListMembershipSnapshot = {
      api: { ibex35: new Set([instrumentId]) },
      listMeta: [{ id: 'ibex35', source: 'catalog' }],
      virtual: {
        visualization: new Set([instrumentId]),
        portfolio: new Set(),
        pendingOrders: new Set(),
      },
    };

    const workspace = emptyWorkspace({
      charts: [tab],
      activeChartId: tab.id,
      chartListContext: { listId: 'ibex35', instrumentId },
      list: {
        id: 'ibex35',
        apiListId: 'ibex35',
        name: 'IBEX 35',
        source: 'catalog',
      } as WorkspaceDocument['list'],
    });

    expect(resolveValidSourceListIdForTab(workspace, tab, membership)).toBe(
      VIRTUAL_LIST_VISUALIZATION,
    );
  });

  it('falls back to catalog when not in Estudio', () => {
    const instrumentId = 'inst-tef';
    const tab = {
      id: 'chart-2',
      instrumentId,
      label: 'TEF',
      sourceListId: 'ibex35',
    } as ChartTabState;

    const membership: ChartListMembershipSnapshot = {
      api: { ibex35: new Set([instrumentId]) },
      listMeta: [{ id: 'ibex35', source: 'catalog' }],
      virtual: {
        visualization: new Set(),
        portfolio: new Set(),
        pendingOrders: new Set(),
      },
    };

    const workspace = emptyWorkspace({
      charts: [tab],
      activeChartId: tab.id,
    });

    expect(resolveValidSourceListIdForTab(workspace, tab, membership)).toBe('ibex35');
  });
});
