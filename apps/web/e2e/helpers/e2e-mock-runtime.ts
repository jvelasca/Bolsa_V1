/**
 * V1.82 — E2E mock runtime flags (mutable mid-test).
 * V1.84 — append-only lifecycle event log (event-driven mock path).
 * V1.85 — validate FSM + identity before append (fail-closed).
 * Public setters re-exported from `e2e/fixtures.ts`.
 */
import { mercadoWorkspaceDocument } from "./mercado";
import {
  appendValidatedLifecycleEvent,
  type LifecycleAppendError,
  type LifecycleEventInput,
  type LifecycleStoreEvent,
} from "./lifecycle-events";
import {
  resolveLineagePathForStage,
  type E2eGoldenPositionStage,
  type LifecycleLineagePath,
} from "./lifecycle-snapshot";

/** True when E2E should run (auto webServer or explicit base URL). */
export function e2eEnabled(): boolean {
  return (
    process.env.E2E_RUN === "1" ||
    Boolean(process.env.PLAYWRIGHT_BASE_URL?.trim())
  );
}

export const E2E_SKIP_REASON =
  "Set E2E_RUN=1 (starts Vite + API mocks) or PLAYWRIGHT_BASE_URL (existing server). See e2e/*.spec.ts headers.";

/** Optional workspace document override for multi-instrument mock routes. */
let mercadoMockWorkspaceDocument: ReturnType<
  typeof mercadoWorkspaceDocument
> | null = null;

export function setMercadoMockWorkspaceDocument(
  document: ReturnType<typeof mercadoWorkspaceDocument> | null,
): void {
  mercadoMockWorkspaceDocument = document;
}

/** Internal read for routeBody (not part of public fixtures barrel). */
export function getMercadoMockWorkspaceDocument(): ReturnType<
  typeof mercadoWorkspaceDocument
> | null {
  return mercadoMockWorkspaceDocument;
}

/** V1.77 / V1.78 — mutable mid-test flags (read on each fulfill). */
export type E2eMockRuntimeFlags = {
  dataFreshness: "current" | "stale";
  reconStatus: "ok" | "drift";
  unknownOrder: boolean;
  /** V1.78 — Hoy desk overlay over multi Mercado installer. */
  deskMode: "off" | "day" | "stale" | "lifecycle" | "lifecycle_stale";
  /** V1.78 — POV stage on first multi position (AAPL). V1.79 lifecycle stages. */
  positionStage: E2eGoldenPositionStage;
  /** V1.83 — CLOSED/EXIT inherit trail vs T2 prefix. */
  lineagePath: LifecycleLineagePath;
  /** V1.84 — append-only SoT when length > 0 (event-driven path). */
  lifecycleEvents: LifecycleStoreEvent[];
};

const e2eMockRuntimeDefaults: E2eMockRuntimeFlags = {
  dataFreshness: "current",
  reconStatus: "ok",
  unknownOrder: false,
  deskMode: "off",
  positionStage: "clean",
  lineagePath: "trail",
  lifecycleEvents: [],
};

let e2eMockRuntime: E2eMockRuntimeFlags = { ...e2eMockRuntimeDefaults };

export function resetE2eMockRuntimeFlags(): void {
  e2eMockRuntime = { ...e2eMockRuntimeDefaults };
}

export function setE2eMockDataFreshness(
  freshness: E2eMockRuntimeFlags["dataFreshness"],
): void {
  e2eMockRuntime = { ...e2eMockRuntime, dataFreshness: freshness };
}

export function setE2eMockReconStatus(
  status: E2eMockRuntimeFlags["reconStatus"],
): void {
  e2eMockRuntime = { ...e2eMockRuntime, reconStatus: status };
}

export function setE2eMockUnknownOrder(enabled: boolean): void {
  e2eMockRuntime = { ...e2eMockRuntime, unknownOrder: enabled };
}

export function setE2eMockDeskMode(
  mode: E2eMockRuntimeFlags["deskMode"],
): void {
  e2eMockRuntime = { ...e2eMockRuntime, deskMode: mode };
}

export function setE2eMockPositionStage(stage: E2eGoldenPositionStage): void {
  e2eMockRuntime = {
    ...e2eMockRuntime,
    positionStage: stage,
    lineagePath: resolveLineagePathForStage(stage, e2eMockRuntime.lineagePath),
    // V1.84 — stage projection mode clears the event log (compat V1.83).
    lifecycleEvents: [],
  };
}

export type EmitLifecycleResult =
  | {
      ok: true;
      event: LifecycleStoreEvent;
      idempotent: boolean;
      stage: E2eGoldenPositionStage;
      lineagePath: LifecycleLineagePath;
      count: number;
    }
  | { ok: false; error: LifecycleAppendError };

/**
 * V1.85 — validate + append (or idempotent no-op). Does not mutate on reject.
 */
export function emitE2eMockLifecycleEvent(
  input: LifecycleEventInput,
): EmitLifecycleResult {
  const result = appendValidatedLifecycleEvent(
    e2eMockRuntime.lifecycleEvents,
    input,
  );
  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  e2eMockRuntime = {
    ...e2eMockRuntime,
    lifecycleEvents: result.log,
    positionStage: result.stage,
    lineagePath: result.lineagePath,
  };
  return {
    ok: true,
    event: result.event,
    idempotent: result.idempotent,
    stage: result.stage,
    lineagePath: result.lineagePath,
    count: result.log.length,
  };
}

export function getE2eMockLifecycleEvents(): LifecycleStoreEvent[] {
  return e2eMockRuntime.lifecycleEvents;
}

/** Internal snapshot for routeBody. */
export function getE2eMockRuntime(): E2eMockRuntimeFlags {
  return e2eMockRuntime;
}
