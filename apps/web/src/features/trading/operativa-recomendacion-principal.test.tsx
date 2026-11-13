/**
 * S4 · Recomendación principal de la ventana maximizada.
 *
 * Guarda que la única recomendación visible es la del dictamen, que el estado de
 * cartera se declara con las cinco categorías de S3 y que ninguna de las dos se
 * convierte en una orden.
 *
 * @see docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  classifyAsesorCarteraState,
  type AsesorCarteraStateV1,
  type InstrumentDailyOpinionStance,
  type InstrumentDailyOpinionV1,
} from "@bolsa/shared";
import { OperativaRecomendacionPrincipal } from "@/features/trading/operativa-recomendacion-principal";
import { resolveOperativaActionHint } from "@/features/trading/operativa-action-hint";

afterEach(() => cleanup());

function opinion(
  stance: InstrumentDailyOpinionStance,
  overrides: Partial<InstrumentDailyOpinionV1> = {},
): InstrumentDailyOpinionV1 {
  return {
    id: "op-1",
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance,
    dictamenStars: 4,
    ioScore: 72,
    distress: false,
    reasons: [],
    source: "eod_batch",
    engineVersion: "opinion_v1",
    idempotencyKey: "k",
    computedAt: "2026-11-12T18:00:00.000Z",
    createdAt: "2026-11-12T18:00:00.000Z",
    updatedAt: "2026-11-12T18:00:00.000Z",
    ...overrides,
  } as InstrumentDailyOpinionV1;
}

function renderHero(options: {
  opinion: InstrumentDailyOpinionV1 | null;
  hasOpenPosition?: boolean;
  measured?: boolean;
  loading?: boolean;
  gate?: {
    entriesBlocked?: boolean;
    positionMeasured?: boolean;
    studiesMeasured?: boolean;
    hasAccount?: boolean;
  };
}) {
  const measured = options.measured ?? true;
  const hasOpenPosition = options.hasOpenPosition ?? false;
  const carteraState: AsesorCarteraStateV1 = classifyAsesorCarteraState({
    opinion: options.opinion,
    position: { measured, hasOpenPosition },
  });
  const actionHint = resolveOperativaActionHint({
    carteraStateId: carteraState.id,
    hasOpenPosition,
    hasAccount: options.gate?.hasAccount ?? true,
    positionMeasured: options.gate?.positionMeasured ?? measured,
    studiesMeasured: options.gate?.studiesMeasured ?? true,
    canEnqueueConfirm: true,
    entriesBlocked: options.gate?.entriesBlocked ?? false,
    requiresEstudio: false,
    inEstudio: true,
  });

  render(
    <OperativaRecomendacionPrincipal
      symbol="BBVA"
      opinion={options.opinion}
      opinionLoading={options.loading}
      carteraState={carteraState}
      actionHint={actionHint}
    />,
  );

  return { carteraState, actionHint };
}

describe("OperativaRecomendacionPrincipal", () => {
  it("recomendación favorable: titula el dictamen y declara la vía de entrada", () => {
    renderHero({ opinion: opinion("buy", { ioScore: 85 }) });

    const hero = screen.getByTestId("operativa-recomendacion-principal");
    expect(hero.dataset.state).toBe("recomendacion_favorable");
    expect(hero.dataset.actionHint).toBe("entrada_disponible");
    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Recomendación favorable",
    );
    const dictamen = screen.getByTestId("operativa-dictamen");
    expect(dictamen.dataset.variant).toBe("hero");
    expect(dictamen.textContent).toContain("Comprar");
    expect(dictamen.textContent).toContain("Confianza 85 / 100");
  });

  it("posición abierta: conserva la recomendación y separa la salida en ACCIÓN", () => {
    renderHero({
      opinion: opinion("hold_watch", { ioScore: 72 }),
      hasOpenPosition: true,
    });

    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Posición abierta",
    );
    expect(screen.getByTestId("operativa-dictamen").textContent).toContain(
      "Mantener",
    );
    expect(screen.getByTestId("operativa-actuacion").textContent).toContain(
      "Salida en ACCIÓN",
    );
  });

  it("posición sin respaldo: usa la etiqueta de S1 y nunca «sobrecompra»", () => {
    renderHero({
      opinion: opinion("overbought", {
        ioScore: 64,
        reasons: ["top_low", "overbought_or_exit"],
      }),
      hasOpenPosition: true,
    });

    const hero = screen.getByTestId("operativa-recomendacion-principal");
    expect(hero.dataset.state).toBe("posicion_sin_respaldo");
    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Posición sin respaldo",
    );
    const text = hero.textContent ?? "";
    expect(text).toContain("Sin respaldo");
    expect(text).not.toContain("Sobrecomprado");
    expect(text.toLowerCase()).not.toContain("sobrecompra");
    expect(text).not.toMatch(/[a-z]+_[a-z]+/);
  });

  it("datos insuficientes: no inventa posición ni vía de actuación", () => {
    renderHero({ opinion: null, measured: false });

    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Sin datos suficientes",
    );
    expect(
      screen.getByTestId("operativa-recomendacion-principal").dataset.actionHint,
    ).toBe("sin_actuacion");
    expect(screen.getByTestId("operativa-dictamen").textContent).toContain(
      "Sin recomendación todavía",
    );
    expect(
      (screen.getByTestId("operativa-recomendacion-principal").textContent ?? "")
        .toLowerCase(),
    ).not.toContain("sin posición");
  });

  it("entrada bloqueada: declara el motivo sin deshabilitar el cockpit", () => {
    renderHero({
      opinion: opinion("buy", { ioScore: 85 }),
      gate: { entriesBlocked: true },
    });

    const hint = screen.getByText("Entrada bloqueada");
    expect(hint.dataset.blockedReason).toBe("entradas_bloqueadas");
    expect(
      screen.getByTestId("operativa-recomendacion-principal").dataset.actionHint,
    ).toBe("entrada_bloqueada");
  });

  it("mientras mide no afirma categoría de cartera", () => {
    renderHero({ opinion: null, loading: true });

    expect(screen.queryByTestId("operativa-cartera-state")).toBeNull();
    expect(
      screen.getByTestId("operativa-recomendacion-principal").dataset.state,
    ).toBe("midiendo");
    expect(screen.getByTestId("operativa-dictamen").textContent).toContain(
      "Midiendo recomendación",
    );
  });

  it("el hero declara siempre que informa y no ejecuta", () => {
    renderHero({ opinion: opinion("buy", { ioScore: 85 }) });
    const aviso = screen.getByTestId("operativa-recomendacion-aviso");
    expect(aviso.textContent).toContain("no ejecuta");
    expect(aviso.textContent).toContain("Confirm");
    expect(aviso.textContent).toContain("contexto técnico");
  });
});
