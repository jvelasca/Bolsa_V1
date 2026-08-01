import { describe, expect, it } from 'vitest';
import type { TrackerDefinitionDetailDto } from '@bolsa/shared';
import {
  hubExecutionModeShort,
  invertTrackersByInstrument,
  pickTrackerChips,
} from '@/features/instruments/instruments-hub-trackers';

function detail(
  partial: Partial<TrackerDefinitionDetailDto> & {
    id: string;
    name: string;
    universe: { listId?: string; instrumentIds?: string[] };
  },
): TrackerDefinitionDetailDto {
  return {
    strategyDefinitionId: 'st-1',
    timeframe: '1d',
    evaluationMode: 'bar_close',
    origin: 'assisted',
    enabled: true,
    updatedAt: '2026-07-31T00:00:00Z',
    createdAt: '2026-07-31T00:00:00Z',
    definition: {
      schemaVersion: 'tracker_definition_v1',
      name: partial.name,
      strategyDefinitionId: 'st-1',
      timeframe: '1d',
      universe: partial.universe,
      schedule: { kind: 'on_bar_close' },
      defaultExecutionPolicyId: 'pol-alert',
      evaluationMode: 'bar_close',
      origin: 'assisted',
      enabled: true,
      ...(partial.definition ?? {}),
    },
    ...partial,
  } as TrackerDefinitionDetailDto;
}

describe('instruments-hub-trackers', () => {
  it('maps mode shorts', () => {
    expect(hubExecutionModeShort('inform_only')).toBe('aviso');
    expect(hubExecutionModeShort('alert')).toBe('alerta');
    expect(hubExecutionModeShort('paper_auto')).toBe('auto');
  });

  it('covers pin and list memberships', () => {
    const memberships = new Map([
      [
        'inst-a',
        [{ listId: 'list-1', listName: 'IBEX', source: 'catalog' }],
      ],
      [
        'inst-b',
        [{ listId: 'list-1', listName: 'IBEX', source: 'catalog' }],
      ],
    ]);
    const policyModeById = new Map([['pol-alert', 'alert' as const]]);
    const map = invertTrackersByInstrument(
      [
        detail({
          id: 't-pin',
          name: 'Radar · SAN · #1',
          universe: { instrumentIds: ['inst-a'] },
        }),
        detail({
          id: 't-list',
          name: 'Radar lista IBEX',
          universe: { listId: 'list-1' },
        }),
      ],
      memberships,
      policyModeById,
    );

    expect(map.get('inst-a')?.map((c) => c.trackerId).sort()).toEqual(['t-list', 't-pin']);
    expect(map.get('inst-a')?.find((c) => c.trackerId === 't-pin')?.coverage).toBe('pin');
    expect(map.get('inst-b')?.map((c) => c.trackerId)).toEqual(['t-list']);
    expect(map.get('inst-a')?.[0]?.modeShort).toBe('alerta');
  });

  it('picks up to 3 chips', () => {
    const chips = [1, 2, 3, 4].map((n) => ({
      trackerId: `t${n}`,
      name: `T${n}`,
      timeframe: '1d',
      enabled: true,
      scheduleLabel: 'Manual',
      modeShort: 'aviso',
      mode: 'inform_only' as const,
      coverage: 'pin' as const,
    }));
    const { visible, overflow } = pickTrackerChips(chips, 3);
    expect(visible).toHaveLength(3);
    expect(overflow).toBe(1);
  });
});
