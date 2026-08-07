/**
 * Prioridad Cartera → Estudio → resto al resolver lista de una pestaña.
 */

import { describe, expect, it } from 'vitest';
import {
  ESTUDIO_LIST_ID,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
} from '@bolsa/shared';
import type { ChartTabState, WorkspaceDocument } from '@bolsa/shared';
import {
  resolvePreferredListIdForInstrument,
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

function membership(partial: Partial<ChartListMembershipSnapshot>): ChartListMembershipSnapshot {
  return {
    api: partial.api ?? {},
    listMeta: partial.listMeta ?? [],
    virtual: {
      visualization: partial.virtual?.visualization ?? new Set(),
      portfolio: partial.virtual?.portfolio ?? new Set(),
      pendingOrders: partial.virtual?.pendingOrders ?? new Set(),
    },
  };
}

describe('resolvePreferredListIdForInstrument', () => {
  const id = 'inst-1';

  it('prefers Cartera over Estudio and Visualizados', () => {
    expect(
      resolvePreferredListIdForInstrument(
        id,
        membership({
          api: { [ESTUDIO_LIST_ID]: new Set([id]), ibex35: new Set([id]) },
          listMeta: [
            { id: ESTUDIO_LIST_ID, source: 'custom' },
            { id: 'ibex35', source: 'catalog' },
          ],
          virtual: {
            visualization: new Set([id]),
            portfolio: new Set([id]),
            pendingOrders: new Set(),
          },
        }),
      ),
    ).toBe(VIRTUAL_LIST_PORTFOLIO);
  });

  it('prefers Estudio over Visualizados and IBEX', () => {
    expect(
      resolvePreferredListIdForInstrument(
        id,
        membership({
          api: { [ESTUDIO_LIST_ID]: new Set([id]), ibex35: new Set([id]) },
          listMeta: [
            { id: ESTUDIO_LIST_ID, source: 'custom' },
            { id: 'ibex35', source: 'catalog' },
          ],
          virtual: {
            visualization: new Set([id]),
            portfolio: new Set(),
            pendingOrders: new Set(),
          },
        }),
      ),
    ).toBe(ESTUDIO_LIST_ID);
  });

  it('falls back to Visualizados when not in Cartera/Estudio', () => {
    expect(
      resolvePreferredListIdForInstrument(
        id,
        membership({
          api: { ibex35: new Set([id]) },
          listMeta: [{ id: 'ibex35', source: 'catalog' }],
          virtual: {
            visualization: new Set([id]),
            portfolio: new Set(),
            pendingOrders: new Set(),
          },
        }),
        ['ibex35'],
      ),
    ).toBe('ibex35');
  });

  it('uses Visualizados when only there', () => {
    expect(
      resolvePreferredListIdForInstrument(
        id,
        membership({
          virtual: {
            visualization: new Set([id]),
            portfolio: new Set(),
            pendingOrders: new Set(),
          },
        }),
      ),
    ).toBe(VIRTUAL_LIST_VISUALIZATION);
  });
});

describe('resolveValidSourceListIdForTab', () => {
  it('prefers Cartera when instrument is in Cartera + Estudio + Visualizados', () => {
    const instrumentId = 'inst-san';
    const tab = {
      id: 'chart-1',
      instrumentId,
      label: 'SAN',
      sourceListId: VIRTUAL_LIST_VISUALIZATION,
    } as ChartTabState;

    const snap = membership({
      api: { [ESTUDIO_LIST_ID]: new Set([instrumentId]), ibex35: new Set([instrumentId]) },
      listMeta: [
        { id: ESTUDIO_LIST_ID, source: 'custom' },
        { id: 'ibex35', source: 'catalog' },
      ],
      virtual: {
        visualization: new Set([instrumentId]),
        portfolio: new Set([instrumentId]),
        pendingOrders: new Set(),
      },
    });

    const workspace = emptyWorkspace({
      charts: [tab],
      activeChartId: tab.id,
      chartListContext: { listId: VIRTUAL_LIST_VISUALIZATION, instrumentId },
    });

    expect(resolveValidSourceListIdForTab(workspace, tab, snap)).toBe(VIRTUAL_LIST_PORTFOLIO);
  });

  it('prefers Estudio over IBEX/Visualizados when not in Cartera', () => {
    const instrumentId = 'inst-san';
    const tab = {
      id: 'chart-1',
      instrumentId,
      label: 'SAN',
      sourceListId: 'ibex35',
    } as ChartTabState;

    const snap = membership({
      api: { [ESTUDIO_LIST_ID]: new Set([instrumentId]), ibex35: new Set([instrumentId]) },
      listMeta: [
        { id: ESTUDIO_LIST_ID, source: 'custom' },
        { id: 'ibex35', source: 'catalog' },
      ],
      virtual: {
        visualization: new Set([instrumentId]),
        portfolio: new Set(),
        pendingOrders: new Set(),
      },
    });

    const workspace = emptyWorkspace({
      charts: [tab],
      activeChartId: tab.id,
      chartListContext: { listId: 'ibex35', instrumentId },
    });

    expect(resolveValidSourceListIdForTab(workspace, tab, snap)).toBe(ESTUDIO_LIST_ID);
  });

  it('falls back to catalog when not in Cartera/Estudio', () => {
    const instrumentId = 'inst-tef';
    const tab = {
      id: 'chart-2',
      instrumentId,
      label: 'TEF',
      sourceListId: 'ibex35',
    } as ChartTabState;

    const snap = membership({
      api: { ibex35: new Set([instrumentId]) },
      listMeta: [{ id: 'ibex35', source: 'catalog' }],
    });

    const workspace = emptyWorkspace({
      charts: [tab],
      activeChartId: tab.id,
    });

    expect(resolveValidSourceListIdForTab(workspace, tab, snap)).toBe('ibex35');
  });
});
