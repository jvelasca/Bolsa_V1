/**
 * V1.26 — geometría operativa única (fail-closed).
 * LONG: stop < entry [< T1 < T2]. SHORT: [T2 < T1 <] entry < stop.
 * No es check_opening. No es OrderIntent.
 */

export type OperationalLevelsDirectionV1 = "long" | "short";

export type OperationalLevelsReasonV1 =
  | "stop_wrong_side"
  | "targets_invalid"
  | "risk_non_positive";

export type OperationalLevelsVerdictV1 = {
  ok: boolean;
  reason: OperationalLevelsReasonV1 | null;
  riskDistance: number | null;
};

const EPS = 1e-9;

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function asDirection(raw: unknown): OperationalLevelsDirectionV1 | null {
  return raw === "long" || raw === "short" ? raw : null;
}

/**
 * Distancia adversa (pérdida vs entry). Stop al lado de beneficio → 0.
 * long: max(0, entry − stop). short: max(0, stop − entry).
 */
export function adverseExposure(
  direction: OperationalLevelsDirectionV1,
  entry: number,
  stop: number,
): number {
  if (direction === "long") return Math.max(0, entry - stop);
  return Math.max(0, stop - entry);
}

export function validateOperationalLevels(input: {
  direction: unknown;
  entry: unknown;
  stop: unknown;
  target1?: unknown;
  target2?: unknown;
}): OperationalLevelsVerdictV1 {
  const direction = asDirection(input.direction);
  const entry = finite(input.entry) ? input.entry : null;
  const stop = finite(input.stop) ? input.stop : null;
  if (
    direction == null ||
    entry == null ||
    entry <= 0 ||
    stop == null ||
    stop <= 0
  ) {
    return { ok: false, reason: "risk_non_positive", riskDistance: null };
  }

  const sideOk = direction === "long" ? stop < entry - EPS : stop > entry + EPS;
  if (!sideOk) {
    return { ok: false, reason: "stop_wrong_side", riskDistance: null };
  }

  const riskDistance = adverseExposure(direction, entry, stop);
  if (riskDistance <= EPS) {
    return { ok: false, reason: "risk_non_positive", riskDistance: 0 };
  }

  const t1 = finite(input.target1) ? input.target1 : null;
  const t2 = finite(input.target2) ? input.target2 : null;
  if (t1 != null) {
    const t1Ok = direction === "long" ? t1 > entry + EPS : t1 < entry - EPS;
    if (!t1Ok) {
      return { ok: false, reason: "targets_invalid", riskDistance };
    }
  }
  if (t2 != null) {
    const t2Ok = direction === "long" ? t2 > entry + EPS : t2 < entry - EPS;
    if (!t2Ok) {
      return { ok: false, reason: "targets_invalid", riskDistance };
    }
  }
  if (t1 != null && t2 != null) {
    const ordered = direction === "long" ? t2 > t1 + EPS : t2 < t1 - EPS;
    if (!ordered) {
      return { ok: false, reason: "targets_invalid", riskDistance };
    }
  }

  return { ok: true, reason: null, riskDistance };
}
