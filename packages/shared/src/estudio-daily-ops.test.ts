import { describe, expect, it } from "vitest";

import { chainReadGaps, describeChainReadGaps } from "./estudio-daily-ops.js";

/**
 * C-1 (auditoría 2.88.179) — la ficha distingue «no hay» de «no se pudo leer».
 *
 * Antes de publicar `readGaps`, un `[]` de propuestas por fallo de lectura se mostraba igual
 * que «el parte no propuso nada»: la afirmación contraria al hueco real.
 */
describe("chainReadGaps", () => {
  it("solo un motivo declara hueco: `null` significa MEDIDA", () => {
    expect(
      chainReadGaps({ readGaps: { dailyProposals: null, diaD: null } }),
    ).toEqual([]);
  });

  it("un servidor anterior a C-1 no envía la clave: no se inventa un hueco", () => {
    expect(chainReadGaps({})).toEqual([]);
    expect(chainReadGaps(null)).toEqual([]);
    expect(chainReadGaps(undefined)).toEqual([]);
  });

  it("devuelve las etapas ilegibles ordenadas por nombre", () => {
    expect(
      chainReadGaps({
        readGaps: {
          diaD: "dia_d_unreadable",
          dailyProposals: "proposals_unreadable",
        },
      }),
    ).toEqual([
      { stage: "dailyProposals", reason: "proposals_unreadable" },
      { stage: "diaD", reason: "dia_d_unreadable" },
    ]);
  });

  it("una cadena vacía o con espacios no es un motivo", () => {
    expect(chainReadGaps({ readGaps: { dailyProposals: "  " } })).toEqual([]);
  });
});

describe("describeChainReadGaps", () => {
  it("sin huecos no produce frase (no se pinta nada)", () => {
    expect(
      describeChainReadGaps({ readGaps: { dailyProposals: null } }),
    ).toBeNull();
    expect(describeChainReadGaps({})).toBeNull();
    expect(describeChainReadGaps(null)).toBeNull();
  });

  it("nombra la etapa en claro y declara que la ausencia no es real", () => {
    const label = describeChainReadGaps({
      readGaps: { dailyProposals: "proposals_unreadable" },
    });
    expect(label).toContain("propuestas diarias del parte");
    expect(label).toContain("falló la lectura");
    expect(label).toContain("no es una ausencia real");
  });

  it("una etapa desconocida y un motivo desconocido se declaran crudos, no se ocultan", () => {
    const label = describeChainReadGaps({
      readGaps: { settlementLink: "settlement_unreadable" },
    });
    expect(label).toContain("settlementLink");
    expect(label).toContain("settlement_unreadable");
  });
});
