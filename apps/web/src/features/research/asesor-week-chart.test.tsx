/**
 * Asesor → Diario · gráfico de la semana (H-22).
 *
 * Lo que debe morder: sin datos no se dibuja un SVG con barras imaginarias; un
 * cero medido (`[]`) se distingue de un campo que no llegó (`null`).
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DailyOpsWeekDayV1 } from "@bolsa/shared";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
import { AsesorWeekChart } from "@/features/research/asesor-week-chart";

afterEach(() => cleanup());

const weekday: DailyOpsWeekDayV1 = {
  date: "2026-11-10",
  tradeCount: 2,
  ledgerCount: 2,
  balanceAfter: 25300,
  netAmount: 120,
};

describe("AsesorWeekChart · ausencia ≠ cero", () => {
  it("con días dibuja el SVG de la semana", () => {
    render(<AsesorWeekChart week={[weekday]} />);
    expect(
      screen.getByRole("img", { name: /Evolución semanal/i }),
    ).toBeTruthy();
    expect(screen.queryByTestId("asesor-week-absent")).toBeNull();
  });

  it("sin campo declara «Sin dato todavía» y no dibuja", () => {
    render(<AsesorWeekChart week={undefined} />);
    const absent = screen.getByTestId("asesor-week-absent");
    expect(absent.textContent).toContain(ABSENT_DATA_NOT_MEASURED);
    expect(
      screen.queryByRole("img", { name: /Evolución semanal/i }),
    ).toBeNull();
  });

  it("un `null` también se declara", () => {
    render(<AsesorWeekChart week={null} />);
    expect(screen.getByTestId("asesor-week-absent").textContent).toContain(
      ABSENT_DATA_NOT_MEASURED,
    );
  });

  it("una semana vacía medida dice «sin movimientos», no «sin dato»", () => {
    render(<AsesorWeekChart week={[]} />);
    const absent = screen.getByTestId("asesor-week-absent");
    expect(absent.textContent).toContain("Sin movimientos registrados");
    expect(absent.textContent).not.toContain(ABSENT_DATA_NOT_MEASURED);
  });
});

describe("AsesorWeekChart · el arreglo no normaliza a colección vacía", () => {
  it("no usa `?? []` ni `?? 0` sobre el dato del parte", () => {
    const src = readFileSync(
      resolve(__dirname, "asesor-week-chart.tsx"),
      "utf8",
    );
    expect(src).not.toContain("?? []");
    expect(src).not.toContain("week ??");
  });
});
