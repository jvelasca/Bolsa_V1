import { describe, expect, it } from 'vitest';
import {
  cycleInstrumentsHubColumnSort,
  fitInstrumentsHubColumnsToContent,
  formatInstrumentLastBarLabel,
  normalizeInstrumentsHubColumnLayout,
  reorderInstrumentsHubColumns,
  resizeInstrumentsHubColumn,
  toggleInstrumentsHubColumn,
  toggleInstrumentsHubFavoriteColumn,
} from '@/features/instruments/instruments-hub-column-layout';

describe('instruments-hub-column-layout', () => {
  it('normalizes stored layout and keeps unknown order', () => {
    const normalized = normalizeInstrumentsHubColumnLayout([
      { id: 'lastBar', width: 200, visible: true },
      { id: 'symbol', width: 10, visible: true },
    ]);
    expect(normalized[0]?.id).toBe('lastBar');
    expect(normalized.find((c) => c.id === 'symbol')?.width).toBe(52);
    expect(normalized.some((c) => c.id === 'tracking')).toBe(true);
  });

  it('resizes, reorders and toggles visibility', () => {
    const base = normalizeInstrumentsHubColumnLayout(undefined);
    const resized = resizeInstrumentsHubColumn(base, 'price', 120);
    expect(resized.find((c) => c.id === 'price')?.width).toBe(120);

    const reordered = reorderInstrumentsHubColumns(resized, 'price', 'symbol');
    expect(reordered[0]?.id).toBe('price');

    const hidden = toggleInstrumentsHubColumn(reordered, 'coach');
    expect(hidden.find((c) => c.id === 'coach')?.visible).toBe(false);
    expect(toggleInstrumentsHubColumn(hidden, 'symbol')).toBe(hidden);
  });

  it('toggles favorites and cycles sort', () => {
    const favs = toggleInstrumentsHubFavoriteColumn(['symbol', 'price'], 'scoreFa');
    expect(favs).toContain('scoreFa');
    expect(cycleInstrumentsHubColumnSort(null, 'lastBar')).toEqual({
      columnId: 'lastBar',
      direction: 'desc',
    });
  });

  it('formats last bar with sync time when date-only', () => {
    const label = formatInstrumentLastBarLabel({
      lastBarDate: '2026-07-28',
      lastSyncAt: '2026-07-28T16:35:00Z',
    });
    expect(label.primary).toMatch(/28/);
    expect(label.primary).toMatch(/·/);
    expect(label.sortKey).toContain('2026-07-28');
  });

  it('fits column widths to content samples', () => {
    const base = normalizeInstrumentsHubColumnLayout(undefined);
    const fitted = fitInstrumentsHubColumnsToContent(base, {
      symbol: ['ACS Actividades de Construcción y Servicios'],
      scoreFa: ['88'],
    });
    const symbolW = fitted.find((c) => c.id === 'symbol')!.width;
    const faW = fitted.find((c) => c.id === 'scoreFa')!.width;
    expect(symbolW).toBeGreaterThan(base.find((c) => c.id === 'symbol')!.width - 1);
    expect(faW).toBeGreaterThanOrEqual(52);
  });
});
