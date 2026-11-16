/**
 * R7 — checklist pre-demo (`backtest-paper-checklist`) con la evidencia P1.
 *
 * Lo que debe morder:
 *   - un run sin medición neta se declara como hueco (aviso con ack), no como
 *     `0 %` ni como verde;
 *   - un run medido en bruto bloquea el despliegue (fail duro, no ack);
 *   - la fricción y la esperanza viajan al recibo de paper (`netEvidence`) sin
 *     mezclar bases: lo que se despliega es lo que se midió;
 *   - sin acuses el botón no habilita: la puerta no se salta sola.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §3.5 y §8 (R1/R7)
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BacktestRunDetailDto } from "@bolsa/shared";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";
import { BacktestPaperChecklist } from "@/features/backtests/backtest-paper-checklist";
import type { PaperNetEvidence } from "@/features/backtests/backtest-paper-gate";

afterEach(() => cleanup());

const NET_MEASURED: PaperNetEvidence = {
  returnBasis: "net",
  netReturnPct: 6.5,
  expectancyCurrency: 12.4,
  roundTripCostBps: 32,
  netTradeCount: 18,
};

function detail(
  partial: Partial<BacktestRunDetailDto> = {},
): BacktestRunDetailDto {
  return {
    id: "run-1",
    instrumentId: "inst-1",
    symbol: "IBE.MC",
    name: "Test",
    strategyType: "sma_crossover",
    initialCash: 10_000,
    finalEquity: 11_000,
    totalReturnPct: 10,
    maxDrawdownPct: 12,
    tradeCount: 8,
    winCount: 5,
    barCount: 500,
    firstDate: "2020-01-01",
    lastDate: "2024-01-01",
    createdAt: "2026-07-26T00:00:00Z",
    strategyDefinitionId: "strat-1",
    trades: [],
    ...partial,
  } as BacktestRunDetailDto;
}

type ChecklistProps = Parameters<typeof BacktestPaperChecklist>[0];

function setup(overrides: Partial<ChecklistProps> = {}) {
  const onDeploy = vi.fn();
  const props: ChecklistProps = {
    detail: detail(),
    excessReturnPct: 3,
    buyHoldReturnPct: 7,
    netEvidence: NET_MEASURED,
    onDeploy,
    ...overrides,
  };
  render(<BacktestPaperChecklist {...props} />);
  return { onDeploy, props };
}

/** Marca todos los avisos para habilitar el despliegue. */
function acknowledgeAll() {
  for (const checkbox of screen.getAllByRole("checkbox")) {
    fireEvent.click(checkbox);
  }
}

describe("BacktestPaperChecklist · P1 neto", () => {
  it("declara la ausencia de medición neta en vez de fingir 0", () => {
    setup({ netEvidence: null });

    expect(
      screen.getByText(
        /Sin medición neta declarada \(run anterior al gate P1\)/,
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/Neto \+/)).toBeNull();
  });

  it("bloquea el despliegue de un run bruto aunque tenga OOS", () => {
    setup({
      netEvidence: {
        ...NET_MEASURED,
        returnBasis: "gross",
        netReturnPct: null,
      },
    });

    expect(
      screen.getByText(/se midió SIN fricción \(returnBasis = gross\)/),
    ).toBeTruthy();
    acknowledgeAll();
    expect(screen.getByText(/Hay bloqueos duros/)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: PAPER_PATH_LAB.cta }),
    ).toBeDisabled();
  });

  it("no habilita sin acuses y envía la medición neta al recibo", () => {
    const { onDeploy } = setup();

    const button = screen.getByRole("button", {
      name: PAPER_PATH_LAB.cta,
    });
    expect(button).toBeDisabled();
    expect(screen.getByText(/Neto \+6\.5% tras 32 bps/)).toBeTruthy();

    acknowledgeAll();
    expect(button).toBeEnabled();
    fireEvent.click(button);

    expect(onDeploy).toHaveBeenCalledTimes(1);
    const payload = onDeploy.mock.calls[0]![0] as {
      labEvidence: { returnBasis: string; roundTripCostBps: number };
    };
    expect(payload.labEvidence.returnBasis).toBe("net");
    expect(payload.labEvidence.roundTripCostBps).toBe(32);
  });
});
