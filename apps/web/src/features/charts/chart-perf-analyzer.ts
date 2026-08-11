/**
 * Analizador de rendimiento del gráfico.
 *
 * Uso recomendado (consola F12):
 *   bolsaPerfStart()   — empieza a grabar
 *   … usa la app con el gráfico …
 *   bolsaPerfStop()    — para, descarga JSON y guarda en localStorage
 *
 * También: bolsaPerfReport(), bolsaPerfCopy(), bolsaPerfLoadLast()
 */

import {
  getIndicatorSpecCacheStats,
  resetIndicatorSpecCacheStats,
} from "@/features/charts/indicator-compute";

type CounterMap = Record<string, number>;

type PerfLogType =
  | "reflow_req"
  | "reflow_evt"
  | "workspace_set"
  | "query_fetch"
  | "query_cache"
  | "debug"
  | "rollup"
  | "session";

interface PerfLogEntry {
  t: number;
  type: PerfLogType;
  source?: string;
  detail?: Record<string, unknown>;
  stack?: string;
}

interface PerfRollup {
  t: number;
  reflowRequests: number;
  reflowEvents: number;
  workspaceSets: number;
  queryFetches: number;
  queryCacheUpdates: number;
  dropped: CounterMap;
}

export interface PerfSessionReport {
  version: 1;
  capturedAt: string;
  durationMs: number;
  userAgent: string;
  url: string;
  summary: {
    reflowRequests: number;
    reflowEvents: number;
    workspaceSets: number;
    queryFetches: number;
    queryCacheUpdates: number;
    indicatorSpecCacheHits: number;
    indicatorSpecCacheMisses: number;
    indicatorSpecCacheHitRate: number;
    reflowRequestsPerSec: number;
    workspaceSetsPerSec: number;
    queryFetchesPerSec: number;
    logEntries: number;
    droppedEntries: CounterMap;
  };
  topSources: CounterMap;
  rollups: PerfRollup[];
  entries: PerfLogEntry[];
}

interface PerfState {
  startedAt: number;
  reflowRequests: number;
  reflowEvents: number;
  workspaceSets: number;
  queryFetches: number;
  queryCacheUpdates: number;
  bySource: CounterMap;
  lastReflowAt: number;
  lastWorkspaceSetAt: number;
  workspaceSetStack?: string;
}

const STORAGE_KEY = "bolsa-debug-chart";
const SESSION_STORAGE_KEY = "bolsa-perf-last-session";
const MAX_LOG_ENTRIES = 4000;

const state: PerfState = {
  startedAt: Date.now(),
  reflowRequests: 0,
  reflowEvents: 0,
  workspaceSets: 0,
  queryFetches: 0,
  queryCacheUpdates: 0,
  bySource: {},
  lastReflowAt: 0,
  lastWorkspaceSetAt: 0,
};

let recording = false;
let sessionStart = 0;
let sessionLog: PerfLogEntry[] = [];
let sessionRollups: PerfRollup[] = [];
let droppedEntries: CounterMap = {};
let rollupTimer: ReturnType<typeof setInterval> | null = null;
let rollupBaseline: PerfState | null = null;
let lastSessionReport: PerfSessionReport | null = null;

let hudNode: HTMLDivElement | null = null;
let hudTimer: ReturnType<typeof setInterval> | null = null;
let installed = false;

function isVerboseDebug(): boolean {
  try {
    return (
      typeof window !== "undefined" &&
      window.localStorage?.getItem(STORAGE_KEY) === "1"
    );
  } catch {
    return false;
  }
}

function hudEnabled(): boolean {
  try {
    return window.localStorage?.getItem(`${STORAGE_KEY}-hud`) === "1";
  } catch {
    return false;
  }
}

function shouldTrack(): boolean {
  return recording || isVerboseDebug();
}

function bump(map: CounterMap, key: string, amount = 1): void {
  map[key] = (map[key] ?? 0) + amount;
}

function elapsedSec(from = state.startedAt): number {
  return Math.max(1, (Date.now() - from) / 1000);
}

function captureStack(skipFrames = 3): string | undefined {
  try {
    const stack = new Error().stack;
    if (!stack) return undefined;
    return stack
      .split("\n")
      .slice(skipFrames, skipFrames + 4)
      .map((line) => line.trim())
      .join(" | ");
  } catch {
    return undefined;
  }
}

