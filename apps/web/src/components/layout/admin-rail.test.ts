import { describe, expect, it } from "vitest";
import { ESTUDIO_LIST_ID } from "@bolsa/shared";
import { DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID } from "@/features/mesa/mesa-candidates-panel";

/**
 * V1.21 — AdminRail vs ⚙ (contrato UX).
 * El menú de configuración ya no lista Overview/Cuentas/Fiscal/Consola;
 * esos viven en AdminRail. Este test ancla el universo diario + el export del rail.
 */
describe("v121 admin rail / config separation", () => {
  it("daily opportunity universe remains Estudio", () => {
    expect(DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID).toBe(ESTUDIO_LIST_ID);
  });

  it("AdminRail module exports AdminRail", async () => {
    const mod = await import("@/components/layout/admin-rail");
    expect(typeof mod.AdminRail).toBe("function");
  });
});
