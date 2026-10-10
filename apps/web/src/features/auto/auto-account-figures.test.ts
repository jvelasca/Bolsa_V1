import { describe, expect, it } from "vitest";
import {
  AUTO_ACCOUNT_CASH_LABEL,
  AUTO_ACCOUNT_CLOSED_PNL_LABEL,
  AUTO_ACCOUNT_OPEN_PNL_LABEL,
  buildAutoAccountFigures,
} from "@/features/auto/auto-account-figures";
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
      "realized",
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
    expect(missing.find((item) => item.id === "realized")?.value).toBe(
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
      "12.50 € en la cuenta simulada",
    );
    expect(JSON.stringify(figures)).not.toContain("DINERO REAL");
    expect(JSON.stringify(figures)).not.toContain("Posición abierta");
  });

  it("pinta el P&L realizado agregado cuando está medido", () => {
    const figures = buildAutoAccountFigures({
      summary: {
        positionsCount: 1,
        cash: 10000,
        totalUnrealizedPnl: 12.5,
        totalRealizedPnl: 94.5,
      },
      riskLabel: "Normal",
    });
    const realized = figures.find((item) => item.id === "realized");
    expect(realized?.label).toBe("Resultado de operaciones cerradas");
    expect(realized?.value).toBe("94.50 € en la cuenta simulada");
    // La separación SIM/dinero real se mantiene explícita.
    expect(realized?.value).toContain("cuenta simulada");
  });

  it("declara el hueco del P&L realizado (null) sin fabricar un 0", () => {
    const figures = buildAutoAccountFigures({
      summary: {
        positionsCount: 0,
        cash: 10000,
        totalUnrealizedPnl: 0,
        totalRealizedPnl: null,
      },
      riskLabel: "Normal",
    });
    expect(figures.find((item) => item.id === "realized")?.value).toBe(
      AUTO_HOME_NO_DATA_LABEL,
    );
    expect(figures.find((item) => item.id === "realized")?.value).not.toBe(
      "0.00 € en la cuenta simulada",
    );
  });

  it("un P&L realizado ausente también es un hueco declarado", () => {
    const figures = buildAutoAccountFigures({
      summary: { positionsCount: 0, cash: 10000, totalUnrealizedPnl: 0 },
      riskLabel: "Normal",
    });
    expect(figures.find((item) => item.id === "realized")?.value).toBe(
      AUTO_HOME_NO_DATA_LABEL,
    );
  });

  it("rotula abierto vs cerrado sin ambigüedad (H4)", () => {
    const figures = buildAutoAccountFigures({
      summary: {
        positionsCount: 2,
        cash: 10000,
        totalUnrealizedPnl: 12.5,
        totalRealizedPnl: 94.5,
      },
      riskLabel: "Normal",
    });
    expect(figures.find((item) => item.id === "pnl")?.label).toBe(
      AUTO_ACCOUNT_OPEN_PNL_LABEL,
    );
    expect(figures.find((item) => item.id === "realized")?.label).toBe(
      AUTO_ACCOUNT_CLOSED_PNL_LABEL,
    );
    expect(figures.find((item) => item.id === "cash")?.label).toBe(
      AUTO_ACCOUNT_CASH_LABEL,
    );
    // La separación SIM/dinero real se mantiene explícita en el valor.
    expect(figures.find((item) => item.id === "pnl")?.value).toContain(
      "cuenta simulada",
    );
    expect(figures.find((item) => item.id === "realized")?.value).toContain(
      "cuenta simulada",
    );
  });
});
