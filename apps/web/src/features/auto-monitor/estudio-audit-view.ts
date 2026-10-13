/**
 * P2 (sello 2) — helpers PUROS de la auditoría por valor de ESTUDIO (testeables).
 *
 * Regla de oro: un dato ausente se declara «Sin dato todavía», JAMÁS un `0` que finja
 * medición; y un valor solo se rotula «Medido» si R y dinero alcanzan su suelo de muestra.
 */

export type EstudioValueState = "measured" | "unmeasured";

export const ESTUDIO_VALUE_LABELS: Record<EstudioValueState, string> = {
  measured: "Medido (R y dinero)",
  unmeasured: "Sin dato todavía",
};

export function estudioValueState(measured: boolean): EstudioValueState {
  return measured ? "measured" : "unmeasured";
}

/** R en múltiplos del riesgo; `null` ⇒ «Sin dato todavía» (nunca `0`). */
export function formatR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}R`;
}

/** Porcentaje; `null` ⇒ «Sin dato todavía» (nunca `0`). */
export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${(value * 100).toFixed(0)}%`;
}

/** Identidad EXACTA de la estrategia; hueco declarado si no viaja. */
export function describeStrategy(strategy: {
  presetKey?: string | null;
  version?: string | null;
}): string {
  const preset = strategy.presetKey?.trim();
  if (!preset) return "Sin dato todavía (identidad no declarada)";
  const version = strategy.version?.trim();
  return version ? `${preset} · ${version}` : preset;
}

/** Veredicto del resultado en R, con el motivo declarado si lo hay. */
export function describeVerdict(resultR: {
  verdict?: string;
  verdictReason?: string | null;
}): string {
  const verdict = (resultR.verdict || "NOT_MEASURED").trim();
  const reason = resultR.verdictReason?.trim();
  return reason ? `${verdict} · ${reason}` : verdict;
}

/** Día de calendario o «sin día» cuando no viaja (nunca se inventa una fecha). */
export function formatDay(value: string | null | undefined): string {
  const day = value?.trim();
  return day ? day : "sin día";
}

/**
 * Recuento de la señal del valor, con los ciclos ENLAZABLES explícitos para cuadrar con la
 * lista: `linkedCycles` debe ser igual a `len(cycles[])`. Los ciclos sin `cycleId` (no
 * enlazables) y los `cycleId` repetidos (deduplicados) se declaran aparte, nunca se ocultan.
 */
export function describeSignal(
  signal: {
    cycles?: number;
    linkedCycles?: number;
    unlinkedCycles?: number;
    duplicateCycles?: number;
    measuredCycles?: number;
  },
  listedCycles: number,
): string {
  const total = signal.cycles ?? listedCycles;
  // Compatibilidad: un artefacto antiguo sin `linkedCycles` cae al nº realmente listado.
  const linked = signal.linkedCycles ?? listedCycles;
  const measured = signal.measuredCycles ?? 0;
  const parts = [
    `${linked} de ${total} ciclos enlazables`,
    `${measured} medidos`,
  ];
  const unlinked = signal.unlinkedCycles ?? 0;
  if (unlinked > 0) parts.push(`${unlinked} sin enlazar`);
  const duplicates = signal.duplicateCycles ?? 0;
  if (duplicates > 0) parts.push(`${duplicates} repetidos`);
  return parts.join(" · ");
}

/** Etiqueta de un ciclo: ventana entrada→salida y R realizado (huecos declarados). */
export function describeCycle(cycle: {
  entryDay?: string | null;
  exitDay?: string | null;
  realizedR?: number | null;
}): string {
  return `${formatDay(cycle.entryDay)} → ${formatDay(cycle.exitDay)} · ${formatR(
    cycle.realizedR,
  )}`;
}
