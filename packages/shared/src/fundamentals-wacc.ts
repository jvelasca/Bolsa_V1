/**
 * FIE F2.4 — WACC proxy por sector Yahoo (`fund_wacc_sector_v1`).
 *
 * Fallback cuando no hay beta CAPM (F2.6 `fund_capm_v1`).
 * Tasas ilustrativas versionadas. Cambiar tasas ⇒ bump de versión.
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

export const FUND_WACC_VERSION = 'fund_wacc_sector_v1' as const;

/** Fallback / sector desconocido (igual al r fijo F2.3). */
export const WACC_SECTOR_DEFAULT = 0.1;

/**
 * Overlays Yahoo `summaryProfile.sector` (match case-insensitive).
 * Valores en ratio (0.09 = 9%).
 */
export const WACC_SECTOR_OVERLAYS: Record<string, number> = {
  Technology: 0.095,
  'Communication Services': 0.085,
  Healthcare: 0.085,
  'Consumer Cyclical': 0.1,
  'Consumer Defensive': 0.075,
  Industrials: 0.09,
  Energy: 0.105,
  'Basic Materials': 0.095,
  Utilities: 0.065,
  'Financial Services': 0.1,
  'Real Estate': 0.075,
};

const OVERLAY_BY_LOWER = new Map(
  Object.entries(WACC_SECTOR_OVERLAYS).map(([k, v]) => [k.toLowerCase(), v] as const),
);

export function resolveSectorWacc(sector: string | null | undefined): {
  known: boolean;
  wacc: number;
  sectorKey: string | null;
  waccMethod: typeof FUND_WACC_VERSION;
} {
  if (!sector || typeof sector !== 'string') {
    return {
      known: false,
      wacc: WACC_SECTOR_DEFAULT,
      sectorKey: null,
      waccMethod: FUND_WACC_VERSION,
    };
  }
  const hit = OVERLAY_BY_LOWER.get(sector.trim().toLowerCase());
  if (hit == null) {
    return {
      known: false,
      wacc: WACC_SECTOR_DEFAULT,
      sectorKey: null,
      waccMethod: FUND_WACC_VERSION,
    };
  }
  return {
    known: true,
    wacc: hit,
    sectorKey: sector.trim(),
    waccMethod: FUND_WACC_VERSION,
  };
}
