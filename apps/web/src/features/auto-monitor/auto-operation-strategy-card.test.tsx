/**
 * Tarjeta «Estrategia que sustenta la señal»: composición visual del puente P3/P4.
 *
 * Se prueba la pieza de forma aislada (recibe la vista ya compuesta): identidad de testids,
 * rank != 1 declarado, LISTA COMPLETA de razones (no `reasons[0] (+N)`) y estado de carga que
 * nunca se disfraza de ausencia de dato.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AutoOperationStrategyCard } from "@/features/auto-monitor/auto-operation-strategy-card";
import {
  AUTO_OPERATION_STRATEGY_MATCH_LABELS,
  AUTO_OPERATION_STRATEGY_NO_DATA,
  type AutoOperationStrategyViewV1,
} from "@/features/auto/auto-operation-strategy";

function view(
  partial: Partial<AutoOperationStrategyViewV1> = {},
): AutoOperationStrategyViewV1 {
  return {
    symbol: "AAA",
    instrumentId: "uuid-aaa",
    strategyDefinitionId: "def-1",
    strategyLabel: "SMA cross",
    rank: 1,
    indicators: ["RSI"],
    reasons: ["Estrellas 3/5", "DD -12%"],
    match: "same",
    matchLabel: AUTO_OPERATION_STRATEGY_MATCH_LABELS.same,
    declaredCycleStrategyVersion: "sma_crossover",
    verifyHref:
      "/backtests?tab=run&instrumentId=uuid-aaa&focus=detail&verify=1",
    gapReason: null,
    loading: false,
    ...partial,
  };
}

function renderCard(
  props: Partial<Parameters<typeof AutoOperationStrategyCard>[0]> = {},
) {
  const onVerify = props.onVerify ?? vi.fn();
  render(
    <AutoOperationStrategyCard
      view={props.view ?? view()}
      onVerify={onVerify}
      disabled={props.disabled}
      loading={props.loading}
    />,
  );
  return { onVerify };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AutoOperationStrategyCard", () => {
  it("pinta la cadena completa conservando los testids", () => {
    renderCard();

    const card = screen.getByTestId("auto-operation-strategy");
    expect(card.getAttribute("data-match")).toBe("same");
    expect(screen.getByTestId("auto-operation-strategy-chain")).toBeTruthy();
    expect(
      screen.getByTestId("auto-operation-strategy-label").textContent,
    ).toContain("#1 SMA cross");
    expect(
      screen.getByTestId("auto-operation-strategy-indicators").textContent,
    ).toContain("RSI");
    expect(
      screen.getByTestId("auto-operation-strategy-match").textContent,
    ).toContain("sma_crossover");
    // Sin hueco real no se pinta el rótulo de ausencia.
    expect(screen.queryByTestId("auto-operation-strategy-gap")).toBeNull();
  });

  it("con rank != 1 declara el puesto real y que NO es la #1", () => {
    renderCard({ view: view({ rank: 2, strategyLabel: "F-D exp" }) });

    expect(
      screen.getByTestId("auto-operation-strategy-label").textContent,
    ).toContain("#2 F-D exp");
    const note = screen.getByTestId("auto-operation-strategy-rank-note");
    expect(note.textContent).toContain("No es la #1");
    expect(note.textContent).toContain("#2");
    // La tarjeta NO afirma «Estrategia #1» cuando el puesto no es 1.
    expect(
      screen.getByTestId("auto-operation-strategy-chain").textContent,
    ).not.toContain("Estrategia #1");
  });

  it("pinta la LISTA COMPLETA de razones (hasta 5) en vez de `reasons[0] (+N)`", () => {
    const reasons = [
      "Estrellas 3/5",
      "DD -12%",
      "Expectancy +0.4R",
      "Hit 58%",
      "Muestra 42",
      "Régimen alcista",
    ];
    renderCard({ view: view({ reasons }) });

    const list = within(screen.getByTestId("auto-operation-strategy-reason"));
    const rows = list.getAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(rows.map((row) => row.textContent)).toEqual(reasons.slice(0, 5));
    // No se resume en `(+N)`.
    expect(
      screen.getByTestId("auto-operation-strategy-reason").textContent,
    ).not.toContain("(+");
  });

  it("sin razones declara «Sin dato todavía»", () => {
    renderCard({ view: view({ reasons: [] }) });
    expect(
      screen.getByTestId("auto-operation-strategy-reason").textContent,
    ).toContain(AUTO_OPERATION_STRATEGY_NO_DATA);
  });

  it("en carga muestra un estado de carga y NUNCA un falso hueco", () => {
    renderCard({
      view: view({
        instrumentId: null,
        strategyDefinitionId: null,
        strategyLabel: AUTO_OPERATION_STRATEGY_NO_DATA,
        rank: null,
        indicators: [],
        reasons: [],
        match: "unknown",
        matchLabel: AUTO_OPERATION_STRATEGY_MATCH_LABELS.unknown,
        declaredCycleStrategyVersion: null,
        verifyHref: null,
        gapReason: null,
        loading: true,
      }),
      loading: true,
    });

    expect(
      screen.getByTestId("auto-operation-strategy-loading").textContent,
    ).toContain("Cargando");
    // El hueco transitorio no se declara ausencia.
    expect(screen.queryByTestId("auto-operation-strategy-gap")).toBeNull();
    expect(
      screen.getByTestId("auto-operation-strategy-label").textContent,
    ).toContain("Cargando");
  });

  it("llama a onVerify al pulsar y respeta el estado deshabilitado", () => {
    const { onVerify } = renderCard();
    fireEvent.click(screen.getByTestId("auto-operation-strategy-verify-dia-d"));
    expect(onVerify).toHaveBeenCalledTimes(1);

    cleanup();
    const disabledOnVerify = vi.fn();
    renderCard({ disabled: true, onVerify: disabledOnVerify });
    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.hasAttribute("disabled")).toBe(true);
    fireEvent.click(button);
    expect(disabledOnVerify).not.toHaveBeenCalled();
  });
});
