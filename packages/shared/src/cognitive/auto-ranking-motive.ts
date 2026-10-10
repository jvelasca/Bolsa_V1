/**
 * F5 — «Motivo de selección» del ranking AUTO, en lenguaje de usuario.
 *
 * El ranking de oportunidades de AUTO es un score **explicable**: cada componente se publica
 * con su valor y el combinado es su suma ponderada (`OPPORTUNITY_WEIGHTS`). Ese desglose es el
 * MOTIVO por el que una oportunidad entró en el TOP-N — y es lo que este módulo traduce a
 * etiquetas humanas para la historia de la operación.
 *
 * Este módulo es la **única casa** de las etiquetas de usuario de los componentes de ranking.
 * Un código NO catalogado NUNCA se pinta crudo: degrada a «Sin dato todavía» (regla de la casa,
 * igual que `entryReasonLabel`/`jitDenyLabel` en la web).
 *
 * Invariantes:
 * - **`ranking ≠ decisión`.** El motivo describe POR QUÉ el valor entró en el TOP-N
 *   (selección/ranking), NO la decisión de cartera (que vive en `PortfolioDecision`).
 * - **`UNKNOWN ≠ 0`.** Sin componentes durables el motivo es «Sin dato todavía» (⇒ `UNKNOWN`),
 *   jamás un valor de relleno ni un código crudo.
 *
 * @see packages/py/analytics/src/bolsa_analytics/cognitive/opportunity_ranker.py
 */

/** Rótulo honesto de un motivo de ranking no medible (nunca un código crudo). */
export const AUTO_RANKING_NO_DATA_LABEL = "Sin dato todavía";

/**
 * Orden CANÓNICO de los componentes del score de ranking (peso DESCENDENTE, según el ranker).
 * Es el orden en el que se listan los factores del motivo: el de mayor peso primero.
 */
export const AUTO_RANKING_COMPONENT_ORDER = [
  "edge",
  "robustness",
  "regime_fit",
  "momentum",
  "liquidity",
  "risk_reward",
  "execution_quality",
] as const;

export type AutoRankingComponentV1 =
  (typeof AUTO_RANKING_COMPONENT_ORDER)[number];

/** Etiquetas de usuario de los componentes del score de ranking (`opportunity_ranker`). */
export const AUTO_RANKING_COMPONENT_LABELS: Record<
  AutoRankingComponentV1,
  string
> = {
  edge: "Ventaja esperada",
  robustness: "Robustez",
  regime_fit: "Encaje con el régimen",
  momentum: "Momento",
  liquidity: "Liquidez",
  risk_reward: "Riesgo/beneficio",
  execution_quality: "Calidad de ejecución",
};

/**
 * Etiqueta humana de un componente de ranking. Un código no catalogado (o ausente) degrada a
 * «Sin dato todavía»: nunca se pinta el código crudo.
 */
export function autoRankingComponentLabel(
  code: string | null | undefined,
): string {
  if (code == null || code === "") return AUTO_RANKING_NO_DATA_LABEL;
  return (
    AUTO_RANKING_COMPONENT_LABELS[code as AutoRankingComponentV1] ??
    AUTO_RANKING_NO_DATA_LABEL
  );
}

function contributed(value: unknown): boolean {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

/**
 * Motivo de selección legible a partir del desglose del score (`components`): los factores que
 * CONTRIBUYERON (valor `> 0`), en orden canónico (peso descendente), unidos por `·`.
 *
 * Devuelve `null` si no hay componentes medibles (o ninguno contribuyó) ⇒ la superficie declara
 * «Sin dato todavía» (`UNKNOWN`). Un componente presente pero con código NO catalogado aparece
 * como «Sin dato todavía», nunca crudo — y por sí solo NO basta para declarar el motivo medido.
 *
 * `ranking ≠ decisión`: esto explica la SELECCIÓN (top-N), no la cartera.
 */
export function autoRankingMotiveLabel(
  components: Record<string, unknown> | null | undefined,
): string | null {
  if (components == null || typeof components !== "object") return null;

  const known = AUTO_RANKING_COMPONENT_ORDER.filter((code) =>
    contributed(components[code]),
  );
  // Un motivo hecho SÓLO de códigos no catalogados no está medido: se declara el hueco.
  if (known.length === 0) return null;

  const unknown = Object.keys(components).filter(
    (code) =>
      !(AUTO_RANKING_COMPONENT_ORDER as readonly string[]).includes(code) &&
      contributed(components[code]),
  );

  return [...known, ...unknown]
    .map((code) => autoRankingComponentLabel(code))
    .join(" · ");
}
