import { describe, expect, it } from "vitest";

import type { ListColumnLayoutItem } from "@bolsa/shared";
import { MIN_LIST_COLUMN_WIDTH } from "@bolsa/shared";

import {
  DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX,
  LIST_ROW_EXPAND_WIDTH_PX,
  LIST_ROW_HORIZONTAL_PADDING_PX,
  LIST_ROW_SELECT_WIDTH_PX,
  buildListRowDataGridTemplate,
  fitColumnWidthsToAvailable,
  listRowMinWidthPx,
} from "@/lib/list-column-layout";

function col(
  id: ListColumnLayoutItem["id"],
  width: number,
  visible = true,
): ListColumnLayoutItem {
  return { id, width, visible };
}

describe("list-column-layout · grid de fila", () => {
  it("usa pistas fijas para las columnas no flexibles (no colapsan a 0)", () => {
    const template = buildListRowDataGridTemplate([
      col("symbol", 64),
      col("lastClose", 80),
      col("name", 120),
    ]);
    // `name` es la flexible; el resto conserva su ancho exacto.
    expect(template).toBe("64px 80px minmax(120px, 1fr)");
  });

  it("cae a minmax(0, 1fr) sin columnas visibles", () => {
    expect(buildListRowDataGridTemplate([])).toBe("minmax(0, 1fr)");
  });

  it("suma gutter + columnas + acciones + padding en el ancho mínimo", () => {
    const visible = [col("symbol", 64), col("lastClose", 80)];
    const expected =
      LIST_ROW_EXPAND_WIDTH_PX +
      64 +
      80 +
      DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX +
      LIST_ROW_HORIZONTAL_PADDING_PX;
    expect(listRowMinWidthPx(visible)).toBe(expected);

    const withSelect = listRowMinWidthPx(
      visible,
      DEFAULT_LIST_ROW_ACTIONS_WIDTH_PX,
      true,
    );
    expect(withSelect - expected).toBe(LIST_ROW_SELECT_WIDTH_PX);
  });

  it("nunca baja del mínimo por columna al ajustar al ancho", () => {
    const visible = [
      col("symbol", 120),
      col("lastClose", 120),
      col("changePct", 120),
      col("name", 200),
    ];
    const fitted = fitColumnWidthsToAvailable(visible, 400);
    const total = fitted.reduce((sum, column) => sum + column.width, 0);
    expect(total).toBeLessThanOrEqual(400);
    for (const column of fitted) {
      expect(column.width).toBeGreaterThanOrEqual(MIN_LIST_COLUMN_WIDTH);
    }
  });

  it("no toca los anchos si ya caben", () => {
    const visible = [col("symbol", 64), col("lastClose", 80)];
    expect(fitColumnWidthsToAvailable(visible, 400)).toBe(visible);
  });

  it("devuelve mínimos cuando no cabe ni con mínimos", () => {
    const visible = [col("symbol", 64), col("lastClose", 80), col("name", 120)];
    const fitted = fitColumnWidthsToAvailable(visible, 60);
    expect(
      fitted.every((column) => column.width === MIN_LIST_COLUMN_WIDTH),
    ).toBe(true);
  });
});
