import { describe, expect, it } from 'vitest';
import {
  conflictForActive,
  findHmConflicts,
} from '@/features/trading/semi-hm-conflict';
import type { SupervisedQueueItem } from '@/stores/supervised-f3-queue-store';

function item(
  id: string,
  instrumentId: string,
  origin: 'finalists' | 'alarm' | 'manual',
  action = 'recommend_long',
): SupervisedQueueItem {
  return {
    id,
    enqueuedAt: '2026-08-03T12:00:00.000Z',
    origin,
    symbol: instrumentId === 'inst-a' ? 'ACS.MC' : 'SAN.MC',
    payload: {
      artifactType: 'ART-RECOMMENDATION',
      schemaVersion: '1.0.0',
      recommendationId: `REC-${id}`,
      decisionId: `DEC-${id}`,
      instrumentId,
      action: action as 'recommend_long',
      suggestedQuantity: 1,
      metrics: {
        confidence: 0.5,
        consensus: 0.5,
        evidenceStrength: 0.5,
        stability: 0.5,
        conviction: 0.5,
      },
      status: 'awaiting_human',
      createdAt: '2026-08-03T12:00:00.000Z',
      source: origin,
    },
  };
}

describe('semi-hm-conflict', () => {
  it('pairs Finalistas + Alarm on same instrument', () => {
    const pairs = findHmConflicts([
      item('h1', 'inst-a', 'finalists'),
      item('m1', 'inst-a', 'alarm', 'wait'),
      item('x', 'inst-b', 'manual'),
    ]);
    expect(pairs).toHaveLength(1);
    expect(pairs[0].h.id).toBe('h1');
    expect(pairs[0].m.id).toBe('m1');
    expect(pairs[0].symbol).toBe('ACS.MC');
  });

  it('resolves conflict for active queue item', () => {
    const pairs = findHmConflicts([
      item('h1', 'inst-a', 'finalists'),
      item('m1', 'inst-a', 'alarm'),
    ]);
    expect(conflictForActive(pairs, 'm1')?.h.id).toBe('h1');
    expect(conflictForActive(pairs, 'other')).toBeNull();
  });
});
