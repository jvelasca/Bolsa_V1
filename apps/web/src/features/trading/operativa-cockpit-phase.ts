/**
 * Re-export shared Mercado cockpit phase (V1.38 — fuente única en @bolsa/shared).
 */
export {
  MERCADO_COCKPIT_PHASES,
  MERCADO_COCKPIT_PHASE_LABEL,
  mercadoCockpitNoLevelsCopy,
  mercadoCockpitPrimaryCta,
  mercadoCockpitShowsPlanLevels,
  resolveMercadoCockpitPhase,
  resolveMercadoTrailingCopy,
  type MercadoCockpitPhase,
  type MercadoCockpitPhaseInput,
  type MercadoTrailingCopyV1,
  type MercadoTrailingStatusLabel,
} from "@bolsa/shared";

import { MERCADO_COCKPIT_PHASE_LABEL } from "@bolsa/shared";

/** V1.60 — hint POV en chip fase cuando posición abierta (T2 / recon). */
export function mercadoCockpitPosicionPhaseLabel(
  povOperatingState?: string | null,
): string {
  const base = MERCADO_COCKPIT_PHASE_LABEL.posicion;
  switch (povOperatingState) {
    case "T2_READY":
      return `${base} · T2 listo`;
    case "T2_EXECUTED":
      return `${base} · T2 ejecutado`;
    case "RECONCILIATION_DRIFT":
      return `${base} · Recon drift`;
    case "RECONCILIATION_ERROR":
      return `${base} · Recon error`;
    default:
      return base;
  }
}
