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
import { buildAutoStrategyDiaDExplanation } from "@/features/auto/auto-strategy-dia-d-explanation";
import {
  AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL,
  AUTO_OPERATION_STRATEGY_DECLARED_LABEL,
  AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT,
  AUTO_OPERATION_STRATEGY_MATCH_LABELS,
  AUTO_OPERATION_STRATEGY_NO_DATA,
  AUTO_OPERATION_STRATEGY_VERIFY_EXECUTED_LABEL,
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
    declaredCyclePresetKey: "sma_crossover",
    declaredCycleStrategyVersion: "sv-1",
    executedStrategyDefinitionId: "def-1",
    executedStrategyLabel: "SMA cross",
    executedStrategyRank: 1,
    verifyTarget: "executed",
    verifyGapReason: null,
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
      explanation={props.explanation ?? null}
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

describe("AutoOperationStrategyCard · explicación P3→P4", () => {
  const explanation = () =>
    buildAutoStrategyDiaDExplanation({
      strategy: view(),
      cycle: {
        cycleId: "cyc-1",
        strategyPresetKey: "sma_crossover",
        strategyVersion: "sv-1",
      },
      artifact: {
        available: true,
        matrixBasis: "entryDay",
        readOnly: true,
        serving: "PRECOMPUTED_ARTIFACT",
        gate: { verdict: "READY", days: 4, episodes: 2, cycles: 32 },
        summary: {
          measuredValues: 1,
          mixed: 0,
          notMeasured: 0,
          oosSupported: 1,
          refuted: 0,
          values: 1,
        },
        values: [
          {
            symbol: "AAA",
            verdict: "OOS_SUPPORTED",
            evidenceQuality: "PRELIMINARY",
            expectancyR: 0.5,
            hitRate: 0.67,
            measuredCycles: 6,
            daysCovered: 4,
            windowDays: 6,
            errorTotal: 0,
            limits: {
              minCycles: 5,
              minHitRate: 0.5,
              supportedMinCycles: 20,
              strongMinCycles: 32,
            },
          },
        ],
        cycles: [{ cycleId: "cyc-1", symbol: "AAA", realizedR: 1.2 }],
      },
    });

  it("sin explicación no pinta el bloque (no declara un falso hueco)", () => {
    renderCard();
    expect(screen.queryByTestId("auto-strategy-dia-d")).toBeNull();
  });

  it("con explicación pinta el alcance del VALOR y conserva los testids de la tarjeta", () => {
    renderCard({ explanation: explanation() });

    expect(screen.getByTestId("auto-operation-strategy")).toBeTruthy();
    expect(screen.getByTestId("auto-operation-strategy-chain")).toBeTruthy();
    const block = screen.getByTestId("auto-strategy-dia-d");
    expect(block.getAttribute("data-strategy-declared")).toBe("true");
    expect(
      screen.getByTestId("auto-strategy-dia-d-scope").textContent,
    ).toContain("no de la estrategia");
    // Los suelos de muestra se declaran, no se relajan.
    expect(
      screen.getByTestId("auto-strategy-dia-d-floors").textContent,
    ).toContain("32");
  });

  it("en carga declara el hueco como TRANSITORIO (no como ausencia)", () => {
    const empty = buildAutoStrategyDiaDExplanation({
      strategy: view({ instrumentId: null }),
      cycle: null,
      artifact: null,
      loading: true,
    });
    renderCard({ explanation: empty });

    expect(screen.getByTestId("auto-strategy-dia-d-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-strategy-dia-d-gap")).toBeNull();
  });
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
    // La identidad EXACTA declarada se pinta aparte del sello opaco del motor.
    expect(
      screen.getByTestId("auto-operation-strategy-preset-key").textContent,
    ).toBe("sma_crossover");
    expect(
      screen.getByTestId("auto-operation-strategy-declared-version")
        .textContent,
    ).toContain("sv-1");
    // Sin hueco real no se pinta el rótulo de ausencia.
    expect(screen.queryByTestId("auto-operation-strategy-gap")).toBeNull();
  });

  it("distingue la MEJOR del valor (Finalistas) de la EJECUTADA declarada por el ciclo y declara la identidad EXACTA", () => {
    renderCard();

    const chain = screen.getByTestId("auto-operation-strategy-chain");
    // Bloque (a): mejor estrategia DISPONIBLE del valor (TOP #1 de Finalistas).
    expect(chain.textContent).toContain(
      AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL,
    );
    // Bloque (b): estrategia EJECUTADA que declara el ciclo (clave exacta + sello opaco).
    expect(chain.textContent).toContain(AUTO_OPERATION_STRATEGY_DECLARED_LABEL);
    // Se conserva la clave EXACTA declarada y su emparejamiento en el testid estable.
    expect(
      screen.getByTestId("auto-operation-strategy-match").textContent,
    ).toContain("sma_crossover");
    // Declaración de honestidad en superficie: identidad EXACTA (`presetKey`), no heurística.
    expect(
      screen.getByTestId("auto-operation-strategy-match-exact").textContent,
    ).toBe(AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT);
    expect(
      screen.getByTestId("auto-operation-strategy-match-exact").textContent,
    ).toContain("identidad EXACTA");
  });

  it("sin clave exacta declarada muestra «Sin dato todavía» (no finge la identidad)", () => {
    renderCard({
      view: view({
        match: "unknown",
        matchLabel: AUTO_OPERATION_STRATEGY_MATCH_LABELS.unknown,
        declaredCyclePresetKey: null,
      }),
    });

    expect(
      screen.getByTestId("auto-operation-strategy-preset-key").textContent,
    ).toBe(AUTO_OPERATION_STRATEGY_NO_DATA);
    // El sello opaco se sigue pintando (no se oculta el dato que SÍ existe).
    expect(
      screen.getByTestId("auto-operation-strategy-declared-version")
        .textContent,
    ).toContain("sv-1");
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
        declaredCyclePresetKey: null,
        declaredCycleStrategyVersion: null,
        executedStrategyDefinitionId: null,
        executedStrategyLabel: null,
        executedStrategyRank: null,
        verifyTarget: null,
        verifyGapReason: null,
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

  it("pinta la estrategia EJECUTADA resuelta y el rótulo de que es lo que se verifica", () => {
    renderCard();

    expect(
      screen.getByTestId("auto-operation-strategy-executed-label").textContent,
    ).toBe(AUTO_OPERATION_STRATEGY_VERIFY_EXECUTED_LABEL);
    const executed = screen.getByTestId("auto-operation-strategy-executed");
    expect(executed.textContent).toContain("#1 SMA cross");
    expect(executed.getAttribute("data-verify-target")).toBe("executed");
    expect(
      screen
        .getByTestId("auto-operation-strategy-verify-dia-d")
        .getAttribute("data-verify-target"),
    ).toBe("executed");
  });

  it("declara un ranking real distinto del #1 cuando la ejecutada no es la mejor del valor", () => {
    renderCard({
      view: view({
        match: "differs",
        matchLabel: AUTO_OPERATION_STRATEGY_MATCH_LABELS.differs,
        executedStrategyDefinitionId: "def-3",
        executedStrategyLabel: "F-D exp",
        executedStrategyRank: 3,
      }),
    });

    const executed = screen.getByTestId("auto-operation-strategy-executed");
    expect(executed.textContent).toContain("#3 F-D exp");
    expect(executed.getAttribute("data-verify-target")).toBe("executed");
  });

  it("deshabilita el CTA y declara el hueco cuando no se resuelve la ejecutada (fail-closed)", () => {
    renderCard({
      view: view({
        executedStrategyDefinitionId: null,
        executedStrategyLabel: null,
        executedStrategyRank: null,
        verifyTarget: null,
        verifyGapReason:
          "Sin dato todavía: el ciclo no declara su estrategia ejecutada (`presetKey`).",
        verifyHref: null,
      }),
    });

    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(button.getAttribute("data-verify-target")).toBe("none");
    // El hueco de la EJECUTADA se declara en su propio testid (no se cae al #1 en silencio).
    expect(
      screen.getByTestId("auto-operation-strategy-executed").textContent,
    ).toContain("no declara su estrategia ejecutada");
  });

  it("asocia programáticamente el motivo del CTA inhabilitado (P3)", () => {
    renderCard({
      view: view({
        executedStrategyDefinitionId: null,
        executedStrategyLabel: null,
        executedStrategyRank: null,
        verifyTarget: null,
        verifyGapReason:
          "Sin dato todavía: el ciclo no declara su estrategia ejecutada (`presetKey`).",
        verifyHref: null,
      }),
    });

    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("aria-describedby")).toBe(
      "auto-operation-strategy-executed",
    );
    // El id descrito EXISTE y contiene el motivo visible (no solo el `title`).
    const described = document.getElementById(
      "auto-operation-strategy-executed",
    );
    expect(described?.textContent).toContain(
      "no declara su estrategia ejecutada",
    );
  });

  it("el CTA habilitado no declara un motivo de inhabilitación (P3)", () => {
    renderCard();

    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.getAttribute("aria-disabled")).toBeNull();
    expect(button.getAttribute("aria-describedby")).toBeNull();
  });

  it("cuando el hueco es el de la cadena, el CTA se describe con el hueco visible (P3)", () => {
    renderCard({
      view: view({
        // La cadena de REFERENCIA está incompleta: el hueco visible es `gapReason`.
        instrumentId: null,
        strategyDefinitionId: null,
        strategyLabel: AUTO_OPERATION_STRATEGY_NO_DATA,
        rank: null,
        executedStrategyDefinitionId: null,
        executedStrategyLabel: null,
        executedStrategyRank: null,
        verifyTarget: null,
        verifyGapReason: null,
        verifyHref: null,
        gapReason:
          "Sin dato todavía: no se pudo resolver el instrumento de la operación.",
      }),
    });

    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("aria-describedby")).toBe(
      "auto-operation-strategy-gap",
    );
    expect(
      document.getElementById("auto-operation-strategy-gap")?.textContent,
    ).toContain("no se pudo resolver el instrumento");
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
