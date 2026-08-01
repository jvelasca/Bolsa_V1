/**
 * Tests — archivo local Evidence DÍA D.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import type { DiaDSessionEvidenceV1 } from '@/features/trading/dia-d-session-evidence';
import {
  DIA_D_EVIDENCE_ARCHIVE_KEY,
  useDiaDEvidenceArchiveStore,
} from '@/stores/dia-d-evidence-archive-store';

const evidence: DiaDSessionEvidenceV1 = {
  schemaVersion: 'dia_d_session_evidence_v1',
  band: 'mixed',
  confidence: 'MEDIUM',
  claims: ['c1'],
  warnings: [],
  metrics: {
    mode: 'semi',
    returnPct: 5,
    maxDrawdownPct: 4,
    tradeCount: 2,
    finalEquity: 10_500,
    autoReturnPct: 8,
    returnDeltaVsAutoPct: -3,
    accepted: 2,
    rejected: 1,
  },
  paragraphs: ['p1', 'p2', 'p3'],
  disclaimer: 'sandbox',
};

describe('dia-d-evidence-archive-store', () => {
  beforeEach(() => {
    localStorage.removeItem(DIA_D_EVIDENCE_ARCHIVE_KEY);
    useDiaDEvidenceArchiveStore.setState({ items: [] });
  });

  it('saves and dedupes by instrument+window+mode', () => {
    const store = useDiaDEvidenceArchiveStore.getState();
    store.save({
      instrumentId: 'inst-1',
      symbol: 'ACS',
      strategyLabel: 'SMA',
      mode: 'semi',
      diaD: '2024-01-01',
      endDate: '2024-12-31',
      researchEvidenceId: null,
      engine: 'heuristic',
      evidence,
    });
    store.save({
      instrumentId: 'inst-1',
      symbol: 'ACS',
      strategyLabel: 'SMA',
      mode: 'semi',
      diaD: '2024-01-01',
      endDate: '2024-12-31',
      researchEvidenceId: 'ev-9',
      engine: 'heuristic',
      evidence: { ...evidence, band: 'favorable' },
    });
    expect(store.forInstrument('inst-1')).toHaveLength(1);
    expect(useDiaDEvidenceArchiveStore.getState().items[0]?.researchEvidenceId).toBe(
      'ev-9',
    );
    expect(useDiaDEvidenceArchiveStore.getState().items[0]?.evidence.band).toBe(
      'favorable',
    );
  });

  it('removes by id', () => {
    const store = useDiaDEvidenceArchiveStore.getState();
    const a = store.save({
      id: 'dde-keep-a',
      instrumentId: 'inst-1',
      symbol: 'ACS',
      strategyLabel: 'SMA',
      mode: 'auto',
      diaD: '2024-01-01',
      endDate: '2024-06-01',
      researchEvidenceId: null,
      engine: 'heuristic',
      evidence,
    });
    store.save({
      id: 'dde-keep-b',
      instrumentId: 'inst-1',
      symbol: 'ACS',
      strategyLabel: 'SMA',
      mode: 'semi',
      diaD: '2024-01-01',
      endDate: '2024-06-01',
      researchEvidenceId: null,
      engine: 'heuristic',
      evidence,
    });
    expect(useDiaDEvidenceArchiveStore.getState().forInstrument('inst-1')).toHaveLength(2);
    useDiaDEvidenceArchiveStore.getState().remove(a.id);
    const left = useDiaDEvidenceArchiveStore.getState().items;
    expect(left).toHaveLength(1);
    expect(left[0]?.mode).toBe('semi');
  });
});
