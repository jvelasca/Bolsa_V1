import { describe, expect, it } from "vitest";
import { TAX_PRESETS } from "@bolsa/shared";

// Paridad de catálogo de impuestos TS <-> domain: el dominio (paquete Python,
// bolsa_domain.account_settings.TAX_PRESETS) es la fuente de verdad para dinero.
// El preset US debe coincidir con el default canónico del dominio (30%).
describe("TAX_PRESETS parity with domain catalog", () => {
  it("keeps US dividend withholding aligned with the domain default (30)", () => {
    expect(TAX_PRESETS.US.dividendWithholdingPct).toBe(30);
  });

  it("keeps the remaining jurisdictions in sync (ES=19, EU_OTHER=15, CUSTOM=0)", () => {
    expect(TAX_PRESETS.ES.dividendWithholdingPct).toBe(19);
    expect(TAX_PRESETS.EU_OTHER.dividendWithholdingPct).toBe(15);
    expect(TAX_PRESETS.CUSTOM.dividendWithholdingPct).toBe(0);
  });
});
