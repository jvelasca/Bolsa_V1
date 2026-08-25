/**
 * Proyección Decision Board → cola Hoy (ADR-031 Ciclo 3).
 * No es un motor: comprime buckets existentes a BUY / ARMED / WATCH / REVIEW / BLOCKED.
 * Prefiere un TradePlan vivo cuando el payload ya lo trae; si no, heurística de gate.
 * Ciclo 4.8: Setup thin (entrySetup + phase/effort del anchor) — no whyNot nuevos.
 * Ciclo 4.9: sesiones Board echo tradePlan + anchor → Hoy deja heurística cuando hay plan.
 * Ciclo 5.0: thesisHealth advisory (Golden F) — ≠ cola REVIEW de EXPIRED.
 * Ciclo 5.1: protectPlan advisory (Golden E) — no muta structuralStop.
 * Ciclo 5.2: exitRadar advisory — no auto-exit.
 * Ciclo 5.3: mfeMae metrics — no CTA / no expectancy plena.
 * Ciclo 8.0: expectancy thin advisory — ≠ permiso / no auto-exit.
 */

import type {
  DecisionBoardV1,
  DecisionSessionViewV1,
  SemiF3ViewV1,
} from "../decision-board.js";
import type {
  EntrySetupV1,
  TradePlanStatusV1,
  TradePlanV1,
  TradePlanWhyNotV1,
} from "./trade-plan.js";
import type { ConfidenceHint } from "./confidence-state.js";
import type {
  ThesisHealthStatusV1,
  ThesisHealthV1,
  ThesisHealthWhyV1,
} from "./thesis-health.js";
import type {
  ProtectPlanStatusV1,
  ProtectPlanV1,
  ProtectPlanWhyV1,
} from "./protect-plan.js";
import type {
  ExitRadarStatusV1,
  ExitRadarV1,
  ExitRadarWhyV1,
} from "./exit-radar.js";
import type { MfeMaeStatusV1, MfeMaeV1, MfeMaeWhyV1 } from "./mfe-mae.js";
import type {
  ExpectancyStatusV1,
  ExpectancyV1,
  ExpectancyWhyV1,
} from "./expectancy.js";

export type HoyActionKindV1 = "BUY" | "ARMED" | "WATCH" | "REVIEW" | "BLOCKED";

/** Evidencia SETUP en superficie Hoy (runtime echo; no contrato TradePlan). */
export type HoySetupEvidenceV1 = {
  entrySetup?: EntrySetupV1 | null;
  phase?: string | null;
  effort?: string | null;
};

export type HoyQueueItemV1 = {
  id: string;
  symbol: string;
  kind: HoyActionKindV1;
  status: TradePlanStatusV1;
  whyNot: TradePlanWhyNotV1[];
  gate: string;
  /** Ciclo 4.8 — bloque Setup en el dialog Hoy. */
  setup?: HoySetupEvidenceV1 | null;
  /** Ciclo 5.0 — advisory; status review ≠ kind REVIEW. */
  thesisHealth?: ThesisHealthV1 | null;
  /** Ciclo 5.1 — advisory protect/T1. */
  protectPlan?: ProtectPlanV1 | null;
  /** Ciclo 5.2 — advisory exit/trail/time-stop. */
  exitRadar?: ExitRadarV1 | null;
  /** Ciclo 5.3 — MFE/MAE metrics (not an action CTA). */
  mfeMae?: MfeMaeV1 | null;
  /** Ciclo 8.0 — Expectancy thin (≠ permiso). */
  expectancy?: ExpectancyV1 | null;
};

const PLAN_STATUSES = new Set<TradePlanStatusV1>([
  "WATCH",
  "ARMED",
  "TRIGGERED",
  "BLOCKED",
  "EXPIRED",
]);

const PLAN_WHY_NOT = new Set<TradePlanWhyNotV1>([
  "fit",
  "freshness",
  "mandate",
  "entry",
  "no_stop",
  "expired",
  "orphan",
  "rr",
  "regime",
]);

const ENTRY_SETUPS = new Set<EntrySetupV1>([
  "breakout",
  "pullback",
  "wyckoff",
  "none",
]);

const SETUP_PHASES = new Set(["none", "spring", "reclaim", "sos", "lps"]);

