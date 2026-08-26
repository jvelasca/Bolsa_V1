/**
 * PositionRevision — historia auditada de stop/status (ADR-034 OI-5).
 * Append-only en PositionState.revisions. ≠ Journal ≠ ExecutionRecord ≠ PaperOrder.
 */

import { createRandomId } from "../create-id.js";

/** Misma unión que PositionStatusV1 (evita ciclo con position-state). */
export type PositionRevisionStatusV1 =
  | "OPEN"
  | "PARTIAL"
  | "PROTECTED"
  | "CLOSED";

export type PositionRevisionOriginV1 =
  | "protect"
  | "reduce"
  | "override"
  | "stop";

export type PositionRevisionV1 = {
  revisionId: string;
  at: string;
  previousStop: number | null;
  nextStop: number | null;
  previousStatus: PositionRevisionStatusV1 | null;
  nextStatus: PositionRevisionStatusV1 | null;
  origin: PositionRevisionOriginV1;
  reason: string | null;
};

export const POSITION_REVISIONS_KEY = "revisions";

const VALID_ORIGINS = new Set<PositionRevisionOriginV1>([
  "protect",
  "reduce",
  "override",
  "stop",
]);

const VALID_STATUSES = new Set<PositionRevisionStatusV1>([
  "OPEN",
  "PARTIAL",
  "PROTECTED",
  "CLOSED",
]);

export type BuildPositionRevisionInputV1 = {
  at: string;
  previousStop?: number | null;
  nextStop?: number | null;
  previousStatus?: PositionRevisionStatusV1 | null;
  nextStatus?: PositionRevisionStatusV1 | null;
  origin?: PositionRevisionOriginV1;
  reason?: string | null;
  revisionId?: string | null;
};

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function finite(n: unknown): number | null {
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function asStatus(value: unknown): PositionRevisionStatusV1 | null {
  return typeof value === "string" &&
    VALID_STATUSES.has(value as PositionRevisionStatusV1)
    ? (value as PositionRevisionStatusV1)
    : null;
}

/** Factory pura. origin inválido → stop. */
export function buildPositionRevision(
  input: BuildPositionRevisionInputV1,
): PositionRevisionV1 {
  const origin: PositionRevisionOriginV1 =
    input.origin && VALID_ORIGINS.has(input.origin) ? input.origin : "stop";
  return {
    revisionId:
      nonEmpty(input.revisionId ?? null) ??
      `REV-${createRandomId().slice(0, 12)}`,
    at: nonEmpty(input.at) ?? "",
    previousStop: finite(input.previousStop ?? null),
    nextStop: finite(input.nextStop ?? null),
    previousStatus: input.previousStatus ?? null,
    nextStatus: input.nextStatus ?? null,
    origin,
    reason: nonEmpty(input.reason ?? null),
  };
}

/** Rehidrata una revisión. Dict inválido → null. */
export function positionRevisionFromUnknown(
  raw: unknown,
): PositionRevisionV1 | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const revisionId = nonEmpty(
    typeof o.revisionId === "string" ? o.revisionId : null,
  );
  const at = nonEmpty(typeof o.at === "string" ? o.at : null);
  const originRaw = typeof o.origin === "string" ? o.origin : null;
  if (!revisionId || !at) return null;
  if (!originRaw || !VALID_ORIGINS.has(originRaw as PositionRevisionOriginV1)) {
    return null;
  }
  return {
    revisionId,
    at,
    previousStop: finite(o.previousStop),
    nextStop: finite(o.nextStop),
    previousStatus: asStatus(o.previousStatus),
    nextStatus: asStatus(o.nextStatus),
    origin: originRaw as PositionRevisionOriginV1,
    reason: nonEmpty(typeof o.reason === "string" ? o.reason : null),
  };
}

/** Lista JSON → array. Entradas inválidas se omiten. */
export function revisionsFromUnknown(raw: unknown): PositionRevisionV1[] {
  if (!Array.isArray(raw)) return [];
  const out: PositionRevisionV1[] = [];
  for (const item of raw) {
    const rev = positionRevisionFromUnknown(item);
    if (rev) out.push(rev);
  }
  return out;
}

/** True si hay cambio real de stop o status (tolerancia 1e-9). */
export function stopOrStatusChanged(input: {
  previousStop: number | null | undefined;
  nextStop: number | null | undefined;
  previousStatus: PositionRevisionStatusV1 | null | undefined;
  nextStatus: PositionRevisionStatusV1 | null | undefined;
}): boolean {
  if (input.previousStatus !== input.nextStatus) return true;
  const prev = input.previousStop;
  const next = input.nextStop;
  if (prev == null && next == null) return false;
  if (prev == null || next == null) return true;
  return Math.abs(prev - next) > 1e-9;
}
