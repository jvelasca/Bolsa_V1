/**
 * P4 — tests del read-model «Por qué AUTO no operó» (falsabilidad).
 *
 * Afirman las invariantes del audit: ninguna causa se declara sin dato; el hueco NO es un
 * «No aplica» ni un 0; los motivos de entrada se traducen (nunca se filtran enums crudos); y
 * la traza del motor se filtra por día.
 */

import { describe, expect, it } from "vitest";
import { absentDataLabel } from "@/components/absent-data";
import {
  AUTO_NO_TRADE_CAUSE_ORDER,
  buildAutoNoTradeExplanation,
  cycleBelongsToDay,
  type AutoNoTradeCycleFacts,
  type AutoNoTradeExplanationInput,
  type AutoNoTradeRowV1,
} from "@/features/auto/auto-no-trade-explanation";

const UNMEASURED = absentDataLabel();

function build(input: Partial<AutoNoTradeExplanationInput> = {}) {
  return buildAutoNoTradeExplanation({
    day: null,
    discovery: null,
    engine: null,
    ...input,
  });
}

function rowOf(
  explanation: ReturnType<typeof build>,
  causeId: string,
): AutoNoTradeRowV1 {
  const row = explanation.layers
    .flatMap((layer) => layer.rows)
    .find((item) => item.id === causeId);
  if (!row) throw new Error(`causa no encontrada: ${causeId}`);
  return row;
}

describe("buildAutoNoTradeExplanation — sin lectura todo es hueco (UNKNOWN ≠ 0)", () => {
  const explanation = build();

  it("las seis causas están presentes en orden de cadena", () => {
    expect(explanation.layers.flatMap((l) => l.rows).map((r) => r.id)).toEqual([
      ...AUTO_NO_TRADE_CAUSE_ORDER,
    ]);
  });

  it("ninguna causa se declara; todas quedan «Sin dato todavía»", () => {
    for (const row of explanation.layers.flatMap((l) => l.rows)) {
      expect(row.status).toBe("unknown");
      expect(row.statusLabel).toBe(UNMEASURED);
    }
    expect(explanation.hasDeclaredCause).toBe(false);
  });

  it("ambas capas se declaran no medidas", () => {
    expect(explanation.layers.every((l) => l.measured === false)).toBe(true);
  });
});

describe("capa de descubrimiento — universo y selección", () => {
  it("universo no disponible ⇒ hueco, NO «ocurrió» ni cero", () => {
    const explanation = build({
      discovery: { loaded: true, estudioStatus: "unavailable" },
    });
    const row = rowOf(explanation, "no_opportunity");
    expect(row.status).toBe("unknown");
    expect(row.evidence[0]?.label).toContain("no está disponible");
  });

  it("universo vacío ⇒ «No apareció una oportunidad»", () => {
    const explanation = build({
      discovery: { loaded: true, estudioStatus: "empty" },
    });
    expect(rowOf(explanation, "no_opportunity").status).toBe("occurred");
  });

  it("candidatos descartados ⇒ causa 2 ocurrida con motivo traducido, sin enum crudo", () => {
    const explanation = build({
      discovery: {
        loaded: true,
        estudioStatus: "ok",
        autoDesk: {
          entry: {
            status: "skipped",
            proposed: 2,
            executed: 0,
            skipped: [
              { symbol: "AAA", reasonCode: "ENTRY_RISK_LIMIT" },
              { symbol: "BBB", reasonCode: "ENTRY_RISK_LIMIT" },
            ],
          },
        },
      },
    });
    expect(rowOf(explanation, "no_opportunity").status).toBe("not_applicable");
    const cause2 = rowOf(explanation, "no_selection");
    expect(cause2.status).toBe("occurred");
    const joined = cause2.evidence.map((e) => e.label).join(" | ");
    expect(joined).toContain("Límite de riesgo alcanzado: 2");
    expect(joined).not.toContain("ENTRY_RISK_LIMIT");
  });

  it("ejecutado sin motivo declarado sigue siendo causa 2 ocurrida", () => {
    const explanation = build({
      discovery: {
        loaded: true,
        estudioStatus: "ok",
        autoDesk: {
          entry: { status: "skipped", proposed: 1, executed: 0, skipped: [] },
        },
      },
    });
    expect(rowOf(explanation, "no_selection").status).toBe("occurred");
  });

  it("kill switch activo ⇒ veto declarado", () => {
    const explanation = build({
      discovery: {
        loaded: true,
        estudioStatus: "ok",
        gate: {
          killOn: true,
          vetoed: 0,
          incidentCount: 0,
          incidentsFailed: false,
        },
      },
    });
    expect(rowOf(explanation, "risk_regime_veto").status).toBe("occurred");
  });

  it("lectura de incidentes fallida ⇒ veto en hueco, NO «No aplica»", () => {
    const explanation = build({
      discovery: {
        loaded: true,
        estudioStatus: "ok",
        gate: {
          killOn: false,
          vetoed: 0,
          incidentCount: -1,
          incidentsFailed: true,
        },
      },
    });
    expect(rowOf(explanation, "risk_regime_veto").status).toBe("unknown");
  });

  it("el contador de incidentes -1 no se interpreta como 0 veto", () => {
    const explanation = build({
      discovery: {
        loaded: true,
        estudioStatus: "ok",
        gate: {
          killOn: false,
          vetoed: 0,
          incidentCount: -1,
          incidentsFailed: false,
        },
      },
    });
    expect(rowOf(explanation, "risk_regime_veto").status).toBe(
      "not_applicable",
    );
  });
});

