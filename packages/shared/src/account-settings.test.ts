import { describe, expect, it } from "vitest";
import {
  COMMISSION_PRESETS,
  TAX_PRESETS,
  calculateTradeFees,
  defaultAccountSettings,
  describeCommissionPreset,
  describeTaxProfile,
  quantizeMoney4,
  resolveCommissionProfile,
} from "@bolsa/shared";

// Paridad de catálogo TS <-> dominio. El paquete Python
// (`bolsa_domain.account_settings`) es la fuente de verdad para dinero: aquí se fija
// que el catálogo del navegador aplique EXACTAMENTE los mismos números, porque el
// wizard y el panel envían estos valores al servidor tal cual.
describe("TAX_PRESETS parity with domain catalog", () => {
  it("keeps the ES profile aligned with the domain (incl. 19% capital gains)", () => {
    // COM-D1: el dominio define capital_gains_tax_pct=19.0 para ES; el preset TS
    // enviaba null y dejaba la estimación fiscal siempre vacía.
    expect(TAX_PRESETS.ES).toEqual({
      jurisdiction: "ES",
      costBasisMethod: "fifo",
      stampDutyBuyPct: 0.2,
      dividendWithholdingPct: 19,
      capitalGainsTaxPct: 19,
      fiscalYearStartMonth: 1,
    });
  });

  it("keeps US dividend withholding aligned with the domain default (30)", () => {
    expect(TAX_PRESETS.US.dividendWithholdingPct).toBe(30);
  });

  it("keeps the remaining jurisdictions in sync (ES=19, EU_OTHER=15, CUSTOM=0)", () => {
    expect(TAX_PRESETS.EU_OTHER.dividendWithholdingPct).toBe(15);
    expect(TAX_PRESETS.CUSTOM.dividendWithholdingPct).toBe(0);
  });

  it("does not project capital gains tax where the domain does not", () => {
    expect(TAX_PRESETS.EU_OTHER.capitalGainsTaxPct).toBeNull();
    expect(TAX_PRESETS.US.capitalGainsTaxPct).toBeNull();
    expect(TAX_PRESETS.CUSTOM.capitalGainsTaxPct).toBeNull();
  });

  it("defaults a new account to the ES preset with capital gains projection", () => {
    expect(defaultAccountSettings().tax).toEqual(TAX_PRESETS.ES);
  });
});

describe("COMMISSION_PRESETS parity with domain catalog", () => {
  it("mirrors the standard_es numbers used by calculate_trade_fees", () => {
    expect(COMMISSION_PRESETS.standard_es).toEqual({
      presetId: "standard_es",
      label: "Broker estándar ES",
      stockCommissionPct: 0.1,
      stockCommissionMin: 1,
      stockCommissionMax: 29,
      vatOnCommissionPct: 21,
      fxConversionPct: 0.5,
      custodyAnnualPct: 0.2,
    });
  });

  it("mirrors xtb_zero_stock, ibkr_tiered and none", () => {
    expect(COMMISSION_PRESETS.xtb_zero_stock.stockCommissionPct).toBe(0);
    expect(COMMISSION_PRESETS.xtb_zero_stock.fxConversionPct).toBe(0.5);
    expect(COMMISSION_PRESETS.ibkr_tiered.stockCommissionMin).toBe(1.25);
    expect(COMMISSION_PRESETS.ibkr_tiered.fxConversionPct).toBe(0.002);
    expect(COMMISSION_PRESETS.none.vatOnCommissionPct).toBe(0);
    expect(COMMISSION_PRESETS.none.stockCommissionMax).toBeNull();
  });
});

describe("quantizeMoney4 (ROUND_HALF_UP parity with Decimal)", () => {
  it("rounds half up and keeps four decimals", () => {
    expect(quantizeMoney4(1.2345678)).toBe(1.2346);
    expect(quantizeMoney4(0.259259238)).toBe(0.2593);
    expect(quantizeMoney4(2.4691356)).toBe(2.4691);
    expect(quantizeMoney4(0.00005)).toBe(0.0001);
  });

  it("does not move values already inside the quantum", () => {
    expect(quantizeMoney4(2.5)).toBe(2.5);
    expect(quantizeMoney4(0)).toBe(0);
    expect(quantizeMoney4(29)).toBe(29);
  });
});

