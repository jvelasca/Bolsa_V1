/**
 * AUTO · OPERAR — lanzadera descubrible «Verificar D→hoy» (P2).
 *
 * Solo aparece cuando la estrategia EJECUTADA del ciclo se resuelve (fail-closed); un hueco se
 * declara y una lectura en vuelo se anuncia como carga, nunca como ausencia. Reutiliza el flujo
 * compartido (`useDiaDVerifyLaunch`), que aquí se espía, y NO fabrica el enlace.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
} from "@bolsa/shared";

const launch = vi.hoisted(() => vi.fn());
const strategyViewState = vi.hoisted(() => ({ view: null as unknown }));

vi.mock("@/features/trading/use-dia-d-verify-launch", () => ({
  useDiaDVerifyLaunch: () => launch,
}));

vi.mock("@/features/auto/use-auto-operation-strategy", () => ({
  useAutoOperationStrategy: () => ({ view: strategyViewState.view }),
}));

import { AutoOperarVerifyAction } from "@/features/auto/auto-operar-verify-action";
import { buildAutoOperationStrategyView } from "@/features/auto/auto-operation-strategy";

function slot(
  partial: Partial<InstrumentStrategyTopSlotV1> = {},
): InstrumentStrategyTopSlotV1 {
  return {
    rank: 1,
    label: "SMA cross",
    stars: 3,
    score: 70,
    source: "coach",
    strategyDefinitionId: "def-1",
    strategyType: "sma_crossover",
    ...partial,
  };
}

function top(
  partial: Partial<InstrumentStrategyTopV1> = {},
): InstrumentStrategyTopV1 {
  return {
    id: "top-1",
    instrumentId: "uuid-1",
    timeframe: "1d",
    status: "active",
    version: 1,
    evidenceLevel: "lab_validated",
    slots: [slot()],
    coachFacts: { recommendations: [{ rank: 1, reasons: ["Estrellas 3/5"] }] },
    createdAt: "2026-10-01T00:00:00Z",
    updatedAt: "2026-10-01T00:00:00Z",
    ...partial,
  };
}

const definition = {
  indicatorSpecs: [{ definitionId: "rsi", parameters: { period: 14 } }],
  presetKey: "sma_crossover" as const,
};

const CYCLE = {
  cycleId: "cyc-1",
  instrumentId: "AAPL",
  strategyPresetKey: "sma_crossover",
  strategyVersion: "sv-1",
};

function resolvableView() {
  return buildAutoOperationStrategyView({
    cycle: {
      instrumentId: CYCLE.instrumentId,
      strategyPresetKey: CYCLE.strategyPresetKey,
      strategyVersion: CYCLE.strategyVersion,
    },
    instrumentId: "uuid-1",
    top: top(),
    definition,
  });
}

function unresolvableView() {
  return buildAutoOperationStrategyView({
    cycle: { instrumentId: "AAPL", strategyVersion: "sv-1" },
    instrumentId: "uuid-1",
    top: top(),
    definition,
  });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  strategyViewState.view = null;
});

describe("AutoOperarVerifyAction", () => {
  it("lanza la verificación con la estrategia EJECUTADA cuando se resuelve", () => {
    strategyViewState.view = resolvableView();
    render(<AutoOperarVerifyAction cycle={CYCLE} />);

    const button = screen.getByTestId("auto-operar-verify-dia-d");
    expect(button.textContent).toContain("Verificar D→hoy");
    expect(button.getAttribute("data-cycle-id")).toBe("cyc-1");

    fireEvent.click(button);
    expect(launch).toHaveBeenCalledTimes(1);
    expect(launch).toHaveBeenCalledWith(
      expect.objectContaining({
        instrumentId: "uuid-1",
        symbol: "AAPL",
        strategyDefinitionId: "def-1",
        cycleId: "cyc-1",
        strategyPresetKey: "sma_crossover",
        strategyVersion: "sv-1",
      }),
    );
  });

  it("no fabrica el enlace: declara el hueco cuando la ejecutada no se resuelve", () => {
    strategyViewState.view = unresolvableView();
    render(<AutoOperarVerifyAction cycle={CYCLE} />);

    expect(screen.queryByTestId("auto-operar-verify-dia-d")).toBeNull();
    const gap = screen.getByTestId("auto-operar-verify-gap");
    expect(gap.textContent).toContain("no declara su estrategia ejecutada");
  });

  it("una lectura en vuelo se anuncia como carga, no como ausencia", () => {
    strategyViewState.view = buildAutoOperationStrategyView({
      cycle: { instrumentId: "AAPL" },
      instrumentId: null,
      top: null,
      definition: null,
      loading: true,
    });
    render(<AutoOperarVerifyAction cycle={CYCLE} />);

    expect(
      screen.getByTestId("auto-operar-verify-loading").textContent,
    ).toContain("Comprobando");
    expect(screen.queryByTestId("auto-operar-verify-gap")).toBeNull();
    expect(screen.queryByTestId("auto-operar-verify-dia-d")).toBeNull();
  });

  it("sin vista no lanza la verificación y no finge un enlace", () => {
    strategyViewState.view = null;
    render(<AutoOperarVerifyAction cycle={CYCLE} />);
    expect(screen.queryByTestId("auto-operar-verify-dia-d")).toBeNull();
    expect(launch).not.toHaveBeenCalled();
  });
});
