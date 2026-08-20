/** Perfil de comisiones simuladas (estilo broker retail EU). */
export type CommissionPresetId =
  | "standard_es"
  | "xtb_zero_stock"
  | "ibkr_tiered"
  | "custom"
  | "none";

export interface CommissionProfile {
  presetId: CommissionPresetId;
  label: string;
  /** Comisión sobre importe operado (%). */
  stockCommissionPct: number;
  /** Mínimo por operación en moneda de la cuenta. */
  stockCommissionMin: number;
  /** Máximo por operación (null = sin tope). */
  stockCommissionMax: number | null;
  /** IVA u otros impuestos sobre la comisión (%). España: 21. */
  vatOnCommissionPct: number;
  /** Comisión de conversión FX (% del importe). */
  fxConversionPct: number;
  /** Custodia anual (% del valor de cartera, null = no aplica). */
  custodyAnnualPct: number | null;
}

export type TaxJurisdiction = "ES" | "EU_OTHER" | "US" | "CUSTOM";
export type CostBasisMethod = "fifo" | "average";

export interface TaxProfile {
  jurisdiction: TaxJurisdiction;
  costBasisMethod: CostBasisMethod;
  /** Impuesto de transmisiones / stamp duty en compras (%). España acciones ~0,2 %. */
  stampDutyBuyPct: number;
  /** Retención sobre dividendos (%). */
  dividendWithholdingPct: number;
  /** Solo proyección informativa — no se retiene en simulación. */
  capitalGainsTaxPct: number | null;
  fiscalYearStartMonth: number;
}

/**
 * Preferencias de cuenta (comisiones/fiscal).
 * El perfil inversor es catálogo ART-PROFILE (`investor_profiles` + `activeProfileId`).
 */
export interface AccountSettings {
  commission: CommissionProfile;
  tax: TaxProfile;
  /** Notas internas visibles en la ficha de cuenta. Opcional en el wire (puede faltar). */
  notes?: string | null;
}

export interface UpdateAccountSettingsRequestDto {
  settings: AccountSettings;
}

export interface TradeFeeBreakdownDto {
  commission: number;
  vatOnCommission: number;
  stampDuty: number;
  fxConversion: number;
  total: number;
  currency: string;
}

export const COMMISSION_PRESETS: Record<
  Exclude<CommissionPresetId, "custom">,
  CommissionProfile
> = {
  none: {
    presetId: "none",
    label: "Sin comisiones",
    stockCommissionPct: 0,
    stockCommissionMin: 0,
    stockCommissionMax: null,
    vatOnCommissionPct: 0,
    fxConversionPct: 0,
    custodyAnnualPct: null,
  },
  xtb_zero_stock: {
    presetId: "xtb_zero_stock",
    label: "Zero comisión acciones (spread)",
    stockCommissionPct: 0,
    stockCommissionMin: 0,
    stockCommissionMax: null,
    vatOnCommissionPct: 0,
    fxConversionPct: 0.5,
    custodyAnnualPct: null,
  },
  standard_es: {
    presetId: "standard_es",
    label: "Broker estándar ES",
    stockCommissionPct: 0.1,
    stockCommissionMin: 1,
    stockCommissionMax: 29,
    vatOnCommissionPct: 21,
    fxConversionPct: 0.5,
    custodyAnnualPct: 0.2,
  },
  ibkr_tiered: {
    presetId: "ibkr_tiered",
    label: "IBKR tiered (EU)",
    stockCommissionPct: 0.05,
    stockCommissionMin: 1.25,
    stockCommissionMax: null,
    vatOnCommissionPct: 21,
    fxConversionPct: 0.002,
    custodyAnnualPct: null,
  },
};

export const TAX_PRESETS: Record<TaxJurisdiction, TaxProfile> = {
  ES: {
    jurisdiction: "ES",
    costBasisMethod: "fifo",
    stampDutyBuyPct: 0.2,
    dividendWithholdingPct: 19,
    capitalGainsTaxPct: null,
    fiscalYearStartMonth: 1,
  },
  EU_OTHER: {
    jurisdiction: "EU_OTHER",
    costBasisMethod: "fifo",
    stampDutyBuyPct: 0,
    dividendWithholdingPct: 15,
    capitalGainsTaxPct: null,
    fiscalYearStartMonth: 1,
  },
  US: {
    jurisdiction: "US",
    costBasisMethod: "fifo",
    stampDutyBuyPct: 0,
    dividendWithholdingPct: 30,
    capitalGainsTaxPct: null,
    fiscalYearStartMonth: 1,
  },
  CUSTOM: {
    jurisdiction: "CUSTOM",
    costBasisMethod: "fifo",
    stampDutyBuyPct: 0,
    dividendWithholdingPct: 0,
    capitalGainsTaxPct: null,
    fiscalYearStartMonth: 1,
  },
};

export function resolveCommissionProfile(
  presetId: CommissionPresetId,
  overrides?: Partial<CommissionProfile>,
): CommissionProfile {
  if (presetId === "custom") {
    return {
      presetId: "custom",
      label: overrides?.label ?? "Personalizado",
      stockCommissionPct: overrides?.stockCommissionPct ?? 0.1,
      stockCommissionMin: overrides?.stockCommissionMin ?? 1,
      stockCommissionMax: overrides?.stockCommissionMax ?? null,
      vatOnCommissionPct: overrides?.vatOnCommissionPct ?? 21,
      fxConversionPct: overrides?.fxConversionPct ?? 0,
      custodyAnnualPct: overrides?.custodyAnnualPct ?? null,
    };
  }
  const base = COMMISSION_PRESETS[presetId];
  return { ...base, ...overrides, presetId: base.presetId };
}

export function defaultAccountSettings(
  commissionPresetId: CommissionPresetId = "standard_es",
  jurisdiction: TaxJurisdiction = "ES",
): AccountSettings {
  return {
    commission: resolveCommissionProfile(commissionPresetId),
    tax: { ...TAX_PRESETS[jurisdiction] },
    notes: null,
  };
}

/** Calcula comisiones e impuestos de una operación (cliente y servidor). */
export function calculateTradeFees(
  notional: number,
  side: "buy" | "sell",
  settings: AccountSettings,
  options?: { isFxConversion?: boolean; currency?: string },
): TradeFeeBreakdownDto {
  const profile = settings.commission;
  const tax = settings.tax;
  let commissionAmount = 0;
  if (profile.stockCommissionPct > 0 || profile.stockCommissionMin > 0) {
    commissionAmount = (notional * profile.stockCommissionPct) / 100;
    commissionAmount = Math.max(commissionAmount, profile.stockCommissionMin);
    if (profile.stockCommissionMax != null) {
      commissionAmount = Math.min(commissionAmount, profile.stockCommissionMax);
    }
  }
  const vatOnCommission = (commissionAmount * profile.vatOnCommissionPct) / 100;
  const stampDuty =
    side === "buy" && tax.stampDutyBuyPct > 0
      ? (notional * tax.stampDutyBuyPct) / 100
      : 0;
  const fxConversion =
    options?.isFxConversion && profile.fxConversionPct > 0
      ? (notional * profile.fxConversionPct) / 100
      : 0;
  const total = commissionAmount + vatOnCommission + stampDuty + fxConversion;
  return {
    commission: commissionAmount,
    vatOnCommission,
    stampDuty,
    fxConversion,
    total,
    currency: options?.currency ?? "EUR",
  };
}
