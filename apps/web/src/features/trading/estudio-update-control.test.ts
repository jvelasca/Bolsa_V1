import { beforeEach, describe, expect, it } from 'vitest';
import {
  beginEstudioUpdateRun,
  clearEstudioUpdatePauseCheckpoint,
  clearEstudioUpdateSoftStop,
  getEstudioUpdatePauseCheckpoint,
  hasEstudioUpdatePauseCheckpoint,
  isEstudioUpdateSoftStopRequested,
  requestEstudioBannerSoftPause,
  requestEstudioUpdateSoftStop,
  settleEstudioUpdatePause,
} from '@/features/trading/estudio-update-control';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';

describe('estudio-update-control soft-stop', () => {
  beforeEach(() => {
    clearEstudioUpdateSoftStop();
    useListAutoActivityStore.getState().clear();
  });

  it('begin clears previous request', () => {
    requestEstudioUpdateSoftStop();
    expect(isEstudioUpdateSoftStopRequested()).toBe(true);
    beginEstudioUpdateRun();
    expect(isEstudioUpdateSoftStopRequested()).toBe(false);
  });

  it('announce uses current activity symbol', () => {
    useListAutoActivityStore.getState().publish({
      active: true,
      paused: false,
      listId: 'estudio',
      listName: 'Estudio',
      index: 2,
      total: 10,
      symbol: 'SAN',
      detail: 'Alta Estudio · SAN',
    });
    const { symbol } = requestEstudioUpdateSoftStop();
    expect(symbol).toBe('SAN');
    expect(isEstudioUpdateSoftStopRequested()).toBe(true);
  });
});

describe('estudio-update-control pause checkpoint', () => {
  beforeEach(() => {
    beginEstudioUpdateRun();
    clearEstudioUpdatePauseCheckpoint();
    useListAutoActivityStore.getState().clear();
  });

  it('no checkpoint antes de pausar', () => {
    expect(hasEstudioUpdatePauseCheckpoint()).toBe(false);
    expect(getEstudioUpdatePauseCheckpoint()).toBeNull();
  });

  it('settle guarda checkpoint y deja el store en pausa', () => {
    settleEstudioUpdatePause({
      ids: ['a', 'b', 'c'],
      nextIndex: 1,
      rediscover: false,
      phaseLabel: 'Actualizar',
      symbolOf: (id) => `SYM-${id}`,
    });

    const cp = getEstudioUpdatePauseCheckpoint();
    expect(cp).not.toBeNull();
    expect(cp).toMatchObject({
      ids: ['a', 'b', 'c'],
      nextIndex: 1,
      rediscover: false,
      phaseLabel: 'Actualizar',
    });
    expect(cp?.symbols).toEqual({ a: 'SYM-a', b: 'SYM-b', c: 'SYM-c' });
    expect(hasEstudioUpdatePauseCheckpoint()).toBe(true);

    const snap = useListAutoActivityStore.getState();
    expect(snap.paused).toBe(true);
    expect(snap.active).toBe(true);
    expect(snap.detail).toContain('Pausa');
    expect(snap.detail).toContain('SYM-b');
    expect(snap.detail).toContain('quedan 2');
  });

  it('nextIndex=length => falta Lab', () => {
    settleEstudioUpdatePause({
      ids: ['a', 'b'],
      nextIndex: 2,
      rediscover: false,
      phaseLabel: 'Actualizar',
      symbolOf: (id) => id,
    });
    expect(getEstudioUpdatePauseCheckpoint()?.nextIndex).toBe(2);
    expect(useListAutoActivityStore.getState().detail).toContain('falta Lab');
  });

  it('clear borra el checkpoint (tras reanudar/completar)', () => {
    settleEstudioUpdatePause({
      ids: ['a'],
      nextIndex: 1,
      rediscover: false,
      phaseLabel: 'Actualizar',
      symbolOf: (id) => id,
    });
    expect(hasEstudioUpdatePauseCheckpoint()).toBe(true);
    clearEstudioUpdatePauseCheckpoint();
    expect(hasEstudioUpdatePauseCheckpoint()).toBe(false);
    expect(getEstudioUpdatePauseCheckpoint()).toBeNull();
  });

  it('requestEstudioBannerSoftPause anuncia Termina… y queda pausado', () => {
    useListAutoActivityStore.getState().publish({
      active: true,
      paused: false,
      listId: 'estudio',
      listName: 'Estudio',
      index: 2,
      total: 10,
      symbol: 'SAN',
      detail: 'Actualizar · SAN',
    });
    const res = requestEstudioBannerSoftPause();
    expect(res.mode).toBe('update');
    expect(res.symbol).toBe('SAN');
    expect(isEstudioUpdateSoftStopRequested()).toBe(true);
    const snap = useListAutoActivityStore.getState();
    expect(snap.paused).toBe(true);
    expect(snap.detail).toBe('Termina SAN y para…');
  });
});
