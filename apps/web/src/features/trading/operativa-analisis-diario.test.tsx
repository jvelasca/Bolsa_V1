/**
 * Banda ANÁLISIS DIARIO del panel DECISIÓN — render de las cuatro lecturas.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { InstrumentDailyAnalysisV1 } from "@bolsa/shared";
import { OperativaAnalisisDiario } from "@/features/trading/operativa-analisis-diario";

afterEach(() => cleanup());

function analysis(
  overrides: Partial<InstrumentDailyAnalysisV1> = {},
): InstrumentDailyAnalysisV1 {
  return {
    instrumentId: "inst-aapl",
    inEstudio: true,
    measured: true,
    studyMeta: {
      studiedAt: "2026-11-10T08:00:00.000Z",
      ageMs: 3_600_000,
      vigencia: "current",
      indicators: { primary: "ADX + DI", confirmation: "SMA" },
    },
    trends: [
      {
        key: "short_term",
        label: "Corto plazo",
        display: "Alcista",
        tone: "bullish",
        basis: "ADX + DI",
      },
      {
        key: "background",
        label: "De fondo",
        display: "Alcista",
        tone: "bullish",
        basis: "SMA",
      },
    ],
    tracking: {
      strategyRank: 1,
      strategyLabel: "Cruce SMA 20/50",
      indicators: [
        { definitionId: "sma", label: "SMA", display: "SMA 20/50" },
        { definitionId: "rsi", label: "RSI", display: "RSI 14" },
      ],
      reason: "Cruce limpio con ADX > 25",
      evidenceLevel: "lab_validated",
      stabilityLabel: "OOS estable",
      gap: null,
    },
    entry: {
      state: "preparada",
      stateLabel: "Preparada",
      entry: 100,
      stop: 94,
      target1: 112,
      target2: 124,
      expectedRR: 2,
      distancePct: 1,
      missing: "Disparador pendiente",
    },
    exit: null,
    gaps: [],
    ...overrides,
  };
}

function renderBand(props: {
  analysis: InstrumentDailyAnalysisV1;
  onRefreshStudy?: () => void;
  refreshPending?: boolean;
}) {
  return render(
    <MemoryRouter>
      <OperativaAnalisisDiario
        analysis={props.analysis}
        symbol="AAPL"
        timeframe="1d"
        labHref="/backtests?tab=run"
        onRefreshStudy={props.onRefreshStudy}
        refreshPending={props.refreshPending}
      />
    </MemoryRouter>,
  );
}

describe("OperativaAnalisisDiario", () => {
  it("muestra tendencia, seguimiento, entrada y vigencia", () => {
    renderBand({ analysis: analysis() });
    const root = screen.getByTestId("operativa-analisis-diario");
    expect(root.getAttribute("data-estudio")).toBe("true");
    expect(root.getAttribute("data-measured")).toBe("true");
    expect(root.getAttribute("data-phase")).toBe("preparada");

    const tendencia = screen.getByTestId("operativa-analisis-tendencia");
    expect(tendencia.textContent).toContain("Corto plazo");
    expect(tendencia.textContent).toContain("Alcista");
    expect(tendencia.querySelector('[data-tone="bullish"]')).toBeTruthy();

    const seguimiento = screen.getByTestId("operativa-analisis-seguimiento");
    expect(seguimiento.textContent).toContain("#1");
    expect(seguimiento.textContent).toContain("Cruce SMA 20/50");
    expect(seguimiento.textContent).toContain("Validada en LAB");
    expect(
      screen.getByTestId("operativa-analisis-indicadores").textContent,
    ).toContain("SMA 20/50 · RSI 14");
    expect(seguimiento.textContent).toContain(
      "Razón: Cruce limpio con ADX > 25",
    );

    const entrada = screen.getByTestId("operativa-analisis-entrada");
    expect(entrada.textContent).toContain("Preparada");
    expect(entrada.textContent).toContain("100,00");
    expect(entrada.textContent).toContain("Disparador pendiente");

    expect(screen.getByTestId("operativa-analisis-vigencia").textContent).toBe(
      "Vigente",
    );
    expect(screen.queryByTestId("operativa-analisis-salida")).toBeNull();
  });

  it("sin parte diario declara el hueco y ofrece actualizar", () => {
    const onRefreshStudy = vi.fn();
    renderBand({
      analysis: analysis({
        measured: false,
        studyMeta: null,
        trends: [],
        entry: null,
        gaps: ["Sin análisis diario todavía"],
      }),
      onRefreshStudy,
    });
    expect(
      screen.getByTestId("operativa-analisis-tendencia").textContent,
    ).toContain("Sin análisis diario todavía");
    screen.getByTestId("operativa-analisis-actualizar").click();
    expect(onRefreshStudy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("operativa-analisis-gaps").textContent).toContain(
      "Falta: Sin análisis diario todavía",
    );
  });

  it("en cartera muestra la escalera de salida y el trailing", () => {
    renderBand({
      analysis: analysis({
        entry: null,
        exit: {
          stop: 100,
          target1Hint: "✓ gestionado",
          target2Hint: "○ pendiente",
          trailingLabel: "No aplicado · requiere Confirm",
          unrealizedR: 1.4,
          invalidation: "Cierre diario bajo la SMA 50",
        },
      }),
    });
    const salida = screen.getByTestId("operativa-analisis-salida");
    expect(salida.textContent).toContain("100,00");
    expect(salida.textContent).toContain("✓ gestionado");
    expect(salida.textContent).toContain("○ pendiente");
    expect(salida.textContent).toContain("1,40R");
    expect(salida.textContent).toContain(
      "Invalida: Cierre diario bajo la SMA 50",
    );
    expect(
      screen.getByTestId("operativa-analisis-trailing").textContent,
    ).toContain("No aplicado · requiere Confirm");
    expect(screen.queryByTestId("operativa-analisis-entrada")).toBeNull();
  });

  it("fuera de Estudio no muestra seguimiento y lo declara", () => {
    renderBand({
      analysis: analysis({
        inEstudio: false,
        measured: false,
        trends: [],
        entry: null,
        gaps: ["Fuera de Estudio"],
      }),
    });
    const root = screen.getByTestId("operativa-analisis-diario");
    expect(root.getAttribute("data-estudio")).toBe("false");
    expect(
      screen.getByTestId("operativa-analisis-diario-fuera").textContent,
    ).toContain("Sin seguimiento diario: fuera de Estudio");
    expect(screen.queryByTestId("operativa-analisis-tendencia")).toBeNull();
    expect(screen.queryByTestId("operativa-analisis-seguimiento")).toBeNull();
  });
});
