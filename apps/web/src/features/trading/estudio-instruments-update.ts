/**
 * Actualizar / Redescubrir sobre ids de Estudio (velas → vigilia → Lab).
 *
 * - **Actualizar** (`rediscover: false`): sync OHLCV + CORE-R force + tick frescura Lab.
 * - **Redescubrir** (`rediscover: true`): igual con `forceRescan` (embudo completo).
 * - Pausa suave: termina el valor en curso → checkpoint + barra en pausa (▶ reanuda).
 * - Tras emitir Lab: deja keep-alive activo para no desmontar BacktestsPage.
 *
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 */

import { ESTUDIO_LIST_ID } from "@bolsa/shared";
import { api } from "@/lib/api";
import {
  emitEstudioProcessRunning,
  laneFromListAutoMode,
  resolveEstudioProcessStatus,
} from "@/features/trading/estudio-process-status";
import { emitEstudioLaneTick } from "@/features/trading/estudio-supervision";
import { loadEstudioSupervisionPrefs } from "@/features/trading/estudio-supervision";
import { touchEstudioLaneStamps } from "@/features/trading/estudio-lane-stamps";
import {
  beginEstudioUpdateRun,
  clearEstudioUpdatePauseCheckpoint,
  clearEstudioUpdateSoftStop,
  getEstudioUpdatePauseCheckpoint,
  isEstudioUpdateSoftStopRequested,
  settleEstudioUpdatePause,
} from "@/features/trading/estudio-update-control";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";

export type EstudioUpdateProgress = {
  current: number;
  total: number;
  label: string;
};

export type RunEstudioInstrumentsUpdateOpts = {
  instrumentIds: readonly string[];
  /** true = Redescubrir (forceRescan); false = Actualizar ligero. */
  rediscover: boolean;
  /** Prefijo de fase en progreso / keep-alive (p. ej. «Alta Estudio»). */
  phaseLabel?: string;
  symbolOf?: (instrumentId: string) => string;
  onProgress?: (progress: EstudioUpdateProgress | null) => void;
  /** Continuar desde índice (reanudar pausa). */
  startIndex?: number;
  /** No resetear checkpoint al empezar (reanudación). */
  resume?: boolean;
};

/** Ids con vigilia/frescura vacía o caducada (candidatos a Actualizar automático). */
export function collectEstudioIdsNeedingUpdate(
  instrumentIds: readonly string[],
): string[] {
  const prefs = loadEstudioSupervisionPrefs();
  const nowMs = Date.now();
  const out: string[] = [];
  for (const id of instrumentIds) {
    if (!id) continue;
    const view = resolveEstudioProcessStatus({
      instrumentId: id,
      prefs,
      nowMs,
    });
    const needs = view.lanes.some(
      (lane) =>
        (lane.id === "vigilance" || lane.id === "freshness") &&
        (lane.state === "empty" || lane.state === "stale"),
    );
    if (needs) out.push(id);
  }
  return out;
}

/**
 * Reanuda un Actualizar/alta dejado en pausa (checkpoint).
 * @returns true si había checkpoint y se reanudó.
 */
export async function resumeEstudioInstrumentsUpdate(opts?: {
  onProgress?: (progress: EstudioUpdateProgress | null) => void;
}): Promise<boolean> {
  const cp = getEstudioUpdatePauseCheckpoint();
  if (!cp) return false;
  clearEstudioUpdatePauseCheckpoint();
  // Quitar estado paused para que el guard de solape no bloquee.
  useListAutoActivityStore.getState().publish({
    active: true,
    paused: false,
    listId: ESTUDIO_LIST_ID,
    listName: "Estudio",
    index: Math.max(0, cp.nextIndex),
    total: Math.max(cp.ids.length, 1),
    symbol:
      cp.symbols[cp.ids[cp.nextIndex] ?? ""] ??
      cp.symbols[cp.ids[0] ?? ""] ??
      "…",
    detail: `${cp.phaseLabel} · reanudando…`,
  });
  await runEstudioInstrumentsUpdate({
    instrumentIds: cp.ids,
    rediscover: cp.rediscover,
    phaseLabel: cp.phaseLabel,
    symbolOf: (id) => cp.symbols[id] ?? id.slice(0, 8),
    onProgress: opts?.onProgress,
    startIndex: cp.nextIndex,
    resume: true,
  });
  return true;
}

/**
 * Pasada Actualizar/Redescubrir. No pide confirmación (el caller lo hace si hace falta).
 */
