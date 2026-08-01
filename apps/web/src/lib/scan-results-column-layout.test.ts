import { describe, expect, it } from 'vitest';
import type { ScanHitDto } from '@bolsa/shared';
import { sortScanHits } from '@/lib/scan-results-column-layout';

function hit(partial: Partial<ScanHitDto> & Pick<ScanHitDto, 'symbol'>): ScanHitDto {
  return {
    instrumentId: partial.instrumentId ?? partial.symbol,
    name: partial.name ?? partial.symbol,
    signal: partial.signal ?? {
      id: 's1',
      instrumentId: partial.symbol,
      timestamp: '2026-01-01',
      kind: 'entry_long',
      price: 10,
      barIndex: 0,
      strategyDefinitionId: 'x',
      strategyVersion: 1,
    },
    ...partial,
  };
}

describe('sortScanHits', () => {
  it('sorts by rating desc', () => {
    const hits = [
      hit({ symbol: 'A', aiScore: 50 }),
      hit({ symbol: 'B', aiScore: 80 }),
    ];
    const sorted = sortScanHits(hits, { columnId: 'rating', direction: 'desc' });
    expect(sorted.map((row) => row.symbol)).toEqual(['B', 'A']);
  });

  it('sorts by symbol asc', () => {
    const hits = [hit({ symbol: 'ZZZ' }), hit({ symbol: 'AAA' })];
    const sorted = sortScanHits(hits, { columnId: 'symbol', direction: 'asc' });
    expect(sorted.map((row) => row.symbol)).toEqual(['AAA', 'ZZZ']);
  });
});

describe('toggleScanResultsFavoriteColumn', () => {
  it('toggles favorite columns preserving order', async () => {
    const { toggleScanResultsFavoriteColumn, DEFAULT_SCAN_RESULTS_FAVORITE_COLUMN_IDS } =
      await import('@/lib/scan-results-column-layout');
    const next = toggleScanResultsFavoriteColumn(DEFAULT_SCAN_RESULTS_FAVORITE_COLUMN_IDS, 'quality');
    expect(next).toContain('quality');
    const removed = toggleScanResultsFavoriteColumn(next, 'signal');
    expect(removed).not.toContain('signal');
  });
});
