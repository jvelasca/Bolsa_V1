/**
 * S3 · Cartera del Asesor — guardas de UI.
 *
 * Lo que debe morder:
 *   - las cinco categorías se ven con su nombre de producto, no con su clave;
 *   - los filtros por estado y «solo con posición» no mienten;
 *   - «Cartera sin medir» ≠ «Sin posición» y «Sin dictamen» se declara;
 *   - no existe CTA de compra/firma en esta pestaña: solo «Ver en Mercado»;
 *   - ninguna etiqueta de primer nivel filtra una clave `snake_case`.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MemoryRouter } from "react-router-dom";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MARKET_STRUCTURE_DEFAULTS,
  MARKET_STRUCTURE_METHOD_ID,
  MARKET_STRUCTURE_METHOD_VERSION,
  buildAsesorCarteraRow,
  type AsesorCarteraRowV1,
  type AsesorCarteraSummaryV1,
  type AsesorCarteraStateIdV1,
  type DecisionJournalStudyViewV1,
  type InstrumentDailyOpinionV1,
  type MarketLevelV1,
  type MarketStructureResultV1,
  type OperationalPlanViewV1,
  type PositionDto,
} from "@bolsa/shared";
import {
  findFirstLevelDashes,
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const focusInstrumentInMercado = vi.fn();

vi.mock("@/features/trading/focus-instrument-in-mercado", () => ({
  focusInstrumentInMercado: (...args: unknown[]) =>
    focusInstrumentInMercado(...args),
}));

let mockData = mockCarteraData([]);

vi.mock("@/features/research/use-asesor-cartera-data", () => ({
  useAsesorCarteraData: () => mockData,
}));

const { AsesorCarteraPanel } = await import("./asesor-cartera-panel");

afterEach(() => cleanup());
beforeEach(() => {
  focusInstrumentInMercado.mockClear();
});

// ── Fixtures ────────────────────────────────────────────────────────────────

function opinion(
  stance: InstrumentDailyOpinionV1["stance"],
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
  };
}

function position(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "pos-1",
    instrumentId: "inst-1",
    symbol: "AAA",
    name: "AAA SA",
    quantity: 100,
    avgCost: 10,
    lastPrice: 10.5,
    marketValue: 1050,
    unrealizedPnl: 50,
    unrealizedPnlPct: 5,
    ...overrides,
  };
}

function plan(): OperationalPlanViewV1 {
  return {
    phase: "vigilar",
    phaseLabel: "Vigilar",
    direction: "long",
    entry: 10.6,
    stopVigente: 10.1,
    stopInicial: 10.1,
    target1: 11.2,
    target2: 12,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: 1.6,
    riskR: null,
    currentPrice: 10.5,
    unrealizedR: null,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: true,
    emptyCopy: "Sin plan",
  } as OperationalPlanViewV1;
}

function rowFor(
  state: AsesorCarteraStateIdV1,
  symbol: string,
): AsesorCarteraRowV1 {
  const base = {
    instrumentId: `inst-${symbol}`,
    symbol,
    name: `${symbol} SA`,
    quote: { price: 10.5, changePct: -1.4 },
    study: null,
    structure: null,
    phase: "vigilar" as const,
    plan: plan(),
    markPrice: 10.5,
  };

  switch (state) {
    case "recomendacion_favorable":
      return buildAsesorCarteraRow({
        ...base,
        opinion: opinion("buy", { ioScore: 84 }),
        position: null,
        portfolioMeasured: true,
      });
    case "evaluado_sin_oportunidad":
      return buildAsesorCarteraRow({
        ...base,
        opinion: opinion("hold_watch", { ioScore: 55 }),
        position: null,
        portfolioMeasured: true,
      });
    case "posicion_abierta":
      return buildAsesorCarteraRow({
        ...base,
        opinion: opinion("hold_watch", { ioScore: 61 }),
        position: position({ instrumentId: `inst-${symbol}`, symbol }),
        portfolioMeasured: true,
      });
    case "posicion_sin_respaldo":
      return buildAsesorCarteraRow({
        ...base,
        opinion: opinion("overbought", { ioScore: 40 }),
        position: position({ instrumentId: `inst-${symbol}`, symbol }),
        portfolioMeasured: true,
      });
    case "sin_datos":
      return buildAsesorCarteraRow({
        ...base,
        opinion: null,
        position: null,
        portfolioMeasured: false,
      });
  }
}

function summaryFor(rows: AsesorCarteraRowV1[]): AsesorCarteraSummaryV1 {
  const byState = {
    recomendacion_favorable: 0,
    evaluado_sin_oportunidad: 0,
    posicion_abierta: 0,
    posicion_sin_respaldo: 0,
    sin_datos: 0,
  } satisfies Record<AsesorCarteraStateIdV1, number>;
  for (const row of rows) byState[row.state.id] += 1;
  return {
    total: rows.length,
    byState,
    withPosition: rows.filter((row) => row.position.hasOpenPosition).length,
    unmeasured: rows.filter((row) => !row.position.measured).length,
    withGaps: rows.filter((row) => row.gaps.length > 0).length,
  };
}

function mockCarteraData(rows: AsesorCarteraRowV1[]) {
  return {
    rows,
    summary: summaryFor(rows),
    universe: rows.map((row) => ({
      instrumentId: row.instrumentId,
      symbol: row.symbol,
      name: row.name,
    })),
    loading: false,
    enriching: false,
    quotesLoading: false,
    opinionsLoading: false,
    barsLoading: false,
    portfolioMeasured: rows.every((row) => row.position.measured),
    portfolioError: false,
    studiesError: false,
    studiesTruncated: false,
    quotesError: false,
    barsError: false,
    barsFailedIds: [],
    barsMissingIds: [],
    empty: rows.length === 0,
  };
}

const ALL_ROWS = [
  rowFor("recomendacion_favorable", "AAA"),
  rowFor("evaluado_sin_oportunidad", "BBB"),
  rowFor("posicion_abierta", "CCC"),
  rowFor("posicion_sin_respaldo", "DDD"),
  rowFor("sin_datos", "EEE"),
];

function renderPanel() {
  return render(
    <MemoryRouter>
      <AsesorCarteraPanel />
    </MemoryRouter>,
  );
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe("AsesorCarteraPanel · las cinco categorías", () => {
  it("pinta una fila por estado con su etiqueta de producto", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    const rows = screen.getAllByTestId("asesor-cartera-row");
    expect(rows).toHaveLength(5);
    expect(rows.map((row) => row.getAttribute("data-state"))).toEqual([
      "posicion_sin_respaldo",
      "recomendacion_favorable",
      "posicion_abierta",
      "evaluado_sin_oportunidad",
      "sin_datos",
    ]);

    expect(
      screen.getByTestId("asesor-cartera-state-posicion_sin_respaldo"),
    ).toHaveTextContent("Posición sin respaldo");
    expect(
      screen.getByTestId("asesor-cartera-state-recomendacion_favorable"),
    ).toHaveTextContent("Recomendación favorable");
    expect(
      screen.getByTestId("asesor-cartera-state-posicion_abierta"),
    ).toHaveTextContent("Posición abierta");
    expect(
      screen.getByTestId("asesor-cartera-state-evaluado_sin_oportunidad"),
    ).toHaveTextContent("Sin oportunidad");
    expect(
      screen.getByTestId("asesor-cartera-state-sin_datos"),
    ).toHaveTextContent("Sin datos suficientes");
  });

  it("la cabecera declara que la lista no combina señales", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();
    expect(
      screen.getByText(/no combina señales ni autoriza compras/i),
    ).toBeInTheDocument();
  });

  it("«Cartera sin medir» y «Sin dictamen» se declaran, no se inventan", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();
    const row = screen
      .getByTestId("asesor-cartera-state-sin_datos")
      .closest("tr")!;
    const text = row.textContent ?? "";
    expect(text).toContain("Cartera sin medir");
    expect(text).toContain("Sin dictamen");
    expect(text).not.toContain("Sin posición");
  });

  it("con posición publica cantidad, coste y P&L", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();
    const row = screen
      .getByTestId("asesor-cartera-state-posicion_abierta")
      .closest("tr")!;
    expect(row.textContent).toContain("100 uds");
    expect(row.textContent).toContain("P&L +5,00 %");
  });
});

describe("AsesorCarteraPanel · filtros", () => {
  it("filtra por estado", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    fireEvent.click(
      screen.getByTestId("asesor-cartera-filter-posicion_sin_respaldo"),
    );
    const rows = screen.getAllByTestId("asesor-cartera-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]!.getAttribute("data-symbol")).toBe("DDD");
  });

  it("«solo con posición» deja únicamente posiciones abiertas", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    const checkbox = screen.getByTestId(
      "asesor-cartera-only-position",
    ) as HTMLInputElement;
    fireEvent.click(checkbox);

    const symbols = screen
      .getAllByTestId("asesor-cartera-row")
      .map((row) => row.getAttribute("data-symbol"));
    expect(symbols.sort()).toEqual(["CCC", "DDD"]);
  });

  it("un filtro vacío lo dice en vez de fingir una tabla", () => {
    mockData = mockCarteraData([rowFor("evaluado_sin_oportunidad", "BBB")]);
    renderPanel();
    fireEvent.click(screen.getByTestId("asesor-cartera-filter-sin_datos"));
    expect(screen.getByText("Ningún valor en este filtro.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("asesor-cartera-row")).toHaveLength(0);
  });
});

describe("AsesorCarteraPanel · la lista no opera", () => {
  it("no hay CTA de compra ni de firma", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    expect(
      screen.queryAllByRole("button", { name: /comprar|firmar/i }),
    ).toHaveLength(0);
    expect(
      screen.queryAllByRole("link", { name: /comprar|firmar/i }),
    ).toHaveLength(0);
    expect(screen.queryByText(/firmar compra/i)).not.toBeInTheDocument();
  });

  it("«Ver en Mercado» abre el valor y no firma nada", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    fireEvent.click(screen.getByTestId("asesor-cartera-open-AAA"));
    expect(focusInstrumentInMercado).toHaveBeenCalledTimes(1);
    const hit = focusInstrumentInMercado.mock.calls[0]![2] as {
      instrumentId: string;
      symbol: string;
    };
    expect(hit).toEqual({ instrumentId: "inst-AAA", symbol: "AAA" });
  });

  it("la recomendación visible es la del dictamen", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    const buy = screen
      .getByTestId("asesor-cartera-state-recomendacion_favorable")
      .closest("tr")!;
    expect(buy.textContent).toContain("Comprar");

    const hold = screen
      .getByTestId("asesor-cartera-state-evaluado_sin_oportunidad")
      .closest("tr")!;
    expect(hold.textContent).toContain("Mantener");
  });
});

describe("AsesorCarteraPanel · vocabulario", () => {
  it("ninguna celda de primer nivel filtra una clave snake_case", () => {
    mockData = mockCarteraData(ALL_ROWS);
    const { container } = renderPanel();
    const clone = container.cloneNode(true) as HTMLElement;
    for (const detail of Array.from(
      clone.querySelectorAll("[data-technical-detail]"),
    )) {
      detail.remove();
    }
    expect(clone.textContent ?? "").not.toMatch(/[a-z]+_[a-z]+/);
  });

  it("el detalle técnico declara la procedencia y los huecos", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    const detalle = screen.getByTestId("asesor-cartera-detalle-EEE");
    const text = detalle.textContent ?? "";
    expect(text).toContain("Dictamen");
    expect(text).toContain("Estructura del gráfico");
    expect(text).toContain("Huecos declarados");
    expect(text).toContain("Cartera sin medir");
  });
});

describe("AsesorCarteraPanel · valores publicados y ausencia declarada", () => {
  function studyFixture(
    overrides: Partial<DecisionJournalStudyViewV1> = {},
  ): DecisionJournalStudyViewV1 {
    return {
      opinion: "bullish",
      strength: 7.5,
      strengthBand: "strong",
      vigencia: "current",
      direction: "long",
      hasOperationalPlan: false,
      decisionSummary: null,
      expectedRR: 1.8,
      riskAmount: 120,
      nextReviewAt: "2026-11-13T08:00:00.000Z",
      consensus: { bullish: 4, bearish: 1, neutral: 2, total: 7 },
      invalidation: ["Cierre bajo 9,80"],
      trends: [
        {
          key: "short_term",
          label: "Corto plazo",
          value: "bullish",
          display: "Alcista",
        },
        {
          key: "background",
          label: "Fondo",
          value: "bearish",
          display: "Bajista",
        },
      ],
      indicators: { primary: "ADX 28", confirmation: "SMA 20/50" },
      ...overrides,
    } as unknown as DecisionJournalStudyViewV1;
  }

  function levelFixture(
    kind: MarketLevelV1["kind"],
    price: number,
    distancePct: number,
  ): MarketLevelV1 {
    return {
      kind,
      price,
      zoneLow: price - 0.05,
      zoneHigh: price + 0.05,
      touches: 3,
      state: "detectado",
      reasons: [],
      pivots: [],
      lastTouchAt: "2026-11-01T00:00:00.000Z",
      distancePct,
      distanceAtr: 0.5,
    };
  }

  function structureFixture(): MarketStructureResultV1 {
    return {
      methodId: MARKET_STRUCTURE_METHOD_ID,
      methodVersion: MARKET_STRUCTURE_METHOD_VERSION,
      params: { ...MARKET_STRUCTURE_DEFAULTS },
      window: {
        from: "2026-01-01T00:00:00.000Z",
        to: "2026-11-12T00:00:00.000Z",
        bars: 220,
        timeframe: "1d",
      },
      inputSignature: "deadbeef",
      status: "ok",
      reasons: [],
      atrRef: 0.4,
      close: 10.5,
      supports: [levelFixture("support", 9.8, -6.7)],
      resistances: [levelFixture("resistance", 11.2, 6.7)],
      structure: { id: "ascendente", tolerance: 0.2, highs: [], lows: [] },
      lastBarMayBeOpen: true,
    };
  }

  function richRow(
    overrides: {
      quote?: {
        price: number | null;
        changePct: number | null;
        lastBarDate?: string | null;
        expectedLastBarDate?: string | null;
        freshness?: "ok" | "stale" | "unknown" | null;
      };
      study?: DecisionJournalStudyViewV1 | null;
    } = {},
  ): AsesorCarteraRowV1 {
    return buildAsesorCarteraRow({
      instrumentId: "inst-AAA",
      symbol: "AAA",
      name: "AAA SA",
      quote: overrides.quote ?? { price: 10.5, changePct: 1.2 },
      opinion: opinion("hold_watch", { ioScore: 61, dictamenStars: 4 }),
      study: overrides.study === undefined ? studyFixture() : overrides.study,
      structure: structureFixture(),
      phase: "vigilar",
      plan: plan(),
      position: null,
      portfolioMeasured: true,
      markPrice: 10.5,
    });
  }

  it("publica cierre, distancias y estructura en la celda de niveles", () => {
    mockData = mockCarteraData([richRow()]);
    renderPanel();

    const row = screen.getByTestId("asesor-cartera-row");
    expect(row.textContent).toContain("9,80");
    expect(row.textContent).toContain("-6,70 %");
    expect(row.textContent).toContain("11,20");
    expect(row.textContent).toContain("+6,70 %");
    expect(row.textContent).toContain("Estructura ascendente");
  });

  it("la fuerza lleva barra accesible además del número", () => {
    mockData = mockCarteraData([richRow()]);
    renderPanel();

    const row = screen.getByTestId("asesor-cartera-row");
    expect(row.textContent).toContain("Fuerza 7,5 / 10");
    const bar = screen
      .getAllByRole("img")
      .find((node) => (node.getAttribute("aria-label") ?? "").includes("Fuerza"));
    expect(bar).toBeDefined();
    expect(bar?.getAttribute("aria-label")).toContain("Fuerza 7,5 / 10");
  });

  it("declara el cierre desactualizado con su fecha", () => {
    mockData = mockCarteraData([
      richRow({
        quote: {
          price: 10.5,
          changePct: 1.2,
          lastBarDate: "2026-11-10",
          expectedLastBarDate: "2026-11-12",
          freshness: "stale",
        },
      }),
    ]);
    renderPanel();

    expect(screen.getByTestId("asesor-cartera-stale")).toHaveTextContent(
      "1 valor con el cierre desactualizado",
    );
    const row = screen.getByTestId("asesor-cartera-row");
    expect(row.textContent).toContain("Cierre desactualizado");
    expect(row.textContent).toContain("2026-11-10");
  });

  it("mientras cargan las velas dice «Midiendo…», no un hueco medido", () => {
    const row = rowFor("evaluado_sin_oportunidad", "BBB");
    mockData = {
      ...mockCarteraData([row]),
      barsLoading: true,
    };
    renderPanel();

    expect(screen.getByTestId("asesor-cartera-row").textContent).toContain(
      "Midiendo…",
    );
  });

  it("con precio de cartera y cotizaciones cargando declara la fuente y el cierre en medición", () => {
    const row = buildAsesorCarteraRow({
      instrumentId: "inst-CCC",
      symbol: "CCC",
      name: "CCC SA",
      quote: { price: 10.5, changePct: -1.4, source: "cartera" },
      opinion: opinion("hold_watch", { ioScore: 61 }),
      study: null,
      structure: null,
      phase: "vigilar",
      plan: plan(),
      position: position({ instrumentId: "inst-CCC", symbol: "CCC" }),
      portfolioMeasured: true,
      markPrice: 10.5,
    });
    mockData = { ...mockCarteraData([row]), quotesLoading: true };
    renderPanel();

    const source = screen.getByTestId("asesor-cartera-price-source-CCC");
    expect(source).toHaveTextContent("Precio de cartera · Midiendo cierre…");
    // No se inventa una fecha de cierre mientras el lote no ha llegado.
    expect(screen.getByTestId("asesor-cartera-row").textContent).not.toContain(
      "Cierre 20",
    );
  });

  it("sin precio y con cotizaciones cargando dice «Midiendo cotizaciones…»", () => {
    const row = buildAsesorCarteraRow({
      instrumentId: "inst-DDD",
      symbol: "DDD",
      name: "DDD SA",
      quote: { price: null, changePct: null, source: null },
      opinion: opinion("hold_watch", { ioScore: 61 }),
      study: null,
      structure: null,
      phase: "vigilar",
      plan: plan(),
      position: null,
      portfolioMeasured: true,
      markPrice: null,
    });
    mockData = { ...mockCarteraData([row]), quotesLoading: true };
    renderPanel();

    expect(screen.getByTestId("asesor-cartera-row").textContent).toContain(
      "Midiendo cotizaciones…",
    );
  });

  it("mientras llegan los dictámenes dice «Midiendo…» y no «Sin dictamen»", () => {
    const row = rowFor("sin_datos", "EEE");
    mockData = { ...mockCarteraData([row]), opinionsLoading: true };
    renderPanel();

    const recommendation = screen.getByTestId(
      "asesor-cartera-recommendation-EEE",
    );
    expect(recommendation).toHaveTextContent("Midiendo…");
    expect(recommendation).not.toHaveTextContent("Sin dictamen");

    const trend = screen.getByTestId("asesor-cartera-trend-EEE");
    expect(trend).toHaveTextContent("Midiendo…");
    expect(trend).not.toHaveTextContent("Sin dato de tendencia");
  });

  it("la cabecera declara los valores sin medir", () => {
    mockData = mockCarteraData(ALL_ROWS);
    renderPanel();

    expect(screen.getByTestId("asesor-cartera-totals").textContent).toContain(
      "1 sin medir",
    );
  });

  it("muestra la tendencia de corto y de fondo en líneas distintas", () => {
    mockData = mockCarteraData([richRow()]);
    renderPanel();

    const row = screen.getByTestId("asesor-cartera-row");
    expect(row.textContent).toContain("Alcista");
    expect(row.textContent).toContain("Fondo: Bajista");
  });

  it("el detalle técnico declara scores, veredicto y consenso", () => {
    mockData = mockCarteraData([richRow()]);
    renderPanel();

    const detail = screen.getByTestId("asesor-cartera-detalle-AAA").textContent ??
      "";
    expect(detail).toContain("Componentes: IO 61 · FA sin medir · TA sin medir");
    expect(detail).toContain("Consenso: 4 alcistas · 1 bajistas · 2 neutras");
    expect(detail).toContain("R/R esperado");
    expect(detail).toContain("Cierre bajo 9,80");
  });
});

describe("asesor-cartera-panel.tsx · gate de primer nivel", () => {
  const source = readFileSync(resolve(__dirname, "asesor-cartera-panel.tsx"), "utf8");

  it("no usa jerga prohibida fuera del detalle técnico", () => {
    expect(findFirstLevelViolations(source)).toEqual([]);
  });

  it("no usa disclosures paralelos ni el comodín de dato ausente", () => {
    expect(source).not.toContain("<details");
    expect(source).not.toContain("<summary");
    expect(findFirstLevelDashes(source)).toEqual([]);
  });

  it("no colapsa un hueco a 0", () => {
    expect(stripTechnicalDetailBlocks(source)).not.toMatch(/\?\?\s*0(?![.\d])/);
  });

  it("no promete una compra automática", () => {
    expect(source.toLowerCase()).not.toContain("comprar ahora");
    expect(source.toLowerCase()).not.toContain("señal de compra agregada");
  });
});
