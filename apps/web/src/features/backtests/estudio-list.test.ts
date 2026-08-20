/**
 * Tests — lista API canónica «Estudio» (ADR-024).
 */

import { describe, expect, it } from "vitest";
import {
  ESTUDIO_LIST_ID,
  ESTUDIO_LIST_NAME,
  isEstudioListId,
  isEstudioListName,
  isEstudioPersonalListName,
  resolveEstudioListId,
} from "@bolsa/shared";

describe("Estudio list helpers (ADR-024)", () => {
  it("matches canonical id and name", () => {
    expect(isEstudioListId(ESTUDIO_LIST_ID)).toBe(true);
    expect(isEstudioListId("__builtin:visualization__")).toBe(false);
    expect(isEstudioListName(ESTUDIO_LIST_NAME)).toBe(true);
    expect(isEstudioListName("  ESTUDIO ")).toBe(true);
    expect(isEstudioPersonalListName("Estudio personal")).toBe(true);
  });

  it("resolves canonical id first, then name, then legacy personal", () => {
    expect(
      resolveEstudioListId([
        { id: "ibex35", name: "IBEX 35" },
        { id: ESTUDIO_LIST_ID, name: ESTUDIO_LIST_NAME },
        { id: "est-1", name: "Estudio personal" },
      ]),
    ).toBe(ESTUDIO_LIST_ID);

    expect(
      resolveEstudioListId([
        { id: "x", name: "Estudio" },
        { id: "est-1", name: "Estudio personal" },
      ]),
    ).toBe("x");

    expect(
      resolveEstudioListId([
        { id: "ibex35", name: "IBEX 35" },
        { id: "est-1", name: "Estudio personal" },
      ]),
    ).toBe("est-1");

    expect(
      resolveEstudioListId([{ id: "ibex35", name: "IBEX 35" }]),
    ).toBeNull();
  });
});
