/**
 * Tests — Mapa IA / tracker producto.
 */

import { describe, expect, it } from 'vitest';
import {
  AI_PRINCIPLE,
  AI_PRODUCT_FROZEN,
  AI_PRODUCT_GOALS,
  AI_PRODUCT_NEXT,
  AI_WHERE_KIND_LABEL,
  AI_WHERE_MAP,
} from '@/features/settings/ai-platform-tracker';

describe('ai-platform-tracker · Mapa IA', () => {
  it('covers Coach, Lab, Lista AUTO, F3 and drafts without LLM ranking', () => {
    const ids = AI_WHERE_MAP.map((row) => row.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'coach-stars',
        'coach-llm',
        'lab-optimize',
        'list-auto',
        'strategy-draft',
        'supervised-f3',
        'paper-auto-b',
        'value-analysis',
      ]),
    );
    expect(AI_WHERE_MAP).toHaveLength(8);
    for (const kind of Object.keys(AI_WHERE_KIND_LABEL)) {
      expect(AI_WHERE_MAP.some((row) => row.kind === kind)).toBe(true);
    }
    const coach = AI_WHERE_MAP.find((row) => row.id === 'coach-stars');
    expect(coach?.kind).toBe('local');
    expect(coach?.rankingOrOrders).toMatch(/local/i);
    expect(coach?.rankingOrOrders).toMatch(/no escribe TOP/i);
    const lab = AI_WHERE_MAP.find((row) => row.id === 'lab-optimize');
    expect(lab?.kind).toBe('deterministic');
    expect(lab?.rankingOrOrders).toMatch(/No es LLM/i);
  });

  it('marks goals done vs partial; NEXT and FROZEN lists', () => {
    const mapGoal = AI_PRODUCT_GOALS.find((g) => g.id === 'goal-ai-map');
    expect(mapGoal?.status).toBe('done');
    expect(mapGoal?.how).toMatch(/Dónde usamos IA/i);
    expect(AI_PRODUCT_GOALS.find((g) => g.id === 'goal-coach-at')?.status).toBe('done');
    expect(AI_PRODUCT_GOALS.find((g) => g.id === 'goal-lab-at')?.status).toBe('done');
    expect(AI_PRODUCT_GOALS.find((g) => g.id === 'goal-core-r')?.status).toBe('done');
    const coreP = AI_PRODUCT_GOALS.find((g) => g.id === 'goal-profile-coach');
    expect(coreP?.status).toBe('done');
    expect(coreP?.how).toMatch(/soft-bias|E2E live|familias|mismatch/i);
    expect(AI_PRODUCT_NEXT.join(' ')).toMatch(/BETA1|Smoke UI|runbook/i);
    expect(AI_PRODUCT_FROZEN.join(' ')).toMatch(/Belief|P3–P9|PAPER_D|multi-dispositivo/i);
    expect(AI_PRINCIPLE.body).toMatch(/nunca envía órdenes/i);
  });
});
