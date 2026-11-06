import { describe, expect, it } from "vitest";

import {
  DEFAULT_LIST_ROW_ACTIONS_WIDTH,
  MIN_LIST_ROW_ACTIONS_WIDTH,
} from "./chart-defaults.js";
import {
  ALL_LIST_HUB_COLUMNS,
  DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH,
  MIN_LIST_HUB_ROW_ACTIONS_WIDTH,
  buildDefaultListHubColumnLayout,
  normalizeListHubColumnLayout,
} from "./list-hub-columns.js";

/** 3 iconos de 24 px + separación/padding + borde = 75 px (medido en la UI). */
const ROW_ACTIONS_CONTENT_PX = 75;
/** Hasta 4 iconos de 24 px en el hub = 96 px. */
const HUB_ROW_ACTIONS_CONTENT_PX = 96;

describe("anchos de la zona de acciones de fila", () => {
  it("el defecto de Valores cabe 3 iconos sin recortar", () => {
    expect(DEFAULT_LIST_ROW_ACTIONS_WIDTH).toBeGreaterThanOrEqual(
      ROW_ACTIONS_CONTENT_PX,
    );
    expect(MIN_LIST_ROW_ACTIONS_WIDTH).toBeGreaterThanOrEqual(
      ROW_ACTIONS_CONTENT_PX,
    );
    expect(MIN_LIST_ROW_ACTIONS_WIDTH).toBeLessThanOrEqual(
      DEFAULT_LIST_ROW_ACTIONS_WIDTH,
    );
  });

  it("el defecto del hub cabe 4 iconos sin recortar", () => {
    expect(DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH).toBeGreaterThanOrEqual(
      HUB_ROW_ACTIONS_CONTENT_PX,
    );
    expect(MIN_LIST_HUB_ROW_ACTIONS_WIDTH).toBeGreaterThanOrEqual(
      ROW_ACTIONS_CONTENT_PX,
    );
    expect(MIN_LIST_HUB_ROW_ACTIONS_WIDTH).toBeLessThanOrEqual(
      DEFAULT_LIST_HUB_ROW_ACTIONS_WIDTH,
    );
  });
});

describe("normalizeListHubColumnLayout", () => {
  it("preserva el orden guardado por el usuario", () => {
    const stored = buildDefaultListHubColumnLayout();
    const reordered = [stored[2]!, stored[0]!, ...stored.slice(3), stored[1]!];

    const normalized = normalizeListHubColumnLayout(reordered);

    expect(normalized.map((column) => column.id)).toEqual(
      reordered.map((column) => column.id),
    );
  });

  it("añade al final las columnas que falten en el layout guardado", () => {
    const stored = buildDefaultListHubColumnLayout();
    const partial = stored.filter((column) => column.id !== "count");

    const normalized = normalizeListHubColumnLayout(partial);

    expect(normalized).toHaveLength(ALL_LIST_HUB_COLUMNS.length);
    expect(normalized.at(-1)?.id).toBe("count");
  });

  it("completa el layout por defecto cuando no hay nada guardado", () => {
    expect(normalizeListHubColumnLayout(undefined)).toEqual(
      buildDefaultListHubColumnLayout(),
    );
    expect(normalizeListHubColumnLayout([])).toEqual(
      buildDefaultListHubColumnLayout(),
    );
  });
});
