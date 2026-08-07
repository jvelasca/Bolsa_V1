import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';
import {
  collectEstudioIdsNeedingUpdate,
  resumeEstudioInstrumentsUpdate,
  runEstudioInstrumentsUpdate,
} from '@/features/trading/estudio-instruments-update';
import {
  beginEstudioUpdateRun,
  clearEstudioUpdatePauseCheckpoint,
  clearEstudioUpdateSoftStop,
  getEstudioUpdatePauseCheckpoint,
  requestEstudioUpdateSoftStop,
} from '@/features/trading/estudio-update-control';
import { ESTUDIO_LANE_STAMPS_KEY } from '@/features/trading/estudio-lane-stamps';
import { ESTUDIO_SUPERVISION_KEY } from '@/features/trading/estudio-supervision';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';

vi.mock('@/lib/api', () => ({
  api: {
    syncInstrument: vi.fn(async () => ({
      data: { barsAdded: 1, status: 'ok' },
    })),
  },
}));

vi.mock('@/features/backtests/core-r-scheduler-tick', () => ({
  runCoreRSchedulerTick: vi.fn(async () => ({ ok: true })),
}));

vi.mock('@/features/trading/estudio-process-status', async () => {
  const actual =
    await vi.importActual<typeof import('@/features/trading/estudio-process-status')>(
      '@/features/trading/estudio-process-status',
    );
  return {
    ...actual,
    emitEstudioProcessRunning: vi.fn(),
    laneFromListAutoMode: (forceRescan: boolean) => (forceRescan ? 'rediscover' : 'freshness'),
  };
});

describe('collectEstudioIdsNeedingUpdate', () => {
  beforeEach(() => {
    localStorage.removeItem(ESTUDIO_LANE_STAMPS_KEY);
    localStorage.removeItem(ESTUDIO_SUPERVISION_KEY);
  });

  it('marks instruments without stamps as needing update', () => {
    const ids = collectEstudioIdsNeedingUpdate(['a', 'b']);
    expect(ids).toEqual(['a', 'b']);
  });
});

describe('runEstudioInstrumentsUpdate soft-stop / resume', () => {
  const onProgress = () => {};

  beforeEach(() => {
    localStorage.removeItem(ESTUDIO_LANE_STAMPS_KEY);
    beginEstudioUpdateRun();
    clearEstudioUpdatePauseCheckpoint();
    clearEstudioUpdateSoftStop();
    useListAutoActivityStore.getState().clear();
    vi.mocked(api.syncInstrument).mockClear();
  });

  afterEach(() => {
    clearEstudioUpdatePauseCheckpoint();
    clearEstudioUpdateSoftStop();
    useListAutoActivityStore.getState().clear();
  });

  it('PAUSA (soft-stop) tras un valor deja checkpoint y RETOMA desde ahí al reanudar', async () => {
    const ids = ['a', 'b', 'c'];
    const symbolOf = (id: string) => `SYM-${id}`;

    // Control determinista: bloquear la 1ª sync hasta que decidamos.
    let allowFirst: (() => void) | null = null;
    const firstGate = new Promise<void>((resolve) => (allowFirst = resolve));
    let calls = 0;
    vi.mocked(api.syncInstrument).mockImplementation(async (_id: string) => {
      calls += 1;
      if (calls === 1) await firstGate; // pausa el ciclo justo en "a"
      return { data: { barsAdded: 1, status: 'ok' } };
    });

    const resolving = runEstudioInstrumentsUpdate({
      instrumentIds: ids,
      rediscover: false,
      phaseLabel: 'Actualizar',
      symbolOf,
      onProgress,
    });

    // Dejamos que entre en el bucle y abra la 1ª sync (queda bloqueado por la gate).
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toBe(1);

    // El usuario pulsa PAUSA mientras el valor "a" está en curso.
    requestEstudioUpdateSoftStop();
    // Se libera "a": termina el valor en curso y debe cortar antes de "b".
    allowFirst?.();
    await resolving;

    // Solo "a" completada → checkpoint nextIndex=1.
    expect(calls).toBe(1);
    const paused = useListAutoActivityStore.getState();
    expect(paused.paused).toBe(true);
    expect(paused.active).toBe(true);
    expect(paused.symbol).toBe('SYM-b');
    expect(paused.detail).toContain('SYM-b');
    expect(paused.detail).toContain('quedan 2');

    // Reanudar desde el checkpoint: continúa sincronizando "b" y "c".
    await resumeEstudioInstrumentsUpdate();
    expect(calls).toBe(3);

    // Al completarse, el checkpoint se ha limpiado y no queda estado "paused".
    const final = useListAutoActivityStore.getState();
    expect(final.paused).toBe(false);
  });

  it('si el soft-stop llega tras completar el sync, deja checkpoint con nextIndex=length (falta vigilia/Lab)', async () => {
    const ids = ['a', 'b'];
    beginEstudioUpdateRun();
    clearEstudioUpdateSoftStop();

    // Gates por valor para un control determinista sobre el punto exacto de pausa.
    const gates: Array<() => void> = [];
    let calls = 0;
    vi.mocked(api.syncInstrument).mockImplementation(async (_id: string) => {
      const idx = calls;
      calls += 1;
      await new Promise<void>((resolve) => {
        gates[idx] = resolve;
      });
      return { data: { barsAdded: 1, status: 'ok' } };
    });

    const running = runEstudioInstrumentsUpdate({
      instrumentIds: ids,
      rediscover: true,
      phaseLabel: 'Redescubrir',
      symbolOf: (id) => `SYM-${id}`,
    });

    // "a" en curso → liberar para completar el sync de "a" y entrar en "b".
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toBe(1);
    gates[0]?.();
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toBe(2); // "b" en curso

    // PAUSA mientras aún no se completó el sync de "b": al liberarla, la tanda
    // completa "b", entra en vigilia y detecta el soft-stop ahí → rightIndex=length.
    requestEstudioUpdateSoftStop();
    gates[1]?.();
    await running;

    expect(calls).toBe(2); // sync completo de ambos
    const cp = getEstudioUpdatePauseCheckpoint();
    expect(cp).not.toBeNull();
    expect(cp?.nextIndex).toBe(2); // nextIndex=length => falta vigilia/Lab
    const snap = useListAutoActivityStore.getState();
    expect(snap.paused).toBe(true);
  });

  it('sobreescritura: no arranca una segunda tanda si ya hay actividad Estudio activa no pausada', async () => {
    useListAutoActivityStore.getState().publish({
      active: true,
      paused: false,
      listId: 'estudio',
      listName: 'Estudio',
      index: 0,
      total: 2,
      symbol: 'A',
      detail: 'Actualizar · A',
    });

    await runEstudioInstrumentsUpdate({
      instrumentIds: ['x', 'y'],
      rediscover: false,
      phaseLabel: 'Actualizar',
      symbolOf: (id) => id,
    });

    expect(vi.mocked(api.syncInstrument)).not.toHaveBeenCalled();
  });
});
