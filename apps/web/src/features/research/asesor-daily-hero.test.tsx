/**
 * Asesor → Diario · hero — guardas del slice A4.
 *
 * Lo que debe morder:
 *   - los tres estados de ausencia se distinguen y no culpan a la cuenta;
 *   - una cifra sin medir dice «Sin dato todavía», nunca el guion de auditoría;
 *   - la capa visual usa tokens del sistema (nada de gradiente hex, `text-white`,
 *     `bg-black/20` ni `font-serif`).
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DailyOpsReportV1 } from "@bolsa/shared";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
import { AsesorDailyHero } from "@/features/research/asesor-daily-hero";

afterEach(() => cleanup());

/** Informe con todos los importes sin medir (`null` ≠ 0). */
const reportWithGaps = {
  estudioStatus: "ok",
  estudioCount: 0,
  summary: {
    totalEquity: null,
    cash: null,
    totalUnrealizedPnl: null,
    positionsCount: 0,
  },
} as unknown as DailyOpsReportV1;

function renderHero(
  props: Partial<ComponentProps<typeof AsesorDailyHero>> = {},
) {
  return render(
    <MemoryRouter>
      <AsesorDailyHero
        hasActiveAccount={false}
        asOf="2026-11-15"
        mode="paper"
        estudioCount={0}
        report={undefined}
        isLoading={false}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe("AsesorDailyHero · ausencia ≠ midiendo", () => {
  it("sin cuenta activa pide seleccionar una cuenta", () => {
    renderHero();
    expect(
      screen.getByText("Selecciona una cuenta DEMO activa."),
    ).toBeInTheDocument();
  });

  it("con cuenta válida y el informe cargando dice «Midiendo…»", () => {
    renderHero({ hasActiveAccount: true, isLoading: true });
    expect(screen.getByText("Midiendo…")).toBeInTheDocument();
    expect(
      screen.queryByText(/Selecciona una cuenta DEMO activa/),
    ).not.toBeInTheDocument();
  });

  it("con cuenta válida y sin informe dice «Sin dato todavía» sin culpar a la cuenta", () => {
    renderHero({ hasActiveAccount: true });
    expect(screen.getByText(/Sin dato todavía/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Selecciona una cuenta DEMO activa/),
    ).not.toBeInTheDocument();
  });

  it("las cifras ausentes se declaran, no se pintan con el guion de auditoría", () => {
    const { container } = renderHero({
      hasActiveAccount: true,
      report: reportWithGaps,
    });
    expect(container.textContent).toContain(ABSENT_DATA_NOT_MEASURED);
    expect(container.textContent).not.toContain("—");
  });
});

describe("AsesorDailyHero · capa visual con tokens", () => {
  it("no usa gradiente hex, text-white, bg-black/20 ni font-serif", () => {
    const source = readFileSync(
      resolve(__dirname, "asesor-daily-hero.tsx"),
      "utf8",
    )
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:])\/\/.*$/gm, "$1");
    expect(source).not.toContain("linear-gradient");
    expect(source).not.toContain("font-serif");
    expect(source).not.toContain("text-white");
    expect(source).not.toContain("bg-black/20");
    expect(source).toContain("bg-card");
    expect(source).toContain("text-muted-foreground");
    expect(source).toContain("border-border");
  });
});
