/**
 * Prefill de `signedStop` desde drag B-γ del gráfico → Confirm.
 * Memoria de proceso + evento; el panel consume al cargar el ítem activo.
 */

export const CHART_SIGNED_STOP_PREFILL_EVENT =
  "bolsa:chart-signed-stop-prefill" as const;

export type ChartSignedStopPrefill = {
  instrumentId: string;
  signedStop: number;
};

type PrefillInternal = ChartSignedStopPrefill & { at: number };

let prefill: PrefillInternal | null = null;

export function setChartSignedStopPrefill(next: ChartSignedStopPrefill): void {
  if (
    !next.instrumentId ||
    typeof next.signedStop !== "number" ||
    !Number.isFinite(next.signedStop) ||
    next.signedStop <= 0
  ) {
    return;
  }
  prefill = { ...next, at: Date.now() };
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

export function peekChartSignedStopPrefill(): ChartSignedStopPrefill | null {
  if (!prefill) return null;
  return {
    instrumentId: prefill.instrumentId,
    signedStop: prefill.signedStop,
  };
}

/** Consume si coincide el instrumento (o sin filtro). */
export function consumeChartSignedStopPrefill(
  instrumentId?: string | null,
): number | null {
  if (!prefill) return null;
  if (instrumentId && prefill.instrumentId !== instrumentId) return null;
  const stop = prefill.signedStop;
  prefill = null;
  return stop;
}

/** Test / reset. */
export function clearChartSignedStopPrefill(): void {
  prefill = null;
}
