import { describe, expect, it } from 'vitest';
import {
  ALL_LIST_COLUMNS,
  normalizeColumnLayout,
  RECOMMENDATION_OPTIONAL_LIST_COLUMNS,
} from '@bolsa/shared';

describe('recommendation list columns', () => {
  it('includes recommendation columns in ALL_LIST_COLUMNS', () => {
    for (const id of RECOMMENDATION_OPTIONAL_LIST_COLUMNS) {
      expect(ALL_LIST_COLUMNS).toContain(id);
    }
  });

  it('normalizeColumnLayout appends recommendation columns hidden by default', () => {
    const layout = normalizeColumnLayout([
      { id: 'symbol', width: 56, visible: true },
      { id: 'lastClose', width: 64, visible: true },
    ]);
    for (const id of RECOMMENDATION_OPTIONAL_LIST_COLUMNS) {
      const col = layout.find((c) => c.id === id);
      expect(col).toBeTruthy();
      expect(col!.visible).toBe(false);
    }
  });
});
