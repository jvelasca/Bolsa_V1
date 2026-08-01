/**
 * Etiquetas legibles para métodos de piernas Composite (v1.1 liquidez).
 * Python emite keys (`adv_mega`, `mcap_large`…); la UI solo traduce.
 */

const LIQUIDITY_METHOD_LABELS: Record<string, string> = {
  adv_mega: 'ADV mega',
  adv_very_high: 'ADV muy alta',
  adv_high: 'ADV alta',
  adv_medium: 'ADV media',
  adv_low: 'ADV baja',
  adv_very_low: 'ADV muy baja',
  adv_missing: 'sin ADV',
  mcap_mega: 'mcap mega',
  mcap_large: 'mcap large',
  mcap_mid_large: 'mcap mid-large',
  mcap_mid: 'mcap mid',
  mcap_small: 'mcap small',
  mcap_micro: 'mcap micro',
  mcap_missing: 'sin mcap',
};

export function formatCompositeLegMethod(
  method: string | null | undefined,
): string | null {
  if (!method || !method.trim()) return null;
  const key = method.trim();
  return LIQUIDITY_METHOD_LABELS[key] ?? key;
}
