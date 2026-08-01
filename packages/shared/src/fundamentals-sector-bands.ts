/**
 * FIE F2.2 — Umbrales de gate normalizados por sector (`fund_sector_bands_v1`).
 *
 * Cuando el gate lleva `sectorBandsVersion`, el evaluador (Python) sustituye
 * los valores de condiciones banded por el perfil del sector del instrumento.
 * Sectores desconocidos → se mantienen los umbrales de la UI (fallback).
 * `skip` → la condición no aplica (p.ej. Altman en bancos).
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

import type { RuleOperator } from './strategy-rules.js';
import type { FundamentalMetric } from './fundamentals-gate.js';

export const FUND_SECTOR_BANDS_VERSION = 'fund_sector_bands_v1' as const;

export type BandedFundamentalMetric = Extract<
  FundamentalMetric,
  | 'trailingPe'
  | 'roe'
  | 'debtToEquity'
  | 'currentRatio'
  | 'altmanZ'
  | 'fcfYield'
  | 'operatingMargin'
>;

export type SectorBandRule =
  | { operator: Extract<RuleOperator, 'lte' | 'gte'>; value: number }
  | 'skip';

export type SectorBandProfile = Partial<Record<BandedFundamentalMetric, SectorBandRule>>;

/** Perfil fallback / sector desconocido (también seed al activar bandas sin UI). */
export const SECTOR_BAND_DEFAULT: SectorBandProfile = {
  trailingPe: { operator: 'lte', value: 25 },
  roe: { operator: 'gte', value: 0.1 },
  debtToEquity: { operator: 'lte', value: 1.5 },
  currentRatio: { operator: 'gte', value: 1.0 },
  altmanZ: { operator: 'gte', value: 1.8 },
  fcfYield: { operator: 'gte', value: 0.02 },
  operatingMargin: { operator: 'gte', value: 0.08 },
};

/**
 * Overlays Yahoo `summaryProfile.sector` (exact match case-insensitive vía resolve).
 * Solo diferencias respecto a DEFAULT; el merge completa el resto.
 */
export const SECTOR_BAND_OVERLAYS: Record<string, SectorBandProfile> = {
  Technology: {
    trailingPe: { operator: 'lte', value: 40 },
    roe: { operator: 'gte', value: 0.12 },
    debtToEquity: { operator: 'lte', value: 1.2 },
    operatingMargin: { operator: 'gte', value: 0.12 },
  },
  'Communication Services': {
    trailingPe: { operator: 'lte', value: 30 },
    roe: { operator: 'gte', value: 0.1 },
    debtToEquity: { operator: 'lte', value: 1.8 },
  },
  Healthcare: {
    trailingPe: { operator: 'lte', value: 35 },
    roe: { operator: 'gte', value: 0.1 },
    operatingMargin: { operator: 'gte', value: 0.1 },
  },
  'Consumer Cyclical': {
    trailingPe: { operator: 'lte', value: 28 },
    debtToEquity: { operator: 'lte', value: 1.8 },
    currentRatio: { operator: 'gte', value: 1.1 },
  },
  'Consumer Defensive': {
    trailingPe: { operator: 'lte', value: 22 },
    roe: { operator: 'gte', value: 0.12 },
    debtToEquity: { operator: 'lte', value: 1.2 },
  },
  Industrials: {
    trailingPe: { operator: 'lte', value: 22 },
    debtToEquity: { operator: 'lte', value: 1.4 },
    altmanZ: { operator: 'gte', value: 2.0 },
  },
  Energy: {
    trailingPe: { operator: 'lte', value: 18 },
    roe: { operator: 'gte', value: 0.08 },
    debtToEquity: { operator: 'lte', value: 1.2 },
    fcfYield: { operator: 'gte', value: 0.04 },
  },
  'Basic Materials': {
    trailingPe: { operator: 'lte', value: 18 },
    roe: { operator: 'gte', value: 0.08 },
    debtToEquity: { operator: 'lte', value: 1.0 },
  },
  Utilities: {
    trailingPe: { operator: 'lte', value: 20 },
    roe: { operator: 'gte', value: 0.08 },
    debtToEquity: { operator: 'lte', value: 2.5 },
    currentRatio: { operator: 'gte', value: 0.8 },
    altmanZ: { operator: 'gte', value: 1.2 },
    fcfYield: { operator: 'gte', value: 0.03 },
  },
  /** Bancos / seguros: D/E y Altman clásico poco aplicables. */
  'Financial Services': {
    trailingPe: { operator: 'lte', value: 15 },
    roe: { operator: 'gte', value: 0.08 },
    debtToEquity: 'skip',
    currentRatio: 'skip',
    altmanZ: 'skip',
    fcfYield: 'skip',
    operatingMargin: { operator: 'gte', value: 0.15 },
  },
  'Real Estate': {
    trailingPe: { operator: 'lte', value: 25 },
    roe: { operator: 'gte', value: 0.06 },
    debtToEquity: { operator: 'lte', value: 2.5 },
    altmanZ: 'skip',
    fcfYield: { operator: 'gte', value: 0.03 },
  },
};

const OVERLAY_BY_LOWER = new Map(
  Object.entries(SECTOR_BAND_OVERLAYS).map(([k, v]) => [k.toLowerCase(), v] as const),
);

export function resolveSectorBandProfile(sector: string | null | undefined): {
  known: boolean;
  profile: SectorBandProfile;
  sectorKey: string | null;
} {
  if (!sector || typeof sector !== 'string') {
    return { known: false, profile: { ...SECTOR_BAND_DEFAULT }, sectorKey: null };
  }
  const overlay = OVERLAY_BY_LOWER.get(sector.trim().toLowerCase());
  if (!overlay) {
    return { known: false, profile: { ...SECTOR_BAND_DEFAULT }, sectorKey: null };
  }
  return {
    known: true,
    profile: { ...SECTOR_BAND_DEFAULT, ...overlay },
    sectorKey: sector.trim(),
  };
}

/** Condiciones seed desde el perfil default (UI / build gate). */
export function defaultSectorBandConditions(): Array<{
  metric: BandedFundamentalMetric;
  operator: Extract<RuleOperator, 'lte' | 'gte'>;
  value: number;
}> {
  const out: Array<{
    metric: BandedFundamentalMetric;
    operator: Extract<RuleOperator, 'lte' | 'gte'>;
    value: number;
  }> = [];
  for (const [metric, rule] of Object.entries(SECTOR_BAND_DEFAULT) as Array<
    [BandedFundamentalMetric, SectorBandRule]
  >) {
    if (rule === 'skip') continue;
    out.push({ metric, operator: rule.operator, value: rule.value });
  }
  return out;
}
