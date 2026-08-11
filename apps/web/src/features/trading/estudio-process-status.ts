/**
 * Estado por capa de supervisión (vigilia / frescura / rediscubrimiento) por instrumento.
 *
 * Usado por: columna «Procesos», subtítulo bajo el nombre (`summarizeEstudioProcessLanes`),
 * timestamps opcionales Últ. Lab / Últ. CORE-R, y tooltips (`ESTUDIO_LANE_PURPOSE`).
 *
 * Combina Finalists freshness + cola CORE-R + sellos `estudio-lane-stamps`.
 *
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 */

import {
  formatEstudioCadenceMinutes,
  loadEstudioSupervisionPrefs,
  type EstudioLane,
  type EstudioSupervisionPrefs,
} from "@/features/trading/estudio-supervision";
import {
  loadLocalFinalistsFreshnessMap,
  type LocalFreshnessEntry,
} from "@/features/backtests/backtest-finalists-freshness";
import {
  maxIso,
  readEstudioLaneStamp,
} from "@/features/trading/estudio-lane-stamps";
import { useCoreRReviewQueueStore } from "@/stores/core-r-review-queue-store";

export type EstudioProcessLaneId = "vigilance" | "freshness" | "rediscover";

export type EstudioProcessLaneState = "ok" | "stale" | "empty" | "running";

export type EstudioProcessLaneView = {
  id: EstudioProcessLaneId;
  label: string;
  state: EstudioProcessLaneState;
  lastAt: string | null;
  cadenceMinutes: number;
  title: string;
};

/** Qué supervisa cada capa (tooltip 1ª línea). */
export const ESTUDIO_LANE_PURPOSE: Record<EstudioProcessLaneId, string> = {
  vigilance:
    "Vigilia: supervisa mandato operativo y PnL paper (juicios CORE-R). No sincroniza velas ni corre el embudo Lab.",
  freshness:
    "Frescura: comprueba si Finalistas / TOP siguen válidos (Lista AUTO; puede omitir si no cambió).",
  rediscover:
    "Redescubrir: embudo completo para buscar otra estrategia (caro; usa presupuesto).",
};

/** Qué acción del usuario actualiza cada capa. */
export const ESTUDIO_LANE_HOW_UPDATED: Record<EstudioProcessLaneId, string> = {
  vigilance:
    "Cómo actualizar: Supervisión ON · Auto-sync CORE-R · o «Actualizar» (dispara vigilia + Lab).",
  freshness:
    "Cómo actualizar: Supervisión ON · Lista AUTO · o botón «Actualizar» (velas + frescura).",
  rediscover:
    "Cómo actualizar: cadencia lenta · botón «Redescubrir» (costoso) · o Reevaluar embudo.",
};

export type EstudioProcessStatusView = {
  instrumentId: string;
  lanes: EstudioProcessLaneView[];
  lastLabAt: string | null;
  lastCoreRAt: string | null;
};

export const ESTUDIO_PROCESS_RUNNING_EVENT = "bolsa-estudio-process-running";

export type EstudioProcessRunningDetail = {
  instrumentId: string | null;
  lane: EstudioProcessLaneId | EstudioLane | null;
};

const LANE_LABEL: Record<EstudioProcessLaneId, string> = {
  vigilance: "Vigilia",
  freshness: "Frescura",
  rediscover: "Redescubrir",
};

function stateLabel(state: EstudioProcessLaneState): string {
  switch (state) {
    case "ok":
      return "al día";
    case "stale":
      return "toca actualizar";
    case "empty":
      return "sin registro";
    case "running":
      return "en curso";
  }
}

function formatShortAt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pickLatestLocalLabAt(
  instrumentId: string,
  map: Record<string, LocalFreshnessEntry>,
): string | null {
  let best: string | null = null;
  let bestMs = -1;
  for (const [key, entry] of Object.entries(map)) {
    if (!key.startsWith(`${instrumentId}|`)) continue;
    const at = entry.lastSearchAt;
    if (!at) continue;
    const ms = Date.parse(at);
    if (!Number.isFinite(ms)) continue;
    if (ms > bestMs) {
      bestMs = ms;
      best = at;
    }
  }
  return best;
}

export function latestCoreRAtForInstrument(
  instrumentId: string,
): string | null {
  const items = useCoreRReviewQueueStore.getState().items;
  let best: string | null = null;
  let bestMs = -1;
  for (const item of items) {
    if (item.instrumentId !== instrumentId) continue;
    const ms = Date.parse(item.enqueuedAt);
    if (!Number.isFinite(ms)) continue;
    if (ms > bestMs) {
      bestMs = ms;
      best = item.enqueuedAt;
    }
  }
  return best;
}

export function resolveLaneState(
  lastAt: string | null,
  cadenceMinutes: number,
  running: boolean,
  nowMs = Date.now(),
): EstudioProcessLaneState {
  if (running) return "running";
  if (!lastAt) return "empty";
  if (cadenceMinutes <= 0) return "ok";
  const last = Date.parse(lastAt);
  if (!Number.isFinite(last)) return "empty";
  return nowMs - last >= cadenceMinutes * 60_000 ? "stale" : "ok";
}