const SETUP_EFFORTS = new Set([
  "none",
  "spring_low_effort",
  "spring_high_effort",
  "result_ok",
  "result_weak",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asLiveTradePlan(value: unknown): TradePlanV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !PLAN_STATUSES.has(status as TradePlanStatusV1)
  ) {
    return null;
  }
  const whyNotRaw = value.whyNot;
  const whyNot: TradePlanWhyNotV1[] = Array.isArray(whyNotRaw)
    ? whyNotRaw.filter(
        (code): code is TradePlanWhyNotV1 =>
          typeof code === "string" &&
          PLAN_WHY_NOT.has(code as TradePlanWhyNotV1),
      )
    : [];
  return {
    ...(value as TradePlanV1),
    status: status as TradePlanStatusV1,
    whyNot,
  };
}

function tradePlanFromPayloadish(value: unknown): TradePlanV1 | null {
  if (!isRecord(value)) return null;
  return asLiveTradePlan(value.tradePlan);
}

/** F3: extra.payload.tradePlan → extra.tradePlan → top-level payload (flatten). */
function readTradePlanFromF3Row(row: SemiF3ViewV1): TradePlanV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = tradePlanFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asLiveTradePlan(extra.tradePlan);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & {
    payload?: unknown;
    tradePlan?: unknown;
  };
  const fromTopPayload = tradePlanFromPayloadish(flattened.payload);
  if (fromTopPayload) return fromTopPayload;
  return asLiveTradePlan(flattened.tradePlan);
}

function asEntrySetup(value: unknown): EntrySetupV1 | null {
  return typeof value === "string" && ENTRY_SETUPS.has(value as EntrySetupV1)
    ? (value as EntrySetupV1)
    : null;
}

function readAnchor(raw: unknown): { phase?: string; effort?: string } | null {
  if (!isRecord(raw)) return null;
  const out: { phase?: string; effort?: string } = {};
  if (typeof raw.phase === "string" && SETUP_PHASES.has(raw.phase)) {
    out.phase = raw.phase;
  }
  if (typeof raw.effort === "string" && SETUP_EFFORTS.has(raw.effort)) {
    out.effort = raw.effort;
  }
  return out.phase !== undefined || out.effort !== undefined ? out : null;
}

/** Anchor: payload.wyckoffSpringAnchor → decisionSession.runtime → runtime. */
function readAnchorFromPayloadish(value: unknown): {
  phase?: string;
  effort?: string;
} | null {
  if (!isRecord(value)) return null;
  const top = readAnchor(value.wyckoffSpringAnchor);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = readAnchor(runtime.wyckoffSpringAnchor);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return readAnchor(value.runtime.wyckoffSpringAnchor);
  }
  return null;
}

function readSetupFromF3Row(row: SemiF3ViewV1): HoySetupEvidenceV1 | null {
  const live = readTradePlanFromF3Row(row);
  const entrySetup = asEntrySetup(live?.entrySetup);
  const extra = row.extra;
  let anchor: { phase?: string; effort?: string } | null = null;
  if (isRecord(extra)) {
    anchor =
      readAnchorFromPayloadish(extra.payload) ??
      readAnchor(extra.wyckoffSpringAnchor) ??
      readAnchorFromPayloadish(extra);
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  if (!anchor) {
    anchor = readAnchorFromPayloadish(flattened.payload);
  }
  if (!entrySetup && !anchor) return null;
  return {
    entrySetup: entrySetup ?? null,
    phase: anchor?.phase ?? null,
    effort: anchor?.effort ?? null,
  };
}

function readSetupFromSession(
  session: DecisionSessionViewV1,
  tradePlan: TradePlanV1 | null,
): HoySetupEvidenceV1 | null {
  const entrySetup = asEntrySetup(tradePlan?.entrySetup);
  const anchor = readAnchor(session.wyckoffSpringAnchor);
  if (!entrySetup && !anchor) return null;
  return {
    entrySetup: entrySetup ?? null,
    phase: anchor?.phase ?? null,
    effort: anchor?.effort ?? null,
  };
}

const THESIS_HINTS = new Set<ConfidenceHint>([
  "hold",
  "tighten",
  "reduce",
  "exit",
  "expire",
]);

const THESIS_WHYS = new Set<ThesisHealthWhyV1>([
  "confidence_degraded",
  "stop_intact",
  "hard_exit",
  "expired",
]);

function asThesisHealth(value: unknown): ThesisHealthV1 | null {
  if (!isRecord(value)) return null;
  const hint = value.hint;
  const status = value.status;
  if (
    typeof hint !== "string" ||
    !THESIS_HINTS.has(hint as ConfidenceHint) ||
    (status !== "ok" && status !== "review")
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: ThesisHealthWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is ThesisHealthWhyV1 =>
          typeof code === "string" &&
          THESIS_WHYS.has(code as ThesisHealthWhyV1),
      )
    : [];
  const confidence =
    typeof value.confidence === "number" && Number.isFinite(value.confidence)
      ? value.confidence
      : 0;
  return {
    hint: hint as ConfidenceHint,
    status: status as ThesisHealthStatusV1,
    why,
    confidence,
  };
}

function readThesisHealthFromPayloadish(value: unknown): ThesisHealthV1 | null {
  if (!isRecord(value)) return null;
  const top = asThesisHealth(value.thesisHealth);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = asThesisHealth(runtime.thesisHealth);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return asThesisHealth(value.runtime.thesisHealth);
  }
  return null;
}

