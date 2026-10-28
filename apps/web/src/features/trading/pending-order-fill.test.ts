/**
 * P1-02 / I-07 — tabla de desenlaces del fill de una orden pendiente.
 *
 * El invariante que se fija: **ningún desenlace distinto de `executed` con
 * `transactionId` puede producir el texto «ejecutada», borrar la orden ni
 * liberar el vínculo de mandato.**
 */
import { describe, expect, it } from "vitest";
import { resolvePendingFill } from "@/features/trading/pending-order-fill";

const base = {
  side: "buy" as const,
  symbol: "SAN",
  priceLabel: "4,25 €",
  reason: null,
  transactionId: null,
};

describe("resolvePendingFill", () => {
  it("executed con transacción es la única ejecución", () => {
    const v = resolvePendingFill({
      ...base,
      status: "executed",
      transactionId: "tx-1",
    });
    expect(v.kind).toBe("executed");
    expect(v.executed).toBe(true);
    expect(v.removesOrder).toBe(true);
    expect(v.copy).toContain("ejecutada");
    expect(v.transactionId).toBe("tx-1");
  });

  it("executed sin transacción degrada a unknown (no se da por bueno)", () => {
    const v = resolvePendingFill({ ...base, status: "executed" });
    expect(v.kind).toBe("unknown");
    expect(v.executed).toBe(false);
    expect(v.copy).not.toContain("ejecutada");
  });

  it("expired cancela y retira la orden", () => {
    const v = resolvePendingFill({ ...base, status: "expired" });
    expect(v.kind).toBe("expired");
    expect(v.removesOrder).toBe(true);
    expect(v.copy).toContain("cancelada");
    expect(v.copy).not.toContain("ejecutada");
  });

  it("rejected_by_gate no ejecuta ni reintenta", () => {
    const v = resolvePendingFill({
      ...base,
      status: "rejected_by_gate",
      reason: "risk_veto",
    });
    expect(v.kind).toBe("rejected");
    expect(v.executed).toBe(false);
    expect(v.removesOrder).toBe(false);
    expect(v.retryable).toBe(false);
    expect(v.copy).toContain("no ejecutada");
    expect(v.copy).toContain("veto de riesgo");
    expect(v.copy).not.toContain("ejecutada @");
  });

  it("skipped (live_not_wired) no se anuncia como ejecutada", () => {
    const v = resolvePendingFill({
      ...base,
      status: "skipped",
      reason: "live_not_wired",
    });
    expect(v.kind).toBe("skipped");
    expect(v.executed).toBe(false);
    expect(v.removesOrder).toBe(false);
    expect(v.copy).toContain("no ejecutada");
    expect(v.copy).not.toContain("ejecutada @");
    expect(v.copy).toContain("live");
  });

  it("unknown no se anuncia como ejecutada y no se reintenta en bucle", () => {
    const v = resolvePendingFill({
      ...base,
      status: "unknown",
      reason: "live_submitted_no_fill",
    });
    expect(v.kind).toBe("unknown");
    expect(v.executed).toBe(false);
    expect(v.removesOrder).toBe(false);
    expect(v.retryable).toBe(false);
    expect(v.copy).toContain("sin confirmar");
    expect(v.copy).not.toMatch(/ejecutada/);
  });

  it("submitted y estados fuera del vocabulario caen en unknown", () => {
    for (const status of ["submitted", "partially_filled", "", "EXECUTED"]) {
      const v = resolvePendingFill({ ...base, status });
      expect(v.kind).toBe("unknown");
      expect(v.executed).toBe(false);
      expect(v.copy).not.toMatch(/ejecutada/);
    }
  });

  it("un motivo desconocido se muestra crudo, no se inventa una causa", () => {
    const v = resolvePendingFill({
      ...base,
      status: "skipped",
      reason: "nuevo_motivo",
    });
    expect(v.copy).toContain("nuevo_motivo");
  });
});
