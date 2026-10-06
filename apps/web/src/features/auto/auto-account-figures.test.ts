import { describe, expect, it } from "vitest";
import { buildAutoAccountFigures } from "@/features/auto/auto-account-figures";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";

describe("buildAutoAccountFigures", () => {
  it("copia el resumen y no inventa un cero cuando falta", () => {
    const missing = buildAutoAccountFigures({
      summary: null,
      riskLabel: "Normal",
    });
    expect(missing.map((item) => item.id)).toEqual([
      "position",
      "pnl",
      "cash",
      "risk",
    ]);
    expect(missing.find((item) => item.id === "position")?.value).toBe(
      AUTO_HOME_NO_DATA_LABEL,
    );
    expect(missing.find((item) => item.id === "cash")?.value).toBe(
      AUTO_HOME_NO_DATA_LABEL,
    );
    expect(missing.find((item) => item.id === "pnl")?.value).toBe(
      AUTO_HOME_NO_DATA_LABEL,
    );
    expect(missing.find((item) => item.id === "risk")?.value).toBe("Normal");
    expect(JSON.stringify(missing)).not.toContain("0.00");
  });

  it("rotula posición, efectivo y resultado como cuenta simulada", () => {
    const figures = buildAutoAccountFigures({
      summary: { positionsCount: 1, cash: 10000, totalUnrealizedPnl: 12.5 },
      riskLabel: AUTO_HOME_NO_DATA_LABEL,
    });
    expect(figures.find((item) => item.id === "position")?.value).toBe(
      "1 posición en la cuenta simulada",
    );
    expect(figures.find((item) => item.id === "cash")?.value).toBe(
      "10000.00 €",
    );
    expect(figures.find((item) => item.id === "pnl")?.value).toBe(
      "Resultado de la cuenta 12.50 €",
    );
    expect(JSON.stringify(figures)).not.toContain("DINERO REAL");
    expect(JSON.stringify(figures)).not.toContain("Posición abierta");
  });
});
