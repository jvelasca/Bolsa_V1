/**
 * Tests — mapa embudo 5 etapas.
 */

import { describe, expect, it } from 'vitest';
import {
  FUNNEL_STAGES,
  funnelPrefsLegend,
  resolveActiveFunnelStage,
  resolveFunnelStageStatus,
} from '@/features/backtests/assistant-funnel-map';
import { emptyAssistantProgress } from '@/features/backtests/backtest-assistant-completion';

describe('assistant-funnel-map', () => {
  it('has 5 product stages', () => {
    expect(FUNNEL_STAGES).toHaveLength(5);
    expect(funnelPrefsLegend()).toMatch(/1\. Probar.*5\. Finalistas/);
  });

  it('starts at probe', () => {
    expect(
      resolveActiveFunnelStage({
        progress: emptyAssistantProgress(),
        coachPass: 'initial',
        fullCycleActive: true,
      }),
    ).toBe('probe');
  });

  it('highlights revalidate on Coach² / awaiting ACK', () => {
    const progress = {
      ...emptyAssistantProgress(),
      universeDone: true,
      semifinalDone: true,
      labDone: true,
    };
    expect(
      resolveActiveFunnelStage({
        progress,
        coachPass: 'post_lab',
        fullCycleActive: true,
      }),
    ).toBe('revalidate');
    expect(
      resolveFunnelStageStatus('revalidate', {
        progress,
        coachPass: 'post_lab',
        fullCycleActive: true,
        awaitingAck: true,
      }),
    ).toBe('blocked');
  });

  it('highlights coach1 when awaiting ACK¹', () => {
    const progress = {
      ...emptyAssistantProgress(),
      universeDone: true,
    };
    expect(
      resolveActiveFunnelStage({
        progress,
        coachPass: 'initial',
        fullCycleActive: true,
        awaitingAck: true,
      }),
    ).toBe('coach1');
    expect(
      resolveFunnelStageStatus('coach1', {
        progress,
        coachPass: 'initial',
        fullCycleActive: true,
        awaitingAck: true,
      }),
    ).toBe('blocked');
  });

  it('marks finalists saved vs skipped', () => {
    const progress = {
      ...emptyAssistantProgress(),
      universeDone: true,
      semifinalDone: true,
      labDone: true,
      finalistsDone: true,
    };
    expect(
      resolveFunnelStageStatus('finalists', {
        progress,
        coachPass: 'post_lab',
        fullCycleActive: false,
        finalistsSaved: true,
      }),
    ).toBe('done');
    expect(
      resolveFunnelStageStatus('finalists', {
        progress,
        coachPass: 'post_lab',
        fullCycleActive: false,
        finalistsSkipped: true,
      }),
    ).toBe('skipped');
  });
});
