import { describe, expect, it } from "vitest";

import { CATALOG_IBEX_LIST_ID } from "@bolsa/shared";

import { reconcileCarouselListIds } from "@/lib/list-sync";

const apiLists = [
  {
    id: CATALOG_IBEX_LIST_ID,
    name: "IBEX 35",
    source: "catalog",
    itemCount: 35,
  },

  { id: "custom-1", name: "Mis valores", source: "custom", itemCount: 3 },
];

describe("reconcileCarouselListIds", () => {
  it("does not prune when api lists are not loaded yet", () => {
    expect(reconcileCarouselListIds(["stale-id"], ["IBEX 35"], [])).toEqual([
      "stale-id",
    ]);
  });

  it("remaps pinned lists by name after id change", () => {
    expect(
      reconcileCarouselListIds(["old-ibex-uuid"], ["IBEX 35"], apiLists),
    ).toEqual([CATALOG_IBEX_LIST_ID]);
  });

  it("keeps valid ids and resolves custom lists by name", () => {
    expect(
      reconcileCarouselListIds(
        ["old-ibex-uuid", "custom-1"],

        ["IBEX 35", "Mis valores"],

        apiLists,
      ),
    ).toEqual([CATALOG_IBEX_LIST_ID, "custom-1"]);
  });

  it("recovers IBEX when only stale ids remain without stored names", () => {
    expect(
      reconcileCarouselListIds(["old-ibex-uuid"], undefined, apiLists),
    ).toEqual([CATALOG_IBEX_LIST_ID]);
  });
});
