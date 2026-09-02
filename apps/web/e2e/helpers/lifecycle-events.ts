/**
 * V1.84 — Lifecycle event log (append-only) → reduce → snapshot.
 * Wire `events` come from the persisted log, not a regenerated stage template.
 */
import {
  buildLifecycleSnapshot,
  type E2eGoldenPositionStage,
  type LifecycleAccountSnapshot,
  type LifecycleLineagePath,
  MOCK_T1_FILL_ID,
  MOCK_T2_FILL_ID,
} from "./lifecycle-snapshot";

export type LifecycleStoreEventKind =
  | "POSITION_OPENED"
  | "T1_TRIGGERED"
  | "T1_EXECUTED"
  | "T2_TRIGGERED"
  | "T2_EXECUTED"
  | "TRAIL_APPLIED"
  | "EXIT_REQUIRED"
  | "POSITION_CLOSED";

export type LifecycleStoreEvent = {
  kind: LifecycleStoreEventKind;
  at: string;
  fillId?: string;
};

/** Kinds that appear on operationalView.events (V1.83 wire contract). */
const WIRE_EVENT_KINDS = new Set<LifecycleStoreEventKind>([
  "T1_EXECUTED",
  "T2_TRIGGERED",
  "T2_EXECUTED",
  "POSITION_CLOSED",
]);

const DEFAULT_AT: Record<LifecycleStoreEventKind, string> = {
  POSITION_OPENED: "2026-09-02T10:00:00.000Z",
  T1_TRIGGERED: "2026-09-02T11:00:00.000Z",
  T1_EXECUTED: "2026-09-02T11:30:00.000Z",
  TRAIL_APPLIED: "2026-09-02T12:00:00.000Z",
  T2_TRIGGERED: "2026-09-02T12:15:00.000Z",
  T2_EXECUTED: "2026-09-02T12:45:00.000Z",
  EXIT_REQUIRED: "2026-09-02T14:00:00.000Z",
  POSITION_CLOSED: "2026-09-02T15:00:00.000Z",
};

export function normalizeLifecycleStoreEvent(input: {
  kind: LifecycleStoreEventKind;
  at?: string;
  fillId?: string;
}): LifecycleStoreEvent {
  const at = input.at ?? DEFAULT_AT[input.kind];
  if (input.kind === "T1_EXECUTED") {
    return { kind: input.kind, at, fillId: input.fillId ?? MOCK_T1_FILL_ID };
  }
  if (input.kind === "T2_EXECUTED") {
    return { kind: input.kind, at, fillId: input.fillId ?? MOCK_T2_FILL_ID };
  }
  return { kind: input.kind, at, fillId: input.fillId };
}

export function reduceLifecycleEvents(events: LifecycleStoreEvent[]): {
  stage: E2eGoldenPositionStage;
  lineagePath: LifecycleLineagePath;
} {
  let stage: E2eGoldenPositionStage = "candidate";
  let lineagePath: LifecycleLineagePath = "trail";
  for (const ev of events) {
    switch (ev.kind) {
      case "POSITION_OPENED":
        stage = "open";
        break;
      case "T1_TRIGGERED":
        stage = "t1_ready";
        break;
      case "T1_EXECUTED":
        stage = "t1_executed";
        break;
      case "T2_TRIGGERED":
        stage = "t2_ready";
        lineagePath = "t2";
        break;
      case "T2_EXECUTED":
        stage = "t2_executed";
        lineagePath = "t2";
        break;
      case "TRAIL_APPLIED":
        stage = "trailing";
        lineagePath = "trail";
        break;
      case "EXIT_REQUIRED":
        stage = "exit_required";
        break;
      case "POSITION_CLOSED":
        stage = "closed";
        break;
      default:
        break;
    }
  }
  return { stage, lineagePath };
}

export function wireEventsFromLog(
  events: LifecycleStoreEvent[],
): Array<{ kind: string; at: string; fillId?: string }> {
  return events
    .filter((ev) => WIRE_EVENT_KINDS.has(ev.kind))
    .map((ev) => ({
      kind: ev.kind,
      at: ev.at,
      ...(ev.fillId ? { fillId: ev.fillId } : {}),
    }));
}

/**
 * Snapshot whose operationalView.events are the persisted log (filtered to wire kinds).
 * Financials / POV still reuse V1.83 stage projection after reduce.
 */
export function buildLifecycleSnapshotFromEvents(
  events: LifecycleStoreEvent[],
): LifecycleAccountSnapshot {
  const { stage, lineagePath } = reduceLifecycleEvents(events);
  const snap = buildLifecycleSnapshot({ stage, lineagePath });
  if (!snap.position) return snap;

  const wireEvents = wireEventsFromLog(events);
  return {
    ...snap,
    position: {
      ...snap.position,
      operational: {
        ...snap.position.operational,
        operationalView: {
          ...snap.position.operational.operationalView,
          events: wireEvents,
        },
      },
    },
  };
}

export function assertWireEventsMatchLog(
  viewEvents: Array<{ kind?: string }> | undefined,
  log: LifecycleStoreEvent[],
): void {
  const expected = wireEventsFromLog(log).map((ev) => ev.kind);
  const actual = (viewEvents ?? []).map((ev) => ev.kind ?? "");
  if (expected.length !== actual.length) {
    throw new Error(
      `wire events length ${actual.length} ≠ log wire ${expected.length}: [${actual.join(",")}] vs [${expected.join(",")}]`,
    );
  }
  for (let i = 0; i < expected.length; i += 1) {
    if (actual[i] !== expected[i]) {
      throw new Error(`wire events[${i}] ${actual[i]} ≠ log ${expected[i]}`);
    }
  }
}