describe("calculateTradeFees parity with the domain", () => {
  const es = defaultAccountSettings("standard_es", "ES");

  it("matches the domain breakdown for a 1234.5678 buy (no intermediate rounding)", () => {
    const fees = calculateTradeFees(1234.5678, "buy", es, { currency: "EUR" });
    expect(fees.commission).toBe(1.2346);
    expect(fees.vatOnCommission).toBe(0.2593);
    expect(fees.stampDuty).toBe(2.4691);
    expect(fees.fxConversion).toBe(0);
    expect(fees.total).toBe(3.963);
    expect(fees.currency).toBe("EUR");
  });

  it("applies the per-operation minimum", () => {
    const fees = calculateTradeFees(100, "buy", es);
    expect(fees.commission).toBe(1);
    expect(fees.vatOnCommission).toBe(0.21);
    expect(fees.stampDuty).toBe(0.2);
    expect(fees.total).toBe(1.41);
  });

  it("caps the commission at the per-operation maximum", () => {
    const fees = calculateTradeFees(100_000, "buy", es);
    expect(fees.commission).toBe(29);
    expect(fees.vatOnCommission).toBe(6.09);
    expect(fees.stampDuty).toBe(200);
    expect(fees.total).toBe(235.09);
  });

  it("charges stamp duty only on buys", () => {
    const buy = calculateTradeFees(5000, "buy", es);
    const sell = calculateTradeFees(5000, "sell", es);
    expect(buy.stampDuty).toBe(10);
    expect(sell.stampDuty).toBe(0);
    expect(sell.total).toBe(6.05);
  });

  it("only charges FX when the conversion is explicit", () => {
    expect(calculateTradeFees(10_000, "buy", es).fxConversion).toBe(0);
    expect(
      calculateTradeFees(10_000, "buy", es, { isFxConversion: true })
        .fxConversion,
    ).toBe(50);
  });

  it("charges nothing but the tax-driven stamp duty with the none preset", () => {
    // COM-D12: el preset «none» apaga comisión/IVA/FX, pero el impuesto de
    // transmisiones pertenece al perfil fiscal (ES = 0,2 %) y el backend lo sigue
    // cobrando. La UI no puede prometer «sin impuestos».
    const fees = calculateTradeFees(
      5000,
      "buy",
      defaultAccountSettings("none", "ES"),
    );
    expect(fees).toEqual({
      commission: 0,
      vatOnCommission: 0,
      stampDuty: 10,
      fxConversion: 0,
      total: 10,
      currency: "EUR",
    });
  });

  it("keeps custom overrides working and quantized", () => {
    const custom = resolveCommissionProfile("custom", {
      stockCommissionPct: 0.33,
      stockCommissionMin: 0,
      vatOnCommissionPct: 21,
    });
    const fees = calculateTradeFees(1000, "buy", {
      ...es,
      commission: custom,
      tax: { ...es.tax, stampDutyBuyPct: 0 },
    });
    expect(fees.commission).toBe(3.3);
    expect(fees.vatOnCommission).toBe(0.693);
    expect(fees.total).toBe(3.993);
  });
});

describe("presentation catalog (single source for panel, wizard and account detail)", () => {
  it("derives the ES hint from the preset numbers", () => {
    expect(describeCommissionPreset("standard_es", { currency: "EUR" })).toBe(
      "0,1 % comisión · mín. 1,00 EUR · máx. 29,00 EUR · IVA 21 % · FX 0,5 % · custodia 0,2 % anual",
    );
  });

  it("describes the zero-commission and no-fees presets without inventing rates", () => {
    expect(describeCommissionPreset("xtb_zero_stock")).toBe(
      "0 % comisión en acciones · FX 0,5 %",
    );
    expect(describeCommissionPreset("none")).toBe(
      "Sin comisión de operación · los impuestos dependen de la jurisdicción",
    );
    expect(describeCommissionPreset("custom")).toBe(
      "Parámetros manuales de comisión, IVA, FX y custodia",
    );
  });

  it("summarizes the tax profile that the backend will actually apply", () => {
    expect(describeTaxProfile(TAX_PRESETS.ES)).toBe(
      "España (ES) · FIFO · transmisiones 0,2 % · retención div. 19 % · plusvalías 19 %",
    );
    expect(describeTaxProfile(TAX_PRESETS.US)).toBe(
      "Estados Unidos · FIFO · retención div. 30 %",
    );
  });
});