function readThesisHealthFromF3Row(row: SemiF3ViewV1): ThesisHealthV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = readThesisHealthFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asThesisHealth(extra.thesisHealth);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  return readThesisHealthFromPayloadish(flattened.payload);
}

const PROTECT_STATUSES = new Set<ProtectPlanStatusV1>(["none", "protect_hint"]);
const PROTECT_WHYS = new Set<ProtectPlanWhyV1>(["mfe_ge_1r", "missing_inputs"]);

function asProtectPlan(value: unknown): ProtectPlanV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !PROTECT_STATUSES.has(status as ProtectPlanStatusV1)
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: ProtectPlanWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is ProtectPlanWhyV1 =>
          typeof code === "string" &&
          PROTECT_WHYS.has(code as ProtectPlanWhyV1),
      )
    : [];
  const target1 =
    typeof value.target1 === "number" && Number.isFinite(value.target1)
      ? value.target1
      : null;
  const suggestedProtectStop =
    typeof value.suggestedProtectStop === "number" &&
    Number.isFinite(value.suggestedProtectStop)
      ? value.suggestedProtectStop
      : null;
  const rMultiple =
    typeof value.rMultiple === "number" && Number.isFinite(value.rMultiple)
      ? value.rMultiple
      : null;
  return {
    status: status as ProtectPlanStatusV1,
    target1,
    suggestedProtectStop,
    rMultiple,
    why,
  };
}

function readProtectPlanFromPayloadish(value: unknown): ProtectPlanV1 | null {
  if (!isRecord(value)) return null;
  const top = asProtectPlan(value.protectPlan);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = asProtectPlan(runtime.protectPlan);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return asProtectPlan(value.runtime.protectPlan);
  }
  return null;
}

function readProtectPlanFromF3Row(row: SemiF3ViewV1): ProtectPlanV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = readProtectPlanFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asProtectPlan(extra.protectPlan);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  return readProtectPlanFromPayloadish(flattened.payload);
}

const EXIT_STATUSES = new Set<ExitRadarStatusV1>([
  "none",
  "trail_hint",
  "time_stop_hint",
  "exit_hint",
]);
const EXIT_WHYS = new Set<ExitRadarWhyV1>([
  "thesis_exit",
  "beyond_target1",
  "expired",
  "mfe_ge_1_5r",
  "missing_inputs",
]);

function asExitRadar(value: unknown): ExitRadarV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !EXIT_STATUSES.has(status as ExitRadarStatusV1)
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: ExitRadarWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is ExitRadarWhyV1 =>
          typeof code === "string" && EXIT_WHYS.has(code as ExitRadarWhyV1),
      )
    : [];
  const numOrNull = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  return {
    status: status as ExitRadarStatusV1,
    suggestedTrailStop: numOrNull(value.suggestedTrailStop),
    target1: numOrNull(value.target1),
    rMultiple: numOrNull(value.rMultiple),
    why,
  };
}

