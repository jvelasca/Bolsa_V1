import { describe, expect, it } from 'vitest';
import {
  resolveSupervisedQueueOrigin,
  supervisedQueueOriginLabel,
} from '@/stores/supervised-f3-queue-store';

describe('resolveSupervisedQueueOrigin', () => {
  it('prefers explicit origin', () => {
    expect(
      resolveSupervisedQueueOrigin({
        origin: 'finalists',
        scanId: 'scan-1',
        payload: { source: 'x' } as never,
      }),
    ).toBe('finalists');
  });

  it('detects finalists from payload.source or legacy scanId prefix', () => {
    expect(
      resolveSupervisedQueueOrigin({
        payload: { source: 'finalists' } as never,
      }),
    ).toBe('finalists');
    expect(
      resolveSupervisedQueueOrigin({
        scanId: 'finalists:inst-1',
        payload: {} as never,
      }),
    ).toBe('finalists');
  });

  it('labels scan vs manual', () => {
    expect(
      resolveSupervisedQueueOrigin({
        scanId: 'abc',
        payload: {} as never,
      }),
    ).toBe('scan');
    expect(resolveSupervisedQueueOrigin({ payload: {} as never })).toBe('manual');
    expect(supervisedQueueOriginLabel('finalists')).toBe('Finalistas');
    expect(supervisedQueueOriginLabel('scan')).toBe('Scan');
  });

  it('resolves alarm origin from source or meta', () => {
    expect(
      resolveSupervisedQueueOrigin({
        origin: 'alarm',
        payload: {} as never,
      }),
    ).toBe('alarm');
    expect(
      resolveSupervisedQueueOrigin({
        payload: { source: 'alarm' } as never,
      }),
    ).toBe('alarm');
    expect(supervisedQueueOriginLabel('alarm')).toBe('Alarma Radar');
  });
});
