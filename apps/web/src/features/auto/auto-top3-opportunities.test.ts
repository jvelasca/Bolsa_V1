/**
 * AUTO UI REFACTOR 4.0 (P3) — TOP 3 OPORTUNIDADES (contrato del read-model).
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_TOP3_DEGRADED_LABEL,
  AUTO_TOP3_EMPTY_LABEL,
  AUTO_TOP3_NO_DATA_LABEL,
  AUTO_TOP3_PROPOSAL_LABEL,
  AUTO_TOP3_TITLE,
  buildAutoTop3View,
  formatOpportunityScore,
  opportunityStrengthLabel,
} from "@/features/auto/auto-top3-opportunities";

const DTO = {
  runId: "top3-default-2026-10-07T09",
  items: [
    {
      rank: 1,
      assetId: "MSFT",
      score: 0.87,
      regime: "trend",
      reasons: [],
      createdAt: "2026-10-07T09:00:00Z",
    },
    {
      rank: 2,
      assetId: "ITX",
      score: 0.74,
      reasons: ["scoring_historico_sin_campeon"],
      createdAt: "2026-10-07T09:00:00Z",
    },
  ],
};

describe("auto-top3-opportunities", () => {
  it("el título es «TOP 3 OPORTUNIDADES», nunca «mejores acciones»", () => {
    expect(AUTO_TOP3_TITLE).toBe("TOP 3 OPORTUNIDADES");
    expect(AUTO_TOP3_TITLE.toLowerCase()).not.toContain("mejores");
  });

  it("presenta el score 0..1 como NN/100", () => {
    expect(formatOpportunityScore(0.87)).toBe("87/100");
    expect(formatOpportunityScore(0.745)).toBe("75/100");
    expect(formatOpportunityScore(null)).toBe(AUTO_TOP3_NO_DATA_LABEL);
  });

  it("etiqueta la fuerza de la oportunidad", () => {
    expect(opportunityStrengthLabel(0.9).label).toBe("Oportunidad fuerte");
    expect(opportunityStrengthLabel(0.6).label).toBe("Oportunidad moderada");
    expect(opportunityStrengthLabel(0.2).label).toBe("Oportunidad débil");
  });

  it("traduce el motivo degradado a lenguaje visible y lo expone", () => {
    const view = buildAutoTop3View(DTO);
    const degraded = view.slots.find((s) => s.assetId === "ITX");
    expect(degraded?.reasonLabel).toBe(AUTO_TOP3_DEGRADED_LABEL);
    const strong = view.slots.find((s) => s.assetId === "MSFT");
    expect(strong?.reasonLabel).toBeNull();
  });

  it("todo slot sin hecho posterior se queda «propuesta» (ranking ≠ compra)", () => {
    const view = buildAutoTop3View(DTO);
    expect(
      view.slots.every((s) => s.stateLabel === AUTO_TOP3_PROPOSAL_LABEL),
    ).toBe(true);
    expect(view.rankNote).toContain("Ranking ≠ decisión");
  });

  it("vacío ≠ hueco: sin foto se declara «Sin TOP3 todavía»", () => {
    const empty = buildAutoTop3View({ runId: "", items: [] });
    expect(empty.isEmpty).toBe(true);
    expect(empty.emptyLabel).toBe(AUTO_TOP3_EMPTY_LABEL);
    expect(empty.emptyLabel).not.toBe(AUTO_TOP3_NO_DATA_LABEL);
    expect(buildAutoTop3View(null).isEmpty).toBe(true);
  });

  it("un activo repetido en el espejo durable se pinta una sola vez (mejor rank)", () => {
    // El espejo `top3_opportunities` no tiene clave natural única por `(runId, activo)`: un run
    // reescrito puede traer el mismo activo dos veces. La UI no debe pintarlo repetido.
    const view = buildAutoTop3View({
      runId: "r",
      items: [
        { ...DTO.items[0]!, rank: 1, assetId: "MSFT" },
        { ...DTO.items[0]!, rank: 2, assetId: "MSFT" },
        { ...DTO.items[1]!, rank: 3, assetId: "ITX" },
      ],
    });
    expect(view.slots.map((s) => s.assetId)).toEqual(["MSFT", "ITX"]);
    expect(view.slots.filter((s) => s.assetId === "MSFT")).toHaveLength(1);
    expect(view.slots.find((s) => s.assetId === "MSFT")?.rank).toBe(1);
  });

  it("ordena por rank y no expone vocabulario de primer nivel prohibido", () => {
    const view = buildAutoTop3View({
      runId: "r",
      items: [
        { ...DTO.items[1]!, rank: 3 },
        { ...DTO.items[0]!, rank: 1 },
      ],
    });
    expect(view.slots.map((s) => s.rank)).toEqual([1, 3]);
    const flat = JSON.stringify(view);
    expect(flat).not.toContain("TOP_N");
    expect(flat).not.toContain("scoring_historico_sin_campeon");
  });
});