function readExitRadarFromPayloadish(value: unknown): ExitRadarV1 | null {
  if (!isRecord(value)) return null;
  const top = asExitRadar(value.exitRadar);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = asExitRadar(runtime.exitRadar);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return asExitRadar(value.runtime.exitRadar);
  }
  return null;
}

function readExitRadarFromF3Row(row: SemiF3ViewV1): ExitRadarV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = readExitRadarFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asExitRadar(extra.exitRadar);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  return readExitRadarFromPayloadish(flattened.payload);
}

const MFE_STATUSES = new Set<MfeMaeStatusV1>([
  "none",
  "observe",
  "favorable",
  "adverse",
]);
const MFE_WHYS = new Set<MfeMaeWhyV1>([
  "peak_from_bars",
  "close_proxy",
  "mae_ge_1r",
  "mfe_ge_1_5r",
  "missing_inputs",
]);

function asMfeMae(value: unknown): MfeMaeV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !MFE_STATUSES.has(status as MfeMaeStatusV1)
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: MfeMaeWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is MfeMaeWhyV1 =>
          typeof code === "string" && MFE_WHYS.has(code as MfeMaeWhyV1),
      )
    : [];
  const numOrNull = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  return {
    status: status as MfeMaeStatusV1,
    mfeR: numOrNull(value.mfeR),
    maeR: numOrNull(value.maeR),
    currentR: numOrNull(value.currentR),
    why,
  };
}

function readMfeMaeFromPayloadish(value: unknown): MfeMaeV1 | null {
  if (!isRecord(value)) return null;
  const top = asMfeMae(value.mfeMae);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = asMfeMae(runtime.mfeMae);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return asMfeMae(value.runtime.mfeMae);
  }
  return null;
}

function readMfeMaeFromF3Row(row: SemiF3ViewV1): MfeMaeV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = readMfeMaeFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asMfeMae(extra.mfeMae);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  return readMfeMaeFromPayloadish(flattened.payload);
}

const EXPECTANCY_STATUSES = new Set<ExpectancyStatusV1>([
  "none",
  "thin",
  "ready",
]);
const EXPECTANCY_WHYS = new Set<ExpectancyWhyV1>([
  "missing_inputs",
  "thin_sample",
  "live_proxy",
  "aggregated",
  "not_permission",
]);

function asExpectancy(value: unknown): ExpectancyV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !EXPECTANCY_STATUSES.has(status as ExpectancyStatusV1)
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: ExpectancyWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is ExpectancyWhyV1 =>
          typeof code === "string" &&
          EXPECTANCY_WHYS.has(code as ExpectancyWhyV1),
      )
    : [];
  const numOrNull = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  const nRaw = value.n;
  const n =
    typeof nRaw === "number" && Number.isFinite(nRaw) && nRaw >= 0
      ? Math.floor(nRaw)
      : 0;
  const setupRaw = value.entrySetup;
  const entrySetup =
    typeof setupRaw === "string" && setupRaw.trim() ? setupRaw.trim() : null;
  return {
    status: status as ExpectancyStatusV1,
    entrySetup,
    n,
    expectancyR: numOrNull(value.expectancyR),
    winRate: numOrNull(value.winRate),
    avgWinR: numOrNull(value.avgWinR),
    avgLossR: numOrNull(value.avgLossR),
    currentR: numOrNull(value.currentR),
    why,
  };
}

function readExpectancyFromPayloadish(value: unknown): ExpectancyV1 | null {
  if (!isRecord(value)) return null;
  const top = asExpectancy(value.expectancy);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = asExpectancy(runtime.expectancy);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return asExpectancy(value.runtime.expectancy);
  }
  return null;
}

function readExpectancyFromF3Row(row: SemiF3ViewV1): ExpectancyV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = readExpectancyFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asExpectancy(extra.expectancy);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  return readExpectancyFromPayloadish(flattened.payload);
}

function kindFromGate(
  gate: string,
  bucket: "pending" | "vetoed" | "deferred" | "auto",
): HoyActionKindV1 {
  if (bucket === "vetoed" || gate.toUpperCase() === "VETO") return "BLOCKED";
  if (bucket === "deferred" || gate.toUpperCase() === "DEFERRED")
    return "WATCH";
  if (bucket === "auto") return "ARMED";
  return "BUY";
}

