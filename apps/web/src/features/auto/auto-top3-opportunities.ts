/**
 * AUTO UI REFACTOR 4.0 (P3) — TOP 3 OPORTUNIDADES (read-model puro).
 *
 * Copia el DTO persistido por el motor (`GET /api/top3-opportunities/latest`) y lo traduce a
 * lenguaje de usuario. **No re-calcula el score**: el ranking lo produce el motor
 * (`plan.ranked` → `_v2_persist_top3`), la UI sólo presenta.
 *
 * Invariantes (spec AUTO UI definitiva §4 §5 §8):
 * - El título es «TOP 3 OPORTUNIDADES», nunca «mejores acciones».
 * - Un slot sin hecho posterior se queda «Estado: propuesta»: ranking ≠ compra.
 * - `scoring_historico_sin_campeon` es un motivo visible («Puntuado sin evidencia completa»).
 * - Vacío («Sin TOP3 todavía») ≠ hueco («Sin dato todavía»).
 *
 * @see docs/engineering/spec-auto-ui-definitiva-2026-10-07.md
 */

export const AUTO_TOP3_TITLE = "TOP 3 OPORTUNIDADES";
export const AUTO_TOP3_EMPTY_LABEL = "Sin TOP3 todavía";
export const AUTO_TOP3_NO_DATA_LABEL = "Sin dato todavía";
export const AUTO_TOP3_PROPOSAL_LABEL = "Estado: propuesta";
export const AUTO_TOP3_DEGRADED_REASON = "scoring_historico_sin_campeon";
export const AUTO_TOP3_DEGRADED_LABEL = "Puntuado sin evidencia completa";
export const AUTO_TOP3_RANK_NOTE =
  "Ranking ≠ decisión: estar arriba no significa que AUTO haya comprado.";

export type AutoTop3DtoV1 = {
  runId: string;
  items?: {
    rank: number;
    assetId: string;
    score: number;
    regime?: string | null;
    reasons?: string[];
    createdAt: string;
    components?: Record<string, unknown>;
  }[];
};

export type AutoTop3Strength = "strong" | "moderate" | "weak" | "unknown";

export type AutoTop3SlotV1 = {
  rank: number;
  assetId: string;
  /** `87/100` o `Sin dato todavía`. */
  scoreLabel: string;
  strengthLabel: string;
  strength: AutoTop3Strength;
  /** Motivo visible del slot, si procede (p. ej. degradado). */
  reasonLabel: string | null;
  /** Estado del peldaño: hoy siempre «propuesta» (ranking ≠ decisión). */
  stateLabel: string;
  regimeLabel: string | null;
};

export type AutoTop3ViewV1 = {
  runId: string;
  slots: AutoTop3SlotV1[];
  isEmpty: boolean;
  /** Etiqueta de vacío (no hay foto). */
  emptyLabel: string;
  rankNote: string;
};

/** Normaliza el score del motor (0..1) a `NN/100`. Un valor ilegible es un hueco declarado. */
export function formatOpportunityScore(
  score: number | null | undefined,
): string {
  if (score == null || !Number.isFinite(score)) return AUTO_TOP3_NO_DATA_LABEL;
  const pct = score <= 1 ? score * 100 : score;
  const clamped = Math.max(0, Math.min(100, pct));
  return `${Math.round(clamped)}/100`;
}

export function opportunityStrengthLabel(score: number | null | undefined): {
  strength: AutoTop3Strength;
  label: string;
} {
  if (score == null || !Number.isFinite(score)) {
    return { strength: "unknown", label: AUTO_TOP3_NO_DATA_LABEL };
  }
  const pct = score <= 1 ? score * 100 : score;
  if (pct >= 75) return { strength: "strong", label: "Oportunidad fuerte" };
  if (pct >= 50) return { strength: "moderate", label: "Oportunidad moderada" };
  return { strength: "weak", label: "Oportunidad débil" };
}

function humanReasons(reasons: readonly string[] | undefined): string | null {
  if (!reasons) return null;
  if (reasons.includes(AUTO_TOP3_DEGRADED_REASON)) {
    return AUTO_TOP3_DEGRADED_LABEL;
  }
  return null;
}

export function buildAutoTop3View(
  dto: AutoTop3DtoV1 | null | undefined,
): AutoTop3ViewV1 {
  const items = dto?.items ?? [];
  if (!dto || dto.runId === "" || items.length === 0) {
    return {
      runId: dto?.runId ?? "",
      slots: [],
      isEmpty: true,
      emptyLabel: AUTO_TOP3_EMPTY_LABEL,
      rankNote: AUTO_TOP3_RANK_NOTE,
    };
  }

  const slots = [...items]
    .sort((a, b) => a.rank - b.rank)
    .map((item) => {
      const { strength, label } = opportunityStrengthLabel(item.score);
      return {
        rank: item.rank,
        assetId: item.assetId,
        scoreLabel: formatOpportunityScore(item.score),
        strengthLabel: label,
        strength,
        reasonLabel: humanReasons(item.reasons),
        stateLabel: AUTO_TOP3_PROPOSAL_LABEL,
        regimeLabel: item.regime?.trim() ? item.regime : null,
      };
    });

  return {
    runId: dto.runId,
    slots,
    isEmpty: false,
    emptyLabel: AUTO_TOP3_EMPTY_LABEL,
    rankNote: AUTO_TOP3_RANK_NOTE,
  };
}
