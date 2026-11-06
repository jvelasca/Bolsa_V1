import { describe, expect, it } from "vitest";

import type { InstrumentListSummaryDto } from "@bolsa/shared";
import { ESTUDIO_LIST_ID, VIRTUAL_LIST_VISUALIZATION } from "@bolsa/shared";

import {
  groupListsByFamily,
  listHubFamily,
  listTypeLabel,
} from "@/lib/list-hub-families";

function list(
  partial: Partial<InstrumentListSummaryDto> & { id: string; name: string },
): InstrumentListSummaryDto {
  return {
    itemCount: 0,
    source: "user",
    kind: "custom",
    ...partial,
  } as InstrumentListSummaryDto;
}

describe("list-hub-families", () => {
  it("clasifica Estudio como Sistema (universo de supervisión)", () => {
    const estudio = list({
      id: ESTUDIO_LIST_ID,
      name: "Estudio",
      kind: "supervision_universe",
      itemCount: 80,
    });
    expect(listHubFamily(estudio)).toBe("sistema");
    expect(listTypeLabel(estudio)).toBe("sistema");
  });

  it("clasifica Estudio por id aunque el kind venga sin normalizar", () => {
    const estudio = list({ id: ESTUDIO_LIST_ID, name: "Estudio" });
    expect(listHubFamily(estudio)).toBe("sistema");
  });

  it("clasifica las listas virtuales como Sistema", () => {
    const visualizados = list({
      id: VIRTUAL_LIST_VISUALIZATION,
      name: "Visualizados",
    });
    expect(listHubFamily(visualizados)).toBe("sistema");
    expect(listTypeLabel(visualizados)).toBe("sistema");
  });

  it("clasifica índices de catálogo y copias", () => {
    const indice = list({
      id: "idx-ibex",
      name: "IBEX 35",
      source: "catalog",
      kind: "linked_universe",
    });
    expect(listHubFamily(indice)).toBe("indices");
    expect(listTypeLabel(indice)).toBe("índice");

    const copia = list({ id: "copia-1", name: "Copia", kind: "snapshot" });
    expect(listHubFamily(copia)).toBe("personales");
    expect(listTypeLabel(copia)).toBe("copia");
  });

  it("clasifica las listas propias como Personales / personal", () => {
    const propia = list({ id: "mia", name: "Mi lista" });
    expect(listHubFamily(propia)).toBe("personales");
    expect(listTypeLabel(propia)).toBe("personal");
  });

  it("agrupa en orden Sistema → Índices → Personales sin familias vacías", () => {
    const groups = groupListsByFamily([
      list({ id: "mia", name: "Mi lista" }),
      list({
        id: ESTUDIO_LIST_ID,
        name: "Estudio",
        kind: "supervision_universe",
      }),
      list({ id: "idx", name: "Índice", source: "catalog" }),
    ]);
    expect(groups.map((group) => group.id)).toEqual([
      "sistema",
      "indices",
      "personales",
    ]);
    expect(groups[0]?.label).toBe("Sistema");
    expect(groups[0]?.lists.map((entry) => entry.id)).toEqual([
      ESTUDIO_LIST_ID,
    ]);
  });
});
