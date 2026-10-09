/**
 * AUTO · SISTEMA (Frente C) — conciliación en lenguaje llano (helper puro).
 *
 * El «¿está funcionando AUTO?» de la HOME ya se responde con frases; la **conciliación** (cuadre
 * de la posición y de la cartera) vivía **solo** en el `Detalle técnico`. Este helper traduce esa
 * lectura a una frase de primer nivel, sin re-derivar ni inventar:
 *
 * * Reutiliza los estados que ya publican los read-models (`portfolioReconciliation.status` de
 *   la auto-evaluación OI-6 y el `status`/contadores del lifecycle recon).
 * * `UNKNOWN ≠ 0`: sin lectura (cargando, error o sin estado) la frase es «Sin dato todavía»,
 *   nunca «Cuadra».
 * * Un estado desconocido se declara como hueco, no se colapsa a «todo bien».
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §5
 */

import { absentDataLabel } from "@/components/absent-data";
import { type AutoHomeRiskTone } from "@/features/auto/auto-home-summary";

export type AutoPlainReconciliationInput = {
  /** `portfolioReconciliation.status` de la auto-evaluación OI-6 (`ok` | `drift` | `blocked` | …). */
  portfolioStatus?: string | null;
  /** `status` del lifecycle recon (`ok` | `drift` | …). */
  lifecycleStatus?: string | null;
  driftCount?: number | null;
  lagCount?: number | null;
  blockedCount?: number | null;
  portfolioLoading?: boolean;
  portfolioError?: boolean;
  lifecycleLoading?: boolean;
  lifecycleError?: boolean;
};

export type AutoPlainReconciliationV1 = {
  /** `true` sólo si alguna de las dos lecturas se materializó. */
  available: boolean;
  tone: AutoHomeRiskTone;
  /** `Cuadra` | `Revisar` | `Bloqueado` | `Sin dato todavía`. */
  label: string;
  /** Frase de primer nivel (lenguaje de usuario). */
  sentence: string;
};

const LABELS: Record<AutoHomeRiskTone, string> = {
  ok: "Cuadra",
  attention: "Revisar",
  blocked: "Bloqueado",
  unknown: absentDataLabel(),
};

function _count(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/** `true` si el estado es un valor reconocido (medido), no un hueco ni un valor ajeno. */
function _known(status: string | null | undefined): boolean {
  return (
    status === "ok" ||
    status === "drift" ||
    status === "lag" ||
    status === "blocked"
  );
}

/**
 * Traduce la conciliación a un veredicto plano. Nunca inventa: si no hay lectura medible, declara
 * el hueco.
 */
export function buildPlainReconciliation(
  input: AutoPlainReconciliationInput,
): AutoPlainReconciliationV1 {
  const loaded =
    !input.portfolioLoading &&
    !input.portfolioError &&
    !input.lifecycleLoading &&
    !input.lifecycleError;
  const known =
    loaded && (_known(input.portfolioStatus) || _known(input.lifecycleStatus));

  if (!known) {
    return {
      available: false,
      tone: "unknown",
      label: LABELS.unknown,
      sentence: "Todavía no hay una lectura de conciliación.",
    };
  }

  const blocked =
    input.portfolioStatus === "blocked" || input.lifecycleStatus === "blocked";
  const drift =
    input.portfolioStatus === "drift" ||
    input.lifecycleStatus === "drift" ||
    _count(input.driftCount) > 0;
  const lag = input.lifecycleStatus === "lag" || _count(input.lagCount) > 0;
  const blockedCount = _count(input.blockedCount);

  if (blocked || blockedCount > 0) {
    return {
      available: true,
      tone: "blocked",
      label: LABELS.blocked,
      sentence:
        "Hay un bloqueo en el cuadre: AUTO no debería abrir posiciones nuevas.",
    };
  }
  if (drift || lag) {
    return {
      available: true,
      tone: "attention",
      label: LABELS.attention,
      sentence:
        "Hay diferencias entre lo declarado y lo real: revísalas antes de confiar en nuevas entradas.",
    };
  }
  return {
    available: true,
    tone: "ok",
    label: LABELS.ok,
    sentence: "Lo declarado y lo real cuadran. Sin diferencias pendientes.",
  };
}