function kindFromPlanStatus(status: TradePlanStatusV1): HoyActionKindV1 {
  switch (status) {
    case "TRIGGERED":
      return "BUY";
    case "ARMED":
      return "ARMED";
    case "BLOCKED":
      return "BLOCKED";
    case "EXPIRED":
      return "REVIEW";
    case "WATCH":
      return "WATCH";
  }
}

function statusFromKind(kind: HoyActionKindV1): TradePlanStatusV1 {
  switch (kind) {
    case "BUY":
      return "TRIGGERED";
    case "ARMED":
      return "ARMED";
    case "BLOCKED":
      return "BLOCKED";
    default:
      return "WATCH";
  }
}

function whyNotFromKind(kind: HoyActionKindV1): TradePlanWhyNotV1[] {
  if (kind === "BLOCKED") return ["fit"];
  if (kind === "WATCH") return ["entry"];
  return [];
}

function toHoyItem(
  id: string,
  symbol: string,
  gate: string,
  live: TradePlanV1 | null,
  heuristicKind: HoyActionKindV1,
  setup: HoySetupEvidenceV1 | null,
  thesisHealth: ThesisHealthV1 | null,
  protectPlan: ProtectPlanV1 | null,
  exitRadar: ExitRadarV1 | null,
  mfeMae: MfeMaeV1 | null,
  expectancy: ExpectancyV1 | null,
): HoyQueueItemV1 {
  if (live) {
    return {
      id,
      symbol,
      kind: kindFromPlanStatus(live.status),
      status: live.status,
      whyNot: live.whyNot,
      gate,
      setup,
      thesisHealth,
      protectPlan,
      exitRadar,
      mfeMae,
      expectancy,
    };
  }
  return {
    id,
    symbol,
    kind: heuristicKind,
    status: statusFromKind(heuristicKind),
    whyNot: whyNotFromKind(heuristicKind),
    gate,
    setup,
    thesisHealth,
    protectPlan,
    exitRadar,
    mfeMae,
    expectancy,
  };
}

/** Mapea el Decision Board a ítems de la tira Hoy (máx. 8). */
export function mapDecisionBoardToHoyQueue(
  board: DecisionBoardV1,
  limit = 8,
): HoyQueueItemV1[] {
  const items: HoyQueueItemV1[] = [];

  for (const row of board.semiF3Queue) {
    const kind = kindFromGate("unknown", "pending");
    items.push(
      toHoyItem(
        `f3-${row.instrumentId ?? row.symbol ?? items.length}`,
        row.symbol ?? row.instrumentId ?? "—",
        row.status,
        readTradePlanFromF3Row(row),
        kind,
        readSetupFromF3Row(row),
        readThesisHealthFromF3Row(row),
        readProtectPlanFromF3Row(row),
        readExitRadarFromF3Row(row),
        readMfeMaeFromF3Row(row),
        readExpectancyFromF3Row(row),
      ),
    );
  }

  for (const session of board.decisionSessions) {
    const gate = session.gate || "unknown";
    let bucket: "pending" | "vetoed" | "deferred" | "auto" = "pending";
    if (gate.toUpperCase() === "VETO") bucket = "vetoed";
    else if (gate.toUpperCase() === "DEFERRED") bucket = "deferred";
    else if (session.kind.includes("paper") || session.kind.includes("auto"))
      bucket = "auto";
    const kind = kindFromGate(gate, bucket);
    const live = asLiveTradePlan(session.tradePlan);
    items.push(
      toHoyItem(
        session.sessionId,
        session.symbol ?? session.instrumentId,
        gate,
        live,
        kind,
        readSetupFromSession(session, live),
        asThesisHealth(session.thesisHealth),
        asProtectPlan(session.protectPlan),
        asExitRadar(session.exitRadar),
        asMfeMae(session.mfeMae),
        asExpectancy(session.expectancy),
      ),
    );
  }

  const seen = new Set<string>();
  const deduped: HoyQueueItemV1[] = [];
  for (const item of items) {
    const key = `${item.symbol}:${item.kind}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
    if (deduped.length >= limit) break;
  }
  return deduped;
}
