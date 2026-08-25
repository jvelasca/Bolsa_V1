/**
 * Índice Operativo — tests de ranking «en estudio».
 */

import { describe, expect, it } from "vitest";
import {
  computeIndiceOperativo,
  resolveIndiceOperativo,
  estudioRankProgressPct,
  formatEstudioRankLabel,
  rankIndiceOperativo,
} from "@/features/trading/operativa-index";

describe("operativa-index", () => {
  it("computeIndiceOperativo clamps and applies distress floor", () => {
    expect(computeIndiceOperativo({ compositeDisplay100: 72 })).toBe(72);
    expect(
      computeIndiceOperativo({ compositeDisplay100: 80, distress: true }),
    ).toBe(40);
    expect(computeIndiceOperativo({ compositeDisplay100: null })).toBeNull();
  });

  it("resolveIndiceOperativo prefers server field over client formula", () => {
    expect(
      resolveIndiceOperativo({
        indiceOperativo: 40,
        compositeDisplay100: 90,
        distress: false,
      }),
    ).toBe(40);
    expect(
      resolveIndiceOperativo({
        indiceOperativo: null,
        compositeDisplay100: 80,
        distress: true,
      }),
    ).toBe(40);
  });

  it("ranks by IO desc and formats label", () => {
    const rows = [
      { instrumentId: "a", io: 50, ta: 40, fa: 60 },
      { instrumentId: "b", io: 90, ta: 80, fa: 70 },
      { instrumentId: "c", io: null, ta: null, fa: null },
    ];
    const r = rankIndiceOperativo(rows, "a");
    expect(r).toEqual({ rank: 2, total: 3, io: 50, ta: 40, fa: 60 });
    expect(formatEstudioRankLabel(2, 3)).toBe("El 2 de 3 en Estudio");
    expect(estudioRankProgressPct(1, 3)).toBe(100);
    expect(estudioRankProgressPct(3, 3)).toBe(0);
  });
});
