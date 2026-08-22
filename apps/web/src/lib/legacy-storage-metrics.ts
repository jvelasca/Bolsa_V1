/**
 * Opt-in / sampled client telemetry for R-12 legacy storage blobs (§2.1–2.3).
 * Metrics only — no purge, no migrator changes.
 */

export const LEGACY_STORAGE_METRICS_OPT_IN_KEY = "bolsa-legacy-storage-metrics";
/** Inspectable local log (no HTTP). Cap keeps DevTools / quota bounded. */
export const LEGACY_STORAGE_METRICS_LOG_KEY =
  "bolsa-legacy-storage-metrics-log";
export const LEGACY_STORAGE_METRICS_LOG_CAP = 200;
const SESSION_REPORTED_PREFIX = "bolsa-legacy-metric-reported:";
/** Sample rate when not explicitly opted in (1%). */
const DEFAULT_SAMPLE_RATE = 0.01;

export type LegacyStorageMetricPayload = Record<string, unknown>;

export type LegacyStorageMetricLogEntry = {
  ts: string;
  name: string;
  payload: LegacyStorageMetricPayload;
};

export type WorkspaceDeprecatedFieldPresence = {
  chartDataStrip: boolean;
  chartNewTabSeed: boolean;
  newChartConfigSource: boolean;
};

function hasBrowserStorage(): boolean {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

export function isLegacyStorageMetricsOptIn(): boolean {
  if (!hasBrowserStorage()) return false;
  try {
    if (localStorage.getItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY) === "1") {
      return true;
    }
  } catch {
    return false;
  }
  return import.meta.env.VITE_LEGACY_STORAGE_METRICS === "1";
}

function sessionReportedKey(name: string): string {
  return `${SESSION_REPORTED_PREFIX}${name}`;
}

function wasReportedThisSession(name: string): boolean {
  if (typeof sessionStorage === "undefined") return false;
  try {
    return sessionStorage.getItem(sessionReportedKey(name)) === "1";
  } catch {
    return false;
  }
}

function markReportedThisSession(name: string): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(sessionReportedKey(name), "1");
  } catch {
    /* ignore quota / private mode */
  }
}

/** Exported for unit tests — decides whether telemetry (not dev debug) fires. */
export function shouldEmitLegacyStorageMetric(
  name: string,
  random = Math.random,
): boolean {
  if (wasReportedThisSession(name)) return false;
  if (isLegacyStorageMetricsOptIn()) return true;
  return random() < DEFAULT_SAMPLE_RATE;
}

export function collectWorkspaceDeprecatedFieldPresence(
  raw:
    | {
        chartDataStrip?: unknown;
        chartNewTabSeed?: unknown;
        preferences?: { newChartConfigSource?: unknown };
      }
    | undefined
    | null,
): WorkspaceDeprecatedFieldPresence {
  return {
    chartDataStrip: raw?.chartDataStrip != null,
    chartNewTabSeed: raw?.chartNewTabSeed != null,
    newChartConfigSource: raw?.preferences?.newChartConfigSource != null,
  };
}

export function mergeWorkspaceDeprecatedFieldPresence(
  a: WorkspaceDeprecatedFieldPresence,
  b: WorkspaceDeprecatedFieldPresence,
): WorkspaceDeprecatedFieldPresence {
  return {
    chartDataStrip: a.chartDataStrip || b.chartDataStrip,
    chartNewTabSeed: a.chartNewTabSeed || b.chartNewTabSeed,
    newChartConfigSource: a.newChartConfigSource || b.newChartConfigSource,
  };
}

function hasAnyDeprecatedField(
  presence: WorkspaceDeprecatedFieldPresence,
): boolean {
  return (
    presence.chartDataStrip ||
    presence.chartNewTabSeed ||
    presence.newChartConfigSource
  );
}

export function reportWorkspaceDeprecatedFields(
  raw: Parameters<typeof collectWorkspaceDeprecatedFieldPresence>[0],
): void {
  const presence = collectWorkspaceDeprecatedFieldPresence(raw);
  if (!hasAnyDeprecatedField(presence)) return;
  reportLegacyStorageMetric("workspace_deprecated_fields", presence);
}

export function reportMergedWorkspaceDeprecatedFields(
  newerDoc: Parameters<typeof collectWorkspaceDeprecatedFieldPresence>[0],
  olderDoc: Parameters<typeof collectWorkspaceDeprecatedFieldPresence>[0],
): void {
  const presence = mergeWorkspaceDeprecatedFieldPresence(
    collectWorkspaceDeprecatedFieldPresence(newerDoc),
    collectWorkspaceDeprecatedFieldPresence(olderDoc),
  );
  if (!hasAnyDeprecatedField(presence)) return;
  reportLegacyStorageMetric("workspace_deprecated_fields", presence);
}

export function readLegacyStorageMetricsLog(): LegacyStorageMetricLogEntry[] {
  if (!hasBrowserStorage()) return [];
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_METRICS_LOG_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as LegacyStorageMetricLogEntry[];
  } catch {
    return [];
  }
}

/** Clear inspectable log — tests and DevTools. */
export function clearLegacyStorageMetricsLog(): void {
  if (!hasBrowserStorage()) return;
  try {
    localStorage.removeItem(LEGACY_STORAGE_METRICS_LOG_KEY);
  } catch {
    /* ignore quota / private mode */
  }
}

function appendLegacyStorageMetricLog(
  name: string,
  payload: LegacyStorageMetricPayload,
): void {
  if (!hasBrowserStorage()) return;
  try {
    const next: LegacyStorageMetricLogEntry[] = [
      ...readLegacyStorageMetricsLog(),
      { ts: new Date().toISOString(), name, payload },
    ];
    const trimmed =
      next.length > LEGACY_STORAGE_METRICS_LOG_CAP
        ? next.slice(next.length - LEGACY_STORAGE_METRICS_LOG_CAP)
        : next;
    localStorage.setItem(
      LEGACY_STORAGE_METRICS_LOG_KEY,
      JSON.stringify(trimmed),
    );
  } catch {
    /* ignore quota / private mode */
  }
}

/**
 * Emit a legacy-storage metric (opt-in or sampled, once per session per name).
 * Always `console.debug` in dev when invoked.
 * When `shouldEmitLegacyStorageMetric` is true, appends to the local inspectable log.
 * No client POST for platform_events (GET-only audit bus).
 */
export function reportLegacyStorageMetric(
  name: string,
  payload: LegacyStorageMetricPayload,
): void {
  if (import.meta.env.DEV) {
    console.debug(`[legacy-storage-metric] ${name}`, payload);
  }
  if (!shouldEmitLegacyStorageMetric(name)) return;
  markReportedThisSession(name);
  appendLegacyStorageMetricLog(name, payload);
}

/** Clear session dedupe keys — tests only. */
export function resetLegacyStorageMetricsForTests(): void {
  if (typeof sessionStorage === "undefined") return;
  const keys: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key?.startsWith(SESSION_REPORTED_PREFIX)) keys.push(key);
  }
  for (const key of keys) sessionStorage.removeItem(key);
}
