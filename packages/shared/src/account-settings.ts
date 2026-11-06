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
    // Paridad con el dominio (`bolsa_domain.account_settings.TAX_PRESETS["ES"]`): el
    // tramo inicial del ahorro es el tipo con el que se estima la plusvalía. Es una
    // proyección, no una retención: la escala real es progresiva.
    capitalGainsTaxPct: 19,
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

/**
 * Catálogo único de PRESENTACIÓN de comisiones y fiscal.
 *
 * Panel de configuración, asistente de alta y ficha de cuenta leen de aquí: antes cada
 * superficie escribía sus propios hints y el catálogo se desincronizaba del preset real
 * (p. ej. mostraba «IVA 21 %» con un preset que ya no lo aplicaba).
 */
export const COMMISSION_PRESET_IDS: CommissionPresetId[] = [
  "standard_es",
  "xtb_zero_stock",
  "ibkr_tiered",
  "custom",
  "none",
];

export const TAX_JURISDICTION_LABELS: Record<TaxJurisdiction, string> = {
  ES: "España (ES)",
  EU_OTHER: "Unión Europea (otro)",
  US: "Estados Unidos",
  CUSTOM: "Personalizado (definir a mano)",
};

export const COST_BASIS_LABELS: Record<CostBasisMethod, string> = {
  fifo: "FIFO (primero en entrar, primero en salir)",
  average: "Coste medio ponderado",
};

export const COST_BASIS_SHORT_LABELS: Record<CostBasisMethod, string> = {
  fifo: "FIFO",
  average: "Coste medio",
};

export function commissionPresetLabel(id: CommissionPresetId): string {
  if (id === "custom") return "Personalizado";
  return COMMISSION_PRESETS[id].label;
}

function pctEs(value: number): string {
  return String(Number(value.toFixed(4))).replace(".", ",");
}

function amountEs(value: number, currency?: string): string {
  const amount = value.toFixed(2).replace(".", ",");
  return currency ? `${amount} ${currency}` : amount;
}

/**
 * Hint del preset derivado de SUS NÚMEROS (no de un texto paralelo): si mañana cambia
 * la comisión del preset, el hint cambia con ella.
 */
export function describeCommissionPreset(
  id: CommissionPresetId,
  options?: { currency?: string | null },
): string {
  if (id === "custom") {
    return "Parámetros manuales de comisión, IVA, FX y custodia";
  }
  if (id === "none") {
    // Honestidad (COM-D12): «sin comisiones» NO significa «sin impuestos». El impuesto
    // de transmisiones sale del perfil fiscal, no del preset de comisión: con ES el
    // backend sigue cobrando el 0,2 % en las compras.
    return "Sin comisión de operación · los impuestos dependen de la jurisdicción";
  }
  return describeCommissionProfile(COMMISSION_PRESETS[id], options);
}

/**
 * Detalle de un perfil de comisión CONCRETO (preset o personalizado). A diferencia de
 * `describeCommissionPreset`, aquí los números salen del propio perfil, así que sirve
 * para el preset `custom` que el usuario ha editado.
 */
export function describeCommissionProfile(
  profile: CommissionProfile,
  options?: { currency?: string | null },
): string {
  const currency = options?.currency?.trim() || undefined;
  const parts: string[] = [];
  if (profile.stockCommissionPct > 0) {
    parts.push(`${pctEs(profile.stockCommissionPct)} % comisión`);
  } else {
    parts.push("0 % comisión en acciones");
  }
  if (profile.stockCommissionMin > 0) {
    parts.push(`mín. ${amountEs(profile.stockCommissionMin, currency)}`);
  }
  if (profile.stockCommissionMax != null) {
    parts.push(`máx. ${amountEs(profile.stockCommissionMax, currency)}`);
  }
  if (profile.vatOnCommissionPct > 0) {
    parts.push(`IVA ${pctEs(profile.vatOnCommissionPct)} %`);
  }
  if (profile.fxConversionPct > 0) {
    parts.push(`FX ${pctEs(profile.fxConversionPct)} %`);
  }
  if (profile.custodyAnnualPct != null && profile.custodyAnnualPct > 0) {
    parts.push(`custodia ${pctEs(profile.custodyAnnualPct)} % anual`);
  }
  return parts.join(" · ");
}

/** Tipos que el backend aplicará de verdad en el informe fiscal (para resúmenes). */
export function describeTaxProfile(tax: TaxProfile): string {
  const parts = [
    TAX_JURISDICTION_LABELS[tax.jurisdiction] ?? tax.jurisdiction,
    COST_BASIS_SHORT_LABELS[tax.costBasisMethod] ?? tax.costBasisMethod,
  ];
  if (tax.stampDutyBuyPct > 0)
    parts.push(`transmisiones ${pctEs(tax.stampDutyBuyPct)} %`);
  if (tax.dividendWithholdingPct > 0) {
    parts.push(`retención div. ${pctEs(tax.dividendWithholdingPct)} %`);
  }
  if (tax.capitalGainsTaxPct != null && tax.capitalGainsTaxPct > 0) {
    parts.push(`plusvalías ${pctEs(tax.capitalGainsTaxPct)} %`);
  }
  return parts.join(" · ");
}

/**
 * Cuantiza a 4 decimales con HALF_UP: misma semántica que
 * `Decimal.quantize(Decimal("0.0001"), ROUND_HALF_UP)` del dominio Python
 * (`bolsa_domain.account_settings.calculate_trade_fees`). Sin esta cuantización la
 * vista previa del navegador podía diferir del asiento real en la 4.ª decimal.
 *
 * Todos los importes de comisión son no negativos; el signo se conserva por robustez.
 */
export function quantizeMoney4(value: number): number {
  if (!Number.isFinite(value)) return value;
  const sign = value < 0 ? -1 : 1;
  // `toFixed(6)` neutraliza el error binario (p. ej. 1234.5678 * 1e4 = 12345678.000000002)
  // antes del redondeo, sin mover los medios exactos (.5 ⇒ hacia arriba).
  const scaled = Number((Math.abs(value) * 1e4).toFixed(6));
  return (sign * Math.round(scaled)) / 1e4;
}

/**
 * Calcula comisiones e impuestos de una operación (cliente y servidor).
 *
 * Contrato de paridad con el dominio Python: el IVA se aplica sobre la comisión SIN
 * redondear y el total se suma SIN redondear; solo el resultado final de cada
 * componente se cuantiza a 4 decimales. Redondear los intermedios cambiaría el asiento.
 */
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
    commission: quantizeMoney4(commissionAmount),
    vatOnCommission: quantizeMoney4(vatOnCommission),
    stampDuty: quantizeMoney4(stampDuty),
    fxConversion: quantizeMoney4(fxConversion),
    total: quantizeMoney4(total),
    currency: options?.currency ?? "EUR",
  };
}
