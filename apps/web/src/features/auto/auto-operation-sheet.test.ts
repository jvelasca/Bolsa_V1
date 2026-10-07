/**
 * AUTO UI REFACTOR 4.0 (P2) — ficha universal de operación (contrato del read-model).
 */

import { describe, expect, it } from "vitest";
import type { AutoBasicCycle } from "@/features/auto/auto-basic-home";
import { buildAutoOperationSheet } from "@/features/auto/auto-operation-sheet";

const FILLED: AutoBasicCycle = {
  cycleId: "cyc-1",
  instrumentId: "AAPL",
  steps: [
    { id: "SIGNAL", state: "reached" },
    {
      id: "ORDER",
      state: "reached",
      facts: [
        {
          key: "entryOrder",
          value: { requestedQty: 10, appliedQty: 10 },
          measurement: "COMPLETE",
        },
        { key: "entryPrice", value: 190.5, measurement: "COMPLETE" },
      ],
    },
    {
      id: "FILL",
      state: "reached",
      measurement: "COMPLETE",
      facts: [{ key: "price", value: 190.42, measurement: "COMPLETE" }],
    },
  ],
};

describe("buildAutoOperationSheet", () => {
  it("siempre presenta los seis bloques en orden canónico", () => {
    const sheet = buildAutoOperationSheet(FILLED);
    expect(sheet.blocks.map((b) => b.id)).toEqual([
      "decided",
      "did",
      "changed",
      "price",
      "money",
      "status",
    ]);
  });

  it("copia el precio aplicado del fill y no salta peldaños", () => {
    const sheet = buildAutoOperationSheet(FILLED);
    expect(sheet.blocks.find((b) => b.id === "price")?.value).toBe("190.42");
    expect(sheet.blocks.find((b) => b.id === "price")?.detail).toBe(
      "Precio aplicado",
    );
    // La decisión durable y la materialización siguen siendo huecos declarados.
    expect(sheet.blocks.find((b) => b.id === "decided")?.value).toBe(
      "Sin dato todavía",
    );
    expect(sheet.blocks.find((b) => b.id === "changed")?.value).toBe(
      "Sin dato todavía",
    );
  });

  it("el precio cae a la orden si no hay fill", () => {
    const sheet = buildAutoOperationSheet({
      cycleId: "cyc-2",
      instrumentId: "MSFT",
      steps: [
        {
          id: "ORDER",
          state: "reached",
          facts: [{ key: "entryPrice", value: 410.1, measurement: "COMPLETE" }],
        },
      ],
    });
    expect(sheet.blocks.find((b) => b.id === "price")?.detail).toBe(
      "Precio de la orden",
    );
    expect(sheet.blocks.find((b) => b.id === "price")?.value).toBe("410.10");
  });

  it("no afirma cifras sin medición COMPLETE (UNKNOWN ≠ 0)", () => {
    const sheet = buildAutoOperationSheet({
      cycleId: "cyc-3",
      instrumentId: "AAPL",
      steps: [
        {
          id: "ORDER",
          state: "reached",
          facts: [{ key: "entryPrice", value: 190.5, measurement: "UNKNOWN" }],
        },
      ],
    });
    expect(sheet.blocks.find((b) => b.id === "price")?.value).toBe(
      "Sin dato todavía",
    );
  });

  it("no filtra vocabulario prohibido de primer nivel", () => {
    const flat = buildAutoOperationSheet(FILLED)
      .blocks.map((b) => `${b.label} ${b.value} ${b.detail ?? ""}`)
      .join(" \n ");
    for (const forbidden of [
      "T1 ejecutado",
      "Orden enviada",
      "pendiente de ack",
      "CYCLE_CLOSED",
      "TOP_N",
      "PAPER_D_EXECUTE",
    ]) {
      expect(flat).not.toContain(forbidden);
    }
  });
});