export async function runEstudioInstrumentsUpdate(
  opts: RunEstudioInstrumentsUpdateOpts,
): Promise<void> {
  const ids = [...opts.instrumentIds].filter(Boolean);
  if (ids.length === 0) return;

  const snap0 = useListAutoActivityStore.getState();
  // Solapar solo si hay trabajo activo no pausado (la pausa con checkpoint se reanuda aparte).
  if (
    snap0.active &&
    snap0.listId === ESTUDIO_LIST_ID &&
    !snap0.paused &&
    !opts.resume
  ) {
    return;
  }
  if (snap0.active && snap0.paused && !opts.resume) {
    return;
  }

  if (!opts.resume) {
    beginEstudioUpdateRun();
  } else {
    clearEstudioUpdateSoftStop();
  }

  const rediscover = opts.rediscover;
  const lane = laneFromListAutoMode(rediscover);
  const phase = opts.phaseLabel ?? (rediscover ? "Redescubrir" : "Actualizar");
  const symbolOf = opts.symbolOf ?? ((id: string) => id.slice(0, 8));
  const startIndex = Math.max(0, Math.min(opts.startIndex ?? 0, ids.length));

  const publishKeepAlive = (index: number, detail: string, paused = false) => {
    useListAutoActivityStore.getState().publish({
      active: true,
      paused,
      listId: ESTUDIO_LIST_ID,
      listName: "Estudio",
      index,
      total: ids.length,
      symbol: symbolOf(ids[index] ?? ids[0] ?? ""),
      detail,
    });
  };

  const setProgress = (progress: EstudioUpdateProgress | null) => {
    opts.onProgress?.(progress);
  };

  const announceSoftStop = (index: number, sym: string) => {
    const label = `Termina ${sym} y para…`;
    setProgress({
      current: index + 1,
      total: ids.length,
      label,
    });
    publishKeepAlive(index, label, true);
  };

  let handedOffToLab = false;
  let settledPause = false;

  try {
    if (startIndex < ids.length) {
      setProgress({
        current: startIndex,
        total: ids.length,
        label: `${phase} · sync…`,
      });
      publishKeepAlive(startIndex, `${phase} · velas…`);
    }

    const completedBefore = ids.slice(0, startIndex);
    const completed: string[] = [...completedBefore];
    let stoppedEarly = false;

    for (let i = startIndex; i < ids.length; i++) {
      const id = ids[i]!;
      const sym = symbolOf(id);

      if (
        isEstudioUpdateSoftStopRequested() &&
        completed.length > completedBefore.length
      ) {
        stoppedEarly = true;
        break;
      }

      if (isEstudioUpdateSoftStopRequested()) {
        announceSoftStop(i, sym);
      } else {
        setProgress({
          current: i + 1,
          total: ids.length,
          label: `${phase} · ${sym}`,
        });
        publishKeepAlive(i, `${phase} · ${sym}`);
      }

      emitEstudioProcessRunning({ instrumentId: id, lane: "freshness" });
      try {
        await api.syncInstrument(id, 5);
      } catch {
        // seguir
      }
      completed.push(id);

      if (isEstudioUpdateSoftStopRequested()) {
        announceSoftStop(i, sym);
        stoppedEarly = true;
        break;
      }
    }

    if (completed.length === 0) {
      emitEstudioProcessRunning({ instrumentId: null, lane: null });
      return;
    }

    const freshlySynced = completed.slice(completedBefore.length);
    if (freshlySynced.length > 0) {
      touchEstudioLaneStamps(
        freshlySynced,
        rediscover ? "rediscover" : "freshness",
      );
    }

    if (stoppedEarly || isEstudioUpdateSoftStopRequested()) {
      settleEstudioUpdatePause({
        ids,
        nextIndex: completed.length,
        rediscover,
        phaseLabel: phase,
        symbolOf,
      });
      settledPause = true;
      setProgress({
        current: completed.length,
        total: ids.length,
        label: useListAutoActivityStore.getState().detail ?? "Pausa",
      });
      emitEstudioProcessRunning({ instrumentId: null, lane: null });
      return;
    }

    setProgress({
      current: ids.length,
      total: ids.length,
      label: `${phase} · vigilia…`,
    });
    emitEstudioProcessRunning({
      instrumentId: completed[0] ?? null,
      lane: "vigilance",
    });
    try {
      const { runCoreRSchedulerTick } =
        await import("@/features/backtests/core-r-scheduler-tick");
      await runCoreRSchedulerTick({ force: true, includePnl: true });
    } catch {
      // best-effort
    }
    touchEstudioLaneStamps(completed, "vigilance");

    if (isEstudioUpdateSoftStopRequested()) {
      // Sync completo; al reanudar solo falta vigilia/Lab (nextIndex = length).
      settleEstudioUpdatePause({
        ids,
        nextIndex: ids.length,
        rediscover,
        phaseLabel: phase,
        symbolOf,
      });
      settledPause = true;
      setProgress({
        current: ids.length,
        total: ids.length,
        label: useListAutoActivityStore.getState().detail ?? "Pausa",
      });
      emitEstudioProcessRunning({ instrumentId: null, lane: null });
      return;
    }

    setProgress({
      current: ids.length,
      total: ids.length,
      label: `${phase} · Lab…`,
    });
    publishKeepAlive(Math.max(0, completed.length - 1), `${phase} · Lab…`);
    emitEstudioProcessRunning({ instrumentId: completed[0] ?? null, lane });
    emitEstudioLaneTick({
      listId: ESTUDIO_LIST_ID,
      lane: rediscover ? "rediscover" : "freshness",
      forceRescan: rediscover,
      skipConfirm: true,
      instrumentIds: completed,
      at: new Date().toISOString(),
    });
    handedOffToLab = true;
    clearEstudioUpdatePauseCheckpoint();
  } finally {
    clearEstudioUpdateSoftStop();
    if (!settledPause) {
      setProgress(null);
    }
    if (!handedOffToLab && !settledPause) {
      const snap = useListAutoActivityStore.getState();
      const detail = snap.detail ?? "";
      if (
        snap.active &&
        snap.listId === ESTUDIO_LIST_ID &&
        (detail.startsWith("Actualizar") ||
          detail.startsWith("Redescubrir") ||
          detail.startsWith("Alta Estudio") ||
          detail.startsWith("Termina "))
      ) {
        snap.clear();
      }
      emitEstudioProcessRunning({ instrumentId: null, lane: null });
    }
  }
}
