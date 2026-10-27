/**
 * O-4 — VEREDICTO DE LA VENTANA: la UI LEE lo que el gate declaró, no escribe una constante.
 *
 * El gate emite un veredicto por valor (`resultR.verdict`, con `measured`) dentro del DTO de
 * auditoría ESTUDIO. Esta vista NO recalcula el gate ni conoce sus umbrales: sólo agrega lo
 * que el artefacto ya declaró para poder pintar una línea de ventana honesta.
 *
 * Reglas duras:
 *
 * - **`UNKNOWN ≠ INCONCLUSIVE`.** Sin valores medidos el veredicto es `null`; la UI declara
 *   «no medido». Nunca se rellena con la constante histórica del gate.
 * - **No se inventa un veredicto de ventana.** Si los valores medidos declaran veredictos
 *   distintos, no hay un veredicto único: `measurement === "PARTIAL"` y `verdict === null`
 *   con el recuento por veredicto para que la UI lo publique tal cual.
 * - **`NOT_MEASURED` no es un veredicto.** Un valor que se declara así no cuenta como medido.
 */

/** Veredicto declarado por el gate para un valor. */
export const WINDOW_VERDICT_NOT_MEASURED = "NOT_MEASURED";

export type WindowVerdictMeasurement = "COMPLETE" | "PARTIAL" | "UNKNOWN";

export type WindowVerdictRead = {
  /** Veredicto único de la ventana, o `null` si no hay uno medido. */
  verdict: string | null;
  /** `UNKNOWN` = nada medido; `PARTIAL` = veredictos distintos conviviendo. */
  measurement: WindowVerdictMeasurement;
  measuredValues: number;
  totalValues: number;
  /** Recuento de veredictos MEDIDOS, ordenado por nombre para una pintura estable. */
  counts: ReadonlyArray<{ verdict: string; count: number }>;
};

type AuditValueLike = {
  measured?: boolean | null;
  resultR?: { verdict?: string | null; measured?: boolean | null } | null;
};

function declaredVerdict(value: AuditValueLike): string | null {
  const resultR = value.resultR ?? null;
  if (resultR === null || resultR.measured !== true) return null;
  const verdict = (resultR.verdict ?? "").trim();
  if (verdict === "" || verdict === WINDOW_VERDICT_NOT_MEASURED) return null;
  return verdict;
}

/**
 * Texto imprimible del veredicto leído. `absentLabel` es la etiqueta de hueco que usa la
 * pantalla; el hueco NUNCA se sustituye por el veredicto histórico del gate.
 */
export function describeWindowVerdict(
  read: WindowVerdictRead,
  absentLabel: string,
): string {
  if (read.measurement === "UNKNOWN") return absentLabel;
  if (read.measurement === "PARTIAL") {
    const detail = read.counts
      .map((entry) => `${entry.verdict} ${entry.count}`)
      .join(" · ");
    return `SIN VEREDICTO ÚNICO (${detail})`;
  }
  return read.verdict ?? absentLabel;
}

/**
 * Lee el veredicto de la ventana desde los valores del DTO de auditoría.
 *
 * No conoce umbrales, no decide y no consulta nada: agregación pura de lo declarado.
 */
export function readWindowVerdict(
  values: ReadonlyArray<AuditValueLike> | null | undefined,
): WindowVerdictRead {
  const totalValues = values?.length ?? 0;
  const counts = new Map<string, number>();
  for (const value of values ?? []) {
    const verdict = declaredVerdict(value);
    if (verdict === null) continue;
    counts.set(verdict, (counts.get(verdict) ?? 0) + 1);
  }
  const measuredValues = [...counts.values()].reduce((sum, n) => sum + n, 0);
  const ordered = [...counts.entries()]
    .map(([verdict, count]) => ({ verdict, count }))
    .sort((a, b) => a.verdict.localeCompare(b.verdict));

  if (measuredValues === 0) {
    return {
      verdict: null,
      measurement: "UNKNOWN",
      measuredValues: 0,
      totalValues,
      counts: [],
    };
  }
  if (ordered.length === 1) {
    return {
      verdict: ordered[0]!.verdict,
      measurement: "COMPLETE",
      measuredValues,
      totalValues,
      counts: ordered,
    };
  }
  return {
    verdict: null,
    measurement: "PARTIAL",
    measuredValues,
    totalValues,
    counts: ordered,
  };
}
