/**
 * Prefill de `signedStop` desde drag B-γ del gráfico → Confirm.
 * Memoria de proceso + evento; el panel consume al cargar el ítem activo.
 */

export const CHART_SIGNED_STOP_PREFILL_EVENT =
  "bolsa:chart-signed-stop-prefill" as const;

/** TTL corto: prefill temporal, no estado durable. */
export const CHART_PREFILL_TTL_MS = 30_000;

export type ChartSignedStopPrefill = {
  instrumentId: string;
  signedStop: number;
};

export type ChartSignedStopPrefillContext = {
  tradePlanId?: string | null;
  currentStop?: number | null;
};

type PrefillInternal = ChartSignedStopPrefill & {
  at: number;
  tradePlanId?: string;
  currentStop?: number;
};

let prefill: PrefillInternal | null = null;

function finiteStop(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : null;
}

export function isChartSignedStopPrefillExpired(
  entry: Pick<PrefillInternal, "at">,
  now = Date.now(),
): boolean {
  return now - entry.at > CHART_PREFILL_TTL_MS;
}

function invalidateExpiredPrefill(now = Date.now()): void {
  if (prefill && isChartSignedStopPrefillExpired(prefill, now)) {
    prefill = null;
  }
}

function contextMatches(
  entry: PrefillInternal,
  context?: ChartSignedStopPrefillContext,
): boolean {
  if (!context) return true;
  if (
    context.tradePlanId != null &&
    context.tradePlanId.trim() !== "" &&
    entry.tradePlanId != null &&
    entry.tradePlanId !== context.tradePlanId
  ) {
    return false;
  }
  const ctxStop = finiteStop(context.currentStop);
  const entryStop = finiteStop(entry.currentStop);
  if (ctxStop != null && entryStop != null && ctxStop !== entryStop) {
    return false;
  }
  return true;
}

export function setChartSignedStopPrefill(
  next: ChartSignedStopPrefill & ChartSignedStopPrefillContext,
): void {
  if (
    !next.instrumentId ||
    typeof next.signedStop !== "number" ||
    !Number.isFinite(next.signedStop) ||
    next.signedStop <= 0
  ) {
    return;
  }
  const entry: PrefillInternal = {
    instrumentId: next.instrumentId,
    signedStop: next.signedStop,
    at: Date.now(),
  };
  const tradePlanId =
    typeof next.tradePlanId === "string" ? next.tradePlanId.trim() : "";
  if (tradePlanId) entry.tradePlanId = tradePlanId;
  const currentStop = finiteStop(next.currentStop);
  if (currentStop != null) entry.currentStop = currentStop;
  prefill = entry;
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent(CHART_SIGNED_STOP_PREFILL_EVENT, {
        detail: {
          instrumentId: next.instrumentId,
          signedStop: next.signedStop,
        },
      }),
    );
  }
}

export function peekChartSignedStopPrefill(
  instrumentId?: string | null,
  context?: ChartSignedStopPrefillContext,
): ChartSignedStopPrefill | null {
  invalidateExpiredPrefill();
  if (!prefill) return null;
  if (instrumentId && prefill.instrumentId !== instrumentId) return null;
  if (!contextMatches(prefill, context)) return null;
  return {
    instrumentId: prefill.instrumentId,
    signedStop: prefill.signedStop,
  };
}

/** Consume si coincide el instrumento (o sin filtro) y el contexto sigue vigente. */
export function consumeChartSignedStopPrefill(
  instrumentId?: string | null,
  context?: ChartSignedStopPrefillContext,
): number | null {
  invalidateExpiredPrefill();
  if (!prefill) return null;
  if (instrumentId && prefill.instrumentId !== instrumentId) return null;
  if (!contextMatches(prefill, context)) {
    prefill = null;
    return null;
  }
  const stop = prefill.signedStop;
  prefill = null;
  return stop;
}

/** Test / reset / invalidación explícita (close Confirm, abandonar Trading). */
export function clearChartSignedStopPrefill(): void {
  prefill = null;
}
