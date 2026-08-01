import { describe, expect, it } from 'vitest';
import { canonicalMarketIndexCode } from '@bolsa/shared';

describe('market-indices aliases', () => {
  it('maps popular queries to canonical codes', () => {
    expect(canonicalMarketIndexCode('ibex35')).toBe('IBEX35');
    expect(canonicalMarketIndexCode('SP500')).toBe('SPX');
    expect(canonicalMarketIndexCode('s&p 500')).toBe('SPX');
    expect(canonicalMarketIndexCode('dax')).toBe('DAX');
    expect(canonicalMarketIndexCode('unknown-xyz')).toBeNull();
  });
});

describe('catalogListIdForIndex', () => {
  it('uses stable ids', async () => {
    const { catalogListIdForIndex } = await import('@bolsa/shared');
    expect(catalogListIdForIndex('IBEX35')).toBe('ibex35');
    expect(catalogListIdForIndex('SPX')).toBe('idx-spx');
  });
});