function pushLog(
  type: PerfLogType,
  options?: {
    source?: string;
    detail?: Record<string, unknown>;
    stack?: string;
  },
): void {
  if (!recording) return;
  if (sessionLog.length >= MAX_LOG_ENTRIES) {
    bump(droppedEntries, type);
    return;
  }
  sessionLog.push({
    t: Date.now() - sessionStart,
    type,
    source: options?.source,
    detail: options?.detail,
    stack: options?.stack,
  });
}

function snapshotRollup(): void {
  if (!recording || !rollupBaseline) return;
  const t = Date.now() - sessionStart;
  sessionRollups.push({
    t,
    reflowRequests: state.reflowRequests - rollupBaseline.reflowRequests,
    reflowEvents: state.reflowEvents - rollupBaseline.reflowEvents,
    workspaceSets: state.workspaceSets - rollupBaseline.workspaceSets,
    queryFetches: state.queryFetches - rollupBaseline.queryFetches,
    queryCacheUpdates:
      state.queryCacheUpdates - rollupBaseline.queryCacheUpdates,
    dropped: { ...droppedEntries },
  });
  rollupBaseline = { ...state, bySource: { ...state.bySource } };
  droppedEntries = {};
}

function renderHud(): void {
  if (!hudNode) return;
  const sec = elapsedSec(recording ? sessionStart : state.startedAt);
  const ind = getIndicatorSpecCacheStats();
  const indTotal = ind.hits + ind.misses;
  const lines = [
    recording ? "● REC bolsa-perf" : "Bolsa chart perf",
    `reflow: ${state.reflowRequests} (${(state.reflowRequests / sec).toFixed(1)}/s)`,
    `workspace: ${state.workspaceSets} (${(state.workspaceSets / sec).toFixed(1)}/s)`,
    `fetch: ${state.queryFetches} (${(state.queryFetches / sec).toFixed(1)}/s)`,
    `ind.cache: ${ind.hits}/${indTotal} hits`,
    recording ? `log: ${sessionLog.length}` : "bolsaPerfStart()",
  ];
  hudNode.textContent = lines.join("\n");
}

function ensureHud(show: boolean): void {
  if (!show) {
    if (hudTimer) clearInterval(hudTimer);
    hudTimer = null;
    hudNode?.remove();
    hudNode = null;
    return;
  }
  if (hudNode) return;
  hudNode = document.createElement("div");
  hudNode.style.cssText =
    "position:fixed;bottom:8px;left:8px;z-index:99999;padding:8px 10px;border-radius:8px;background:rgba(0,0,0,.78);color:#9ef;font:11px/1.35 ui-monospace,monospace;white-space:pre;pointer-events:none;max-width:340px";
  document.body.appendChild(hudNode);
  renderHud();
  hudTimer = setInterval(renderHud, 1000);
}

function buildSessionReport(): PerfSessionReport {
  const durationMs = Math.max(1, Date.now() - sessionStart);
  const sec = durationMs / 1000;
  const topSources = Object.fromEntries(
    Object.entries(state.bySource)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20),
  );

  const indicatorCache = getIndicatorSpecCacheStats();
  return {
    version: 1,
    capturedAt: new Date().toISOString(),
    durationMs,
    userAgent: navigator.userAgent,
    url: window.location.href,
    summary: {
      reflowRequests: state.reflowRequests,
      reflowEvents: state.reflowEvents,
      workspaceSets: state.workspaceSets,
      queryFetches: state.queryFetches,
      queryCacheUpdates: state.queryCacheUpdates,
      indicatorSpecCacheHits: indicatorCache.hits,
      indicatorSpecCacheMisses: indicatorCache.misses,
      indicatorSpecCacheHitRate: indicatorCache.hitRate,
      reflowRequestsPerSec: state.reflowRequests / sec,
      workspaceSetsPerSec: state.workspaceSets / sec,
      queryFetchesPerSec: state.queryFetches / sec,
      logEntries: sessionLog.length,
      droppedEntries: { ...droppedEntries },
    },
    topSources,
    rollups: sessionRollups,
    entries: sessionLog,
  };
}

function persistSession(report: PerfSessionReport): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(report));
  } catch {
    // quota
  }
}