function buildLaneView(opts: {
  id: EstudioProcessLaneId;
  lastAt: string | null;
  cadenceMinutes: number;
  running: boolean;
  nowMs: number;
}): EstudioProcessLaneView {
  const state = resolveLaneState(
    opts.lastAt,
    opts.cadenceMinutes,
    opts.running,
    opts.nowMs,
  );
  const cadence =
    opts.cadenceMinutes <= 0
      ? "off"
      : `cada ${formatEstudioCadenceMinutes(opts.cadenceMinutes)}`;
  return {
    id: opts.id,
    label: LANE_LABEL[opts.id],
    state,
    lastAt: opts.lastAt,
    cadenceMinutes: opts.cadenceMinutes,
    title: [
      ESTUDIO_LANE_PURPOSE[opts.id],
      `Estado: ${stateLabel(state)}`,
      `Última pasada: ${formatShortAt(opts.lastAt)}`,
      `Cadencia: ${cadence}`,
      ESTUDIO_LANE_HOW_UPDATED[opts.id],
    ].join("\n"),
  };
}

export type ResolveEstudioProcessStatusOpts = {
  instrumentId: string;
  prefs?: EstudioSupervisionPrefs;
  runningLane?: EstudioProcessLaneId | null;
  nowMs?: number;
  localFreshnessMap?: Record<string, LocalFreshnessEntry>;
};

export function resolveEstudioProcessStatus(
  opts: ResolveEstudioProcessStatusOpts,
): EstudioProcessStatusView {
  const prefs = opts.prefs ?? loadEstudioSupervisionPrefs();
  const nowMs = opts.nowMs ?? Date.now();
  const map = opts.localFreshnessMap ?? loadLocalFinalistsFreshnessMap();
  const lastLabAt = maxIso(
    pickLatestLocalLabAt(opts.instrumentId, map),
    readEstudioLaneStamp(opts.instrumentId, "freshness"),
  );
  const lastCoreRAt = maxIso(
    latestCoreRAtForInstrument(opts.instrumentId),
    readEstudioLaneStamp(opts.instrumentId, "vigilance"),
  );
  const lastRediscoverAt = maxIso(
    lastLabAt,
    readEstudioLaneStamp(opts.instrumentId, "rediscover"),
  );
  const running = opts.runningLane ?? null;

  const lanes: EstudioProcessLaneView[] = [
    buildLaneView({
      id: "vigilance",
      lastAt: lastCoreRAt,
      cadenceMinutes: prefs.vigilanceMinutes,
      running: running === "vigilance",
      nowMs,
    }),
    buildLaneView({
      id: "freshness",
      lastAt: lastLabAt,
      cadenceMinutes: prefs.freshnessMinutes,
      running: running === "freshness",
      nowMs,
    }),
    buildLaneView({
      id: "rediscover",
      lastAt: lastRediscoverAt,
      cadenceMinutes: prefs.rediscoverMinutes,
      running: running === "rediscover",
      nowMs,
    }),
  ];

  return {
    instrumentId: opts.instrumentId,
    lanes,
    lastLabAt,
    lastCoreRAt,
  };
}

export function formatEstudioProcessTimestamp(
  iso: string | null | undefined,
): string {
  return formatShortAt(iso ?? null);
}

export function emitEstudioProcessRunning(
  detail: EstudioProcessRunningDetail,
): void {
  try {
    window.dispatchEvent(
      new CustomEvent(ESTUDIO_PROCESS_RUNNING_EVENT, { detail }),
    );
  } catch {
    // SSR / tests
  }
}

export function laneFromListAutoMode(
  forceRescan: boolean,
): EstudioProcessLaneId {
  return forceRescan ? "rediscover" : "freshness";
}

const LANE_SHORT: Record<EstudioProcessLaneId, string> = {
  vigilance: "V",
  freshness: "F",
  rediscover: "R",
};

export type EstudioProcessSummary = {
  text: string;
  tone: "ok" | "attention" | "empty" | "running";
  title: string;
};

/** Resumen corto para subtítulo bajo el nombre (columna Valores · Estudio). */
export function summarizeEstudioProcessLanes(
  lanes: ReadonlyArray<EstudioProcessLaneView>,
): EstudioProcessSummary {
  const title = lanes.map((l) => l.title).join("\n\n");
  if (lanes.some((l) => l.state === "running")) {
    return { text: "actualizando…", tone: "running", title };
  }
  const needs = lanes.filter((l) => l.state === "stale" || l.state === "empty");
  if (needs.length === 0) {
    return { text: "al día", tone: "ok", title };
  }
  if (
    needs.length === lanes.length &&
    needs.every((l) => l.state === "empty")
  ) {
    return { text: "sin sync", tone: "empty", title };
  }
  const letters = needs.map((l) => LANE_SHORT[l.id]).join("·");
  return {
    text: `toca ${letters}`,
    tone: "attention",
    title,
  };
}
