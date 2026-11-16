/**
 * R4 — P2/P3 en el primer nivel del resultado del LAB.
 *
 * - P3: el run declara su estrategia #1 y la especificación de indicadores
 *   (`strategySlotToIndicatorDetails`) sin abrir el detalle.
 * - P2: declara entrada, stop y objetivos cuando existe plan, y distingue
 *   `WATCH` (`vigilar`), `BLOCKED` (`bloqueada`), `EXPIRED` (`caducada`) y
 *   «sin plan declarado» en vez de dejar un hueco vacío (`UNKNOWN ≠ 0`).
 */

import { cleanup, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import type { Mock } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  BacktestRunDetailDto,
  OperationalPlanViewV1,
} from "@bolsa/shared";
import { BacktestResultDecisionCard } from "@/features/backtests/backtest-result-decision-card";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";

vi.mock("@/lib/api", () => ({
  api: { getStrategy: vi.fn() },
}));

vi.mock("@/features/trading/use-instrument-operational-context", () => ({
  useInstrumentOperationalContext: vi.fn(),
}));

import { api } from "@/lib/api";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";

const getStrategy = api.getStrategy as unknown as Mock;
const useContext = useInstrumentOperationalContext as unknown as Mock;

function plan(
  overrides: Partial<OperationalPlanViewV1> = {},
): OperationalPlanViewV1 {
  return {
    phase: "prepared",
    phaseLabel: "Preparada",
    direction: "long",
    entry: 100,
    stopVigente: 95,
    stopInicial: 95,
    target1: 110,
    target2: 120,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: 2,
    riskR: 5,
    currentPrice: 101,
    unrealizedR: null,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: true,
    emptyCopy: "",
    ...overrides,
  };
}

function context(overrides: Record<string, unknown> = {}) {
  return {
    instrumentId: "inst-1",
    accountId: "acc-1",
    phase: "preparada",
    plan: plan(),
    showsPlanLevels: true,
    trailing: {
      show: false,
      stopVigente: 95,
      stopSugerido: null,
      applied: false,
      label: "↗ Trailing sugerido",
      stopVigenteLabel: "Stop operativo",
      stopSugeridoLabel: "Stop sugerido",
      statusLabel: null,
    },
    study: null,
    originStudy: null,
    position: null,
    positionMeasured: true,
    portfolioError: false,
    studiesMeasured: true,
    studiesError: false,
    studiesTruncated: false,
    inEstudio: true,
    inConfirmQueue: false,
    confirmQueueCount: 0,
    orderPendingFill: false,
    submitIntent: null,
    loading: false,
    ...overrides,
  };
}

function detail(
  overrides: Partial<BacktestRunDetailDto> = {},
): BacktestRunDetailDto {
  return {
    id: "run-1",
    instrumentId: "inst-1",
    symbol: "ACA",
    name: "Acerinox",
    strategyType: "sma_crossover",
    initialCash: 10_000,
    finalEquity: 10_500,
    totalReturnPct: 5,
    maxDrawdownPct: 4,
    tradeCount: 12,
    winCount: 7,
    barCount: 250,
    firstDate: "2025-01-01",
    lastDate: "2025-12-31",
    createdAt: "2026-01-01T00:00:00Z",
    trades: [],
    ...overrides,
  };
}

beforeEach(() => {
  getStrategy.mockResolvedValue({ data: { definition: null } });
  useContext.mockReturnValue(context());
});

function render(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return rtlRender(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BacktestResultDecisionCard", () => {
  it("declara estrategia #1, indicadores y niveles del plan en primer nivel", () => {
    render(<BacktestResultDecisionCard detail={detail()} markPrice={101} />);

    expect(screen.getByTestId("backtest-decision-first-level")).toBeTruthy();
    expect(screen.getByText(/#1/)).toBeTruthy();
    // P3 · preset como fuente declarada de indicadores.
    expect(
      screen.getByTestId("backtest-decision-indicators").textContent,
    ).toContain("SMA");
    // P2 · entrada, stop y objetivos.
    const levels = screen.getByTestId("backtest-decision-levels").textContent;
    expect(levels).toContain("Entrada");
    expect(levels).toContain("100,00");
    expect(levels).toContain("Stop");
    expect(levels).toContain("95,00");
    expect(levels).toContain("T1");
    expect(levels).toContain("110,00");
    expect(levels).toContain("T2");
    expect(levels).toContain("120,00");
    expect(screen.queryByTestId("backtest-decision-no-plan")).toBeNull();
  });

  it("sin plan declara el hueco en vez de dejarlo vacío", () => {
    useContext.mockReturnValue(
      context({
        phase: "vigilar",
        plan: plan({
          hasPlan: false,
          entry: null,
          stopVigente: null,
          target1: null,
          target2: null,
        }),
        showsPlanLevels: false,
      }),
    );
    render(<BacktestResultDecisionCard detail={detail()} />);

    expect(screen.getByTestId("backtest-decision-no-plan").textContent).toBe(
      "Sin plan declarado todavía",
    );
    expect(screen.getByTestId("backtest-decision-phase").textContent).toBe(
      "En estudio",
    );
    expect(screen.queryByTestId("backtest-decision-levels")).toBeNull();
  });

  it("distingue BLOCKED de EXPIRED por el estado de la fase", () => {
    useContext.mockReturnValue(
      context({
        phase: "bloqueada",
        plan: plan({ hasPlan: true }),
        showsPlanLevels: false,
      }),
    );
    const { unmount } = render(
      <BacktestResultDecisionCard detail={detail()} />,
    );
    expect(screen.getByTestId("backtest-decision-phase").textContent).toBe(
      "Bloqueada",
    );
    unmount();

    useContext.mockReturnValue(
      context({
        phase: "caducada",
        plan: plan({ hasPlan: true }),
        showsPlanLevels: false,
      }),
    );
    render(<BacktestResultDecisionCard detail={detail()} />);
    expect(screen.getByTestId("backtest-decision-phase").textContent).toBe(
      "Caducada",
    );
  });

  it("sin definición ni preset declara «Sin dato todavía» en indicadores", () => {
    render(
      <BacktestResultDecisionCard
        detail={detail({ strategyType: "tipo_desconocido" as never })}
      />,
    );
    expect(screen.getByTestId("backtest-decision-indicators").textContent).toBe(
      `Indicadores: ${ABSENT_DATA_NOT_MEASURED}`,
    );
  });
});