function downloadSession(report: PerfSessionReport): void {
  const stamp = report.capturedAt.replace(/[:.]/g, "-");
  const blob = new Blob([JSON.stringify(report, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `bolsa-perf-${stamp}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function chartPerfDebug(
  event: string,
  detail?: Record<string, unknown>,
): void {
  if (!shouldTrack()) return;
  bump(state.bySource, event);
  pushLog("debug", { source: event, detail });
  if (isVerboseDebug()) {
    console.debug(`[chart-perf] ${event}`, detail ?? "");
  }
}

export function chartPerfRecordReflowRequest(source?: string): void {
  if (!shouldTrack()) return;
  state.reflowRequests += 1;
  state.lastReflowAt = Date.now();
  if (source) bump(state.bySource, `reflow:${source}`);
  pushLog("reflow_req", { source });
}

export function chartPerfRecordReflowEvent(): void {
  if (!shouldTrack()) return;
  state.reflowEvents += 1;
  pushLog("reflow_evt");
}

export function chartPerfRecordWorkspaceSet(): void {
  if (!shouldTrack()) return;
  state.workspaceSets += 1;
  state.lastWorkspaceSetAt = Date.now();
  const stack =
    recording && state.workspaceSets % 10 === 0 ? captureStack(5) : undefined;
  if (stack) state.workspaceSetStack = stack;
  pushLog("workspace_set", stack ? { stack } : undefined);
}

export function chartPerfRecordQueryFetch(key: string): void {
  if (!shouldTrack()) return;
  state.queryFetches += 1;
  bump(state.bySource, `fetch:${key}`);
  pushLog("query_fetch", { source: key });
}

export function chartPerfRecordQueryCacheUpdate(): void {
  if (!shouldTrack()) return;
  state.queryCacheUpdates += 1;
  pushLog("query_cache");
}

export function bolsaPerfStart(): void {
  if (recording) {
    console.warn("[bolsa-perf] ya está grabando. Usa bolsaPerfStop() primero.");
    return;
  }
  recording = true;
  sessionStart = Date.now();
  sessionLog = [];
  sessionRollups = [];
  droppedEntries = {};
  resetIndicatorSpecCacheStats();
  bolsaPerfReset();
  rollupBaseline = { ...state, bySource: { ...state.bySource } };

  pushLog("session", { detail: { action: "start" } });
  snapshotRollup();

  if (rollupTimer) clearInterval(rollupTimer);
  rollupTimer = setInterval(snapshotRollup, 1000);

  ensureHud(true);
  console.info(
    "[bolsa-perf] ● Grabando. Reproduce el parpadeo / carga CPU, luego ejecuta bolsaPerfStop()",
  );
}

export function bolsaPerfStop(): PerfSessionReport {
  if (!recording) {
    console.warn(
      "[bolsa-perf] no hay grabación activa. Ejecuta bolsaPerfStart() primero.",
    );
    return lastSessionReport ?? buildSessionReport();
  }

  recording = false;
  if (rollupTimer) {
    clearInterval(rollupTimer);
    rollupTimer = null;
  }
  pushLog("session", { detail: { action: "stop" } });
  snapshotRollup();

  const report = buildSessionReport();
  lastSessionReport = report;
  persistSession(report);
  downloadSession(report);

  console.group("[bolsa-perf] sesión guardada");
  console.table({
    duración_s: (report.durationMs / 1000).toFixed(1),
    reflow_s: report.summary.reflowRequestsPerSec.toFixed(2),
    workspace_s: report.summary.workspaceSetsPerSec.toFixed(2),
    fetch_s: report.summary.queryFetchesPerSec.toFixed(2),
    ind_cache_hit_pct: (report.summary.indicatorSpecCacheHitRate * 100).toFixed(
      1,
    ),
    entradas_log: report.summary.logEntries,
  });
  console.log("Top sources:", report.topSources);
  console.log("Archivo descargado + localStorage bolsa-perf-last-session");
  console.log("Pega en el chat: bolsaPerfCopy() o el JSON del archivo");
  console.groupEnd();

  renderHud();
  return report;
}

export function bolsaPerfExport(): PerfSessionReport | null {
  return lastSessionReport ?? bolsaPerfLoadLast();
}

export function bolsaPerfLoadLast(): PerfSessionReport | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PerfSessionReport;
  } catch {
    return null;
  }
}

export async function bolsaPerfCopy(): Promise<boolean> {
  const report = bolsaPerfExport();
  if (!report) {
    console.warn(
      "[bolsa-perf] no hay sesión. Ejecuta bolsaPerfStop() o bolsaPerfLoadLast().",
    );
    return false;
  }
  const text = JSON.stringify(report);
  try {
    await navigator.clipboard.writeText(text);
    console.info(
      `[bolsa-perf] ${(text.length / 1024).toFixed(1)} KB copiados al portapapeles`,
    );
    return true;
  } catch {
    console.log(text);
    console.info("[bolsa-perf] no se pudo copiar; JSON impreso arriba");
    return false;
  }
}

export function bolsaPerfReport(): void {
  const sec = elapsedSec();
  const topSources = Object.entries(state.bySource)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  console.group("[bolsa-perf] report en vivo");
  const indicatorCache = getIndicatorSpecCacheStats();
  console.table({
    grabando: recording,
    segundos: sec.toFixed(1),
    reflowRequests: state.reflowRequests,
    reflow_s: (state.reflowRequests / sec).toFixed(2),
    workspaceSets: state.workspaceSets,
    workspace_s: (state.workspaceSets / sec).toFixed(2),
    queryFetches: state.queryFetches,
    ind_cache_hit_pct: (indicatorCache.hitRate * 100).toFixed(1),
    logEntries: sessionLog.length,
  });
  if (topSources.length > 0)
    console.log("Top sources:", Object.fromEntries(topSources));
  if (state.workspaceSetStack)
    console.log("Stack workspace (muestra):", state.workspaceSetStack);
  console.groupEnd();
}

export function bolsaPerfReset(): void {
  state.startedAt = Date.now();
  state.reflowRequests = 0;
  state.reflowEvents = 0;
  state.workspaceSets = 0;
  state.queryFetches = 0;
  state.queryCacheUpdates = 0;
  state.bySource = {};
  state.workspaceSetStack = undefined;
  if (!recording) {
    sessionLog = [];
    sessionRollups = [];
    droppedEntries = {};
  }
}

export function bolsaPerfHud(enabled: boolean): void {
  try {
    if (enabled) window.localStorage.setItem(`${STORAGE_KEY}-hud`, "1");
    else window.localStorage.removeItem(`${STORAGE_KEY}-hud`);
  } catch {
    // ignore
  }
  ensureHud(enabled);
}

export function installChartPerfAnalyzer(
  workspaceSubscribe?: (listener: () => void) => () => void,
  queryClient?: {
    getQueryCache: () => {
      subscribe: (
        listener: (event: {
          type: string;
          query?: { queryHash: string; state: { fetchStatus: string } };
          action?: { type: string };
        }) => void,
      ) => () => void;
    };
  },
): void {
  if (installed) return;
  installed = true;

  const win = window as Window & {
    bolsaPerfStart?: () => void;
    bolsaPerfStop?: () => PerfSessionReport;
    bolsaPerfReport?: () => void;
    bolsaPerfReset?: () => void;
    bolsaPerfHud?: (enabled: boolean) => void;
    bolsaPerfExport?: () => PerfSessionReport | null;
    bolsaPerfCopy?: () => Promise<boolean>;
    bolsaPerfLoadLast?: () => PerfSessionReport | null;
  };

  win.bolsaPerfStart = bolsaPerfStart;
  win.bolsaPerfStop = bolsaPerfStop;
  win.bolsaPerfReport = bolsaPerfReport;
  win.bolsaPerfReset = bolsaPerfReset;
  win.bolsaPerfHud = bolsaPerfHud;
  win.bolsaPerfExport = bolsaPerfExport;
  win.bolsaPerfCopy = bolsaPerfCopy;
  win.bolsaPerfLoadLast = bolsaPerfLoadLast;

  if (workspaceSubscribe) {
    workspaceSubscribe(() => chartPerfRecordWorkspaceSet());
  }

  if (queryClient) {
    queryClient.getQueryCache().subscribe((event) => {
      if (event.type !== "updated") return;
      const query = event.query;
      if (!query) return;
      if (event.action?.type === "fetch") {
        chartPerfRecordQueryFetch(query.queryHash);
        return;
      }
      chartPerfRecordQueryCacheUpdate();
    });
  }

  if (hudEnabled()) ensureHud(true);

  console.info(
    "[bolsa-perf] listo. bolsaPerfStart() → usa la app → bolsaPerfStop() → bolsaPerfCopy() para pegar aquí",
  );
}
