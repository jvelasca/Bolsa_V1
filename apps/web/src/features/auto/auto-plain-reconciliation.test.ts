/**
 * Frente C — conciliación en lenguaje llano (`buildPlainReconciliation`).
 *
 * Certifica el contrato `UNKNOWN ≠ 0`: sin lectura el rótulo es «Sin dato todavía» (nunca
 * «Cuadra»), un estado ajeno es hueco (no se colapsa), y `drift`/`lag`/`blocked` producen el
 * veredicto plano correspondiente.
 */
import { describe, expect, it } from "vitest";
import { absentDataLabel } from "@/components/absent-data";
import { buildPlainReconciliation } from "@/features/auto/auto-plain-reconciliation";

const UNKNOWN = absentDataLabel();

describe("buildPlainReconciliation", () => {
  it("sin lectura declara «Sin dato todavía», nunca «Cuadra»", () => {
    const plain = buildPlainReconciliation({});
    expect(plain.available).toBe(false);
    expect(plain.tone).toBe("unknown");
    expect(plain.label).toBe(UNKNOWN);
  });

  it("cargando o con error es hueco, aunque haya un estado previo", () => {
    expect(
      buildPlainReconciliation({
        portfolioStatus: "ok",
        portfolioLoading: true,
      }).tone,
    ).toBe("unknown");
    expect(
      buildPlainReconciliation({ lifecycleStatus: "ok", lifecycleError: true })
        .tone,
    ).toBe("unknown");
  });

  it("un estado ajeno no se colapsa a «Cuadra»", () => {
    const plain = buildPlainReconciliation({ portfolioStatus: "weird" });
    expect(plain.tone).toBe("unknown");
    expect(plain.label).toBe(UNKNOWN);
  });

  it("ambas lecturas ok ⇒ Cuadra", () => {
    const plain = buildPlainReconciliation({
      portfolioStatus: "ok",
      lifecycleStatus: "ok",
      driftCount: 0,
      lagCount: 0,
      blockedCount: 0,
    });
    expect(plain.available).toBe(true);
    expect(plain.tone).toBe("ok");
    expect(plain.label).toBe("Cuadra");
  });

  it("drift/lag ⇒ Revisar", () => {
    expect(buildPlainReconciliation({ portfolioStatus: "drift" }).tone).toBe(
      "attention",
    );
    expect(
      buildPlainReconciliation({ portfolioStatus: "ok", driftCount: 3 }).tone,
    ).toBe("attention");
    expect(
      buildPlainReconciliation({
        portfolioStatus: "ok",
        lifecycleStatus: "lag",
      }).tone,
    ).toBe("attention");
  });

  it("blocked ⇒ Bloqueado", () => {
    expect(buildPlainReconciliation({ portfolioStatus: "blocked" }).tone).toBe(
      "blocked",
    );
    expect(
      buildPlainReconciliation({
        portfolioStatus: "ok",
        lifecycleStatus: "ok",
        blockedCount: 1,
      }).tone,
    ).toBe("blocked");
  });
});