describe("capa del motor — traza por ciclo filtrada por día", () => {
  const makeCycle = (
    id: string,
    day: string,
    steps: Array<{ id: string; state: string }>,
    closed: boolean | null = null,
  ): AutoNoTradeCycleFacts => ({
    id,
    closed,
    closedMeasurement: "COMPLETE",
    resultClosedAt: null,
    steps: steps.map((s) => ({ ...s, at: `${day}T10:00:00Z` })),
  });

  it("orden creada sin ejecución ⇒ causa 5 ocurrida con enlace al ciclo", () => {
    const c = makeCycle("cyc-1", "2026-10-09", [
      { id: "RISK", state: "reached" },
      { id: "ORDER", state: "reached" },
      { id: "FILL", state: "pending" },
    ]);
    const explanation = build({
      day: "2026-10-09",
      engine: { loaded: true, cycles: [c] },
    });
    const row = rowOf(explanation, "order_without_fill");
    expect(row.status).toBe("occurred");
    expect(row.evidence[0]?.ref).toBe("cyc-1");
    expect(rowOf(explanation, "execution_unconfirmed").status).toBe(
      "not_applicable",
    );
  });

  it("decisión tomada sin orden (paso ausente) ⇒ causa 4 ocurrida", () => {
    const c = makeCycle("cyc-2", "2026-10-09", [
      { id: "RISK", state: "reached" },
      { id: "ORDER", state: "absent" },
    ]);
    const explanation = build({
      day: "2026-10-09",
      engine: { loaded: true, cycles: [c] },
    });
    expect(rowOf(explanation, "decision_without_order").status).toBe(
      "occurred",
    );
  });

  it("orden no durable (unknown) ⇒ causa 4 en hueco, no afirmada", () => {
    const c = makeCycle("cyc-3", "2026-10-09", [
      { id: "RISK", state: "reached" },
      { id: "ORDER", state: "unknown" },
    ]);
    const explanation = build({
      day: "2026-10-09",
      engine: { loaded: true, cycles: [c] },
    });
    expect(rowOf(explanation, "decision_without_order").status).toBe("unknown");
  });

  it("ejecución sin cierre confirmado ⇒ causa 6 ocurrida", () => {
    const c = makeCycle(
      "cyc-4",
      "2026-10-09",
      [
        { id: "ORDER", state: "reached" },
        { id: "FILL", state: "reached" },
      ],
      null,
    );
    const explanation = build({
      day: "2026-10-09",
      engine: { loaded: true, cycles: [c] },
    });
    expect(rowOf(explanation, "execution_unconfirmed").status).toBe("occurred");
  });

  it("un ciclo de otro día se excluye ⇒ causas del motor en hueco", () => {
    const c = makeCycle("cyc-5", "2026-10-08", [
      { id: "ORDER", state: "reached" },
      { id: "FILL", state: "pending" },
    ]);
    const explanation = build({
      day: "2026-10-09",
      engine: { loaded: true, cycles: [c] },
    });
    expect(rowOf(explanation, "order_without_fill").status).toBe("unknown");
    expect(rowOf(explanation, "decision_without_order").status).toBe("unknown");
  });
});

describe("cycleBelongsToDay", () => {
  it("reconoce el día por cualquier sello de paso o de cierre", () => {
    expect(
      cycleBelongsToDay(
        {
          id: "c",
          steps: [
            { id: "SIGNAL", state: "reached", at: "2026-10-09T09:00:00Z" },
          ],
        },
        "2026-10-09",
      ),
    ).toBe(true);
    expect(
      cycleBelongsToDay(
        { id: "c", resultClosedAt: "2026-10-09T17:00:00Z" },
        "2026-10-09",
      ),
    ).toBe(true);
    expect(cycleBelongsToDay({ id: "c" }, "2026-10-09")).toBe(false);
  });
});

describe("honestidad de la cabecera", () => {
  it("sin causa declarada explica el hueco, no inventa una causa", () => {
    const explanation = build();
    expect(explanation.headline).toContain("No hay una causa declarada");
    expect(explanation.headline).toContain("Sin dato todavía");
  });

  it("con causa declarada nombra la más temprana", () => {
    const explanation = build({
      discovery: { loaded: true, estudioStatus: "empty" },
    });
    expect(explanation.headline).toContain("No apareció una oportunidad");
  });
});
