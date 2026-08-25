/**
 * Etiquetas legibles para métodos de piernas Composite (v1.1 liquidez).
 * Python emite keys (`adv_mega`, `mcap_large`…); la UI solo traduce.
 */

const LIQUIDITY_METHOD_LABELS: Record<string, string> = {
  adv_mega: "ADV mega",
  adv_very_high: "ADV muy alta",
  adv_high: "ADV alta",
  adv_medium: "ADV media",
  adv_low: "ADV baja",
  adv_very_low: "ADV muy baja",
  adv_missing: "sin ADV",
  mcap_mega: "mcap mega",
  mcap_large: "mcap large",
  mcap_mid_large: "mcap mid-large",
  mcap_mid: "mcap mid",
  mcap_small: "mcap small",
  mcap_micro: "mcap micro",
  mcap_missing: "sin mcap",
};

export function formatCompositeLegMethod(
  method: string | null | undefined,
): string | null {
  if (!method || !method.trim()) return null;
  const key = method.trim();
  return LIQUIDITY_METHOD_LABELS[key] ?? key;
}

/** Ciclo 7 — honesty de status de pierna Composite (esp. portfolioConstraints). */
export function formatCompositeLegStatus(
  status: string | null | undefined,
): string {
  if (!status || !status.trim()) return "—";
  switch (status.trim()) {
    case "not_evaluated":
      return "no en Composite (Fit en gate)";
    case "stub":
      return "stub";
    case "missing":
      return "faltante";
    case "ok":
      return "ok";
    default:
      return status.trim();
  }
}
