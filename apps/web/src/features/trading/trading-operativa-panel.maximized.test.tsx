/**
 * S4 · Composición de la ventana maximizada de DECISIÓN.
 *
 * Guarda las tres superficies: `maximized` antepone la recomendación principal y
 * deja **un solo** dictamen; `narrow` conserva la composición anterior (dictamen
 * dentro de Evidencia); `dock` reparte el contenido en los cinco grupos
 * plegables y mueve el dictamen a Recomendación. Ninguna monta el hero salvo la
 * maximizada.
 *
 * @see docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { marketStanceLabel } from "@bolsa/shared";
import type {
  InstrumentDailyOpinionV1,
  OperationalPlanViewV1,
} from "@bolsa/shared";

const shared = vi.hoisted(() => ({
  context: null as unknown,
  opinion: null as unknown,
  /** S5 — el mock de bloqueo de entradas es mutable por escenario. */
  entriesBlocked: false,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    isSuccess: true,
    refetch: vi.fn(),
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }: { to: string; children: ReactNode }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
  useNavigate: () => vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getPortfolio: vi.fn(),
    getInstruments: vi.fn(),
    getInstrumentStrategyTop: vi.fn(),
    getStrategy: vi.fn(),
  },
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: (sel: (s: unknown) => unknown) =>
    sel({
      workspace: {
        charts: [
          {
            id: "chart-1",
            instrumentId: "inst-1",
            label: "BBVA",
            timeframe: "1d",
          },
        ],
        activeChartId: "chart-1",
      },
    }),
}));

vi.mock("@/stores/estudio-membership-store", () => ({
  useEstudioMembershipStore: (sel: (s: unknown) => unknown) =>
    sel({
      members: [{ instrumentId: "inst-1" }],
      contains: () => true,
      upsertMembers: vi.fn(),
    }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (sel: (s: unknown) => unknown) =>
    sel({ items: [], enqueue: () => "q1", setActive: vi.fn() }),
}));

vi.mock("@/stores/alerts-store", () => ({
  useAlertsStore: (sel: (s: unknown) => unknown) =>
    sel({ pushToast: vi.fn() }),
}));

vi.mock("@/stores/dia-d-trading-session-store", () => ({
  useDiaDTradingSessionStore: (sel: (s: unknown) => unknown) =>
    sel({ enterSession: vi.fn() }),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/stores/active-account-store", () => ({
  useActiveAccountQueryKey: () => ["account", "acc-1"],
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({
    entriesBlocked: shared.entriesBlocked,
    paperDExecuteEnv: false,
    killOn: shared.entriesBlocked,
    vetoed: 0,
    incidentCount: 0,
    incidentsFailed: false,
  }),
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: "semi" }),
}));

vi.mock("@/features/trading/demo-book-prefs", () => ({
  demoBookAllowsEnqueueConfirm: () => true,
  demoBookRequiresEstudioMembership: () => false,
}));

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
}));

vi.mock("@/features/platform/operating-mandate-sync", () => ({
  ensureMandateHydrated: vi.fn(),
}));

vi.mock("@/features/platform/product-universe", () => ({
  diaDVerifyHref: () => "/backtests/verify",
  VERIFY_DIA_D_CTA: "Verificar D→hoy",
}));

vi.mock("@/features/platform/strategy-adoption", () => ({
  STRATEGY_ADOPTION_LABELS: {},
  getAdoptionState: () => "none",
}));

vi.mock("@/features/backtests/instrument-strategy-top-panel", () => ({
  instrumentTopBacktestsHref: () => "/backtests",
  readRecommendationReasons: () => [],
}));

vi.mock("@/features/backtests/finalists-stability-summary", () => ({
  finalistsStabilityWarnTitle: () => null,
  formatFinalistsStabilityBadge: () => null,
  readLabEvidenceFromCoachFacts: () => ({}),
}));

vi.mock("@/features/backtests/dia-d-experiment-top", () => ({
  getDiaDExperimentTop1: () => null,
}));

vi.mock("@/features/instruments/use-instruments-hub-scores", () => ({
  useInstrumentsHubScores: () => ({
    faByInstrument: new Map(),
    taByInstrument: new Map(),
    scoresLoading: false,
  }),
}));

vi.mock("@/features/trading/use-operativa-study-actions", () => ({
  useRefreshStudyAction: () => ({
    refreshPending: false,
    refreshStudy: vi.fn(),
  }),
  useAddToEstudioAction: () => ({
    addToEstudioPending: false,
    addToEstudio: vi.fn(),
  }),
}));

vi.mock("@/features/trading/use-decision-package-chips", () => ({
  useDecisionPackageChips: () => ({ action: null, fit: null }),
}));

vi.mock("@/features/trading/propose-instrument-supervised", () => ({
  proposeInstrumentSupervised: vi.fn(),
}));

vi.mock("@/features/confirm/daily-nav", () => ({
  formatFueraUniversoOperativaCopy: () => "Fuera de Estudio",
}));

vi.mock("@/features/trading/use-instrument-operational-context", () => ({
  useInstrumentOperationalContext: () => shared.context,
}));

vi.mock("@/features/trading/use-instrument-daily-opinions", () => ({
  useInstrumentDailyOpinions: () => ({
    data: shared.opinion ? [shared.opinion] : [],
    isLoading: false,
  }),
}));

// ── Bloques hijos: stubs para aislar la composición del panel ──────────────
vi.mock("@/features/trading/operativa-cockpit-card", () => ({
  OperativaCockpitCard: () => <div data-testid="cockpit-stub" />,
}));

vi.mock("@/features/trading/operativa-analisis-diario", () => ({
  OperativaAnalisisDiario: () => <div data-testid="analisis-diario-stub" />,
}));

vi.mock("@/features/market-structure/market-structure-readout", () => ({
  MarketStructureReadout: () => <div data-testid="estructura-stub" />,
}));

vi.mock("@/features/trading/trading-operativa-section", () => ({
  TradingOperativaSection: ({
    sectionId,
    children,
  }: {
    sectionId: string;
    children: ReactNode;
  }) => <section data-testid={`operativa-section-${sectionId}`}>{children}</section>,
}));

vi.mock("@/features/trading/mandate-timeline-panel", () => ({
  MandateTimelinePanel: () => <div data-testid="mandate-stub" />,
}));

vi.mock("@/features/help/mesa-tip-button", () => ({
  MesaTipButton: () => null,
}));

vi.mock("@/features/trading/decision-package-chips-bar", () => ({
  DecisionPackageChipsBar: () => <div data-testid="chips-stub" />,
}));

vi.mock("@/features/trading/operativa-pulse", () => ({
  OperativaPulseBlock: () => <div data-testid="pulse-stub" />,
}));

vi.mock("@/features/trading/operativa-outcomes", () => ({
  OperativaOutcomesBlock: () => <div data-testid="outcomes-stub" />,
}));

vi.mock("@/features/trading/operativa-auto-panel", () => ({
  OperativaAutoPanel: () => <div data-testid="auto-stub" />,
}));

import { TradingOperativaPanel } from "@/features/trading/trading-operativa-panel";

function plan(): OperationalPlanViewV1 {
  return {
    phase: "descubierto",
    phaseLabel: "Descubierto",
    direction: "long",
    entry: null,
    stopVigente: null,
    stopInicial: null,
    target1: null,
    target2: null,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: null,
    riskR: null,
    currentPrice: null,
    unrealizedR: null,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: false,
    emptyCopy: "Sin plan operativo",
  };
}

function context(overrides: Record<string, unknown> = {}) {
  return {
    instrumentId: "inst-1",
    accountId: "acc-1",
    phase: "descubierto",
    plan: plan(),
    showsPlanLevels: false,
    trailing: {
      show: false,
      stopVigente: null,
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

function opinion(
  overrides: Partial<InstrumentDailyOpinionV1> = {},
): InstrumentDailyOpinionV1 {
  return {
    id: "op-1",
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance: "buy",
    dictamenStars: 4,
    ioScore: 85,
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

function renderPanel(surface: "dock" | "maximized" | "narrow") {
  return render(
    <TradingOperativaPanel
      surface={surface}
      maximized={surface !== "dock"}
    />,
  );
}

beforeEach(() => {
  shared.context = context();
  shared.opinion = opinion();
  shared.entriesBlocked = false;
});

afterEach(() => cleanup());

describe("TradingOperativaPanel — superficie maximizada", () => {
  it("monta el hero y un único dictamen, con el orden de lectura declarado", () => {
    renderPanel("maximized");

    const panel = screen.getByTestId("trading-operativa-panel");
    expect(panel.dataset.surface).toBe("maximized");

    const hero = screen.getByTestId("operativa-recomendacion-principal");
    const accion = screen.getByTestId("operativa-col-accion");
    const contexto = screen.getByTestId("operativa-contexto-tecnico");
    const seguimiento = screen.getByTestId("operativa-seguimiento");

    const order = [hero, accion, contexto, seguimiento];
    for (let i = 0; i < order.length - 1; i += 1) {
      const relation = order[i].compareDocumentPosition(order[i + 1]);
      expect(
        relation & Node.DOCUMENT_POSITION_FOLLOWING,
        `${order[i].dataset.testid ?? order[i].className} debe ir antes`,
      ).toBeTruthy();
    }

    const dictamenes = screen.getAllByTestId("operativa-dictamen");
    expect(dictamenes).toHaveLength(1);
    expect(hero.contains(dictamenes[0])).toBe(true);
    expect(dictamenes[0].dataset.variant).toBe("hero");
  });

  it("ACCIÓN lleva el cockpit; el contexto técnico lleva análisis y estructura", () => {
    renderPanel("maximized");

    expect(
      screen.getByTestId("operativa-col-accion").contains(
        screen.getByTestId("cockpit-stub"),
      ),
    ).toBe(true);

    const contexto = screen.getByTestId("operativa-contexto-tecnico");
    expect(contexto.contains(screen.getByTestId("analisis-diario-stub"))).toBe(
      true,
    );
    expect(contexto.contains(screen.getByTestId("estructura-stub"))).toBe(true);
    expect(contexto.textContent).toContain("Informan; no autorizan entradas");
  });

  it("el hero declara el estado de cartera y la vía de actuación", () => {
    renderPanel("maximized");

    const hero = screen.getByTestId("operativa-recomendacion-principal");
    expect(hero.dataset.state).toBe("recomendacion_favorable");
    expect(hero.dataset.actionHint).toBe("entrada_disponible");
    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Recomendación favorable",
    );
  });

  it("cartera no medida: el hero declara «Sin datos suficientes» y no inventa posición", () => {
    shared.context = context({ positionMeasured: false });
    renderPanel("maximized");

    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Sin datos suficientes",
    );
    expect(
      screen.getByTestId("operativa-recomendacion-principal").dataset.actionHint,
    ).toBe("sin_actuacion");
    expect(
      screen.getByTestId("operativa-recomendacion-principal").textContent ?? "",
    ).not.toContain("Sin posición");
  });

  it("posición sin respaldo: la etiqueta de S1 llega al primer nivel", () => {
    shared.context = context({
      phase: "posicion",
      position: {
        id: "pos-1",
        instrumentId: "inst-1",
        quantity: 10,
        avgCost: 100,
        lastPrice: 101,
        unrealizedPnlPct: 1,
      },
    });
    shared.opinion = opinion({ stance: "overbought", ioScore: 61 });
    renderPanel("maximized");

    expect(screen.getByTestId("operativa-cartera-state").textContent).toBe(
      "Posición sin respaldo",
    );
    expect(
      screen.getByTestId("operativa-recomendacion-principal").textContent ?? "",
    ).not.toContain("Sobrecomprado");
  });
});

describe("TradingOperativaPanel — superficies dock y estrecha", () => {
  it("narrow conserva la composición anterior y no monta el hero", () => {
    renderPanel("narrow");

    expect(
      screen.getByTestId("trading-operativa-panel").dataset.surface,
    ).toBe("narrow");
    expect(screen.queryByTestId("operativa-recomendacion-principal")).toBeNull();
    expect(screen.queryByTestId("operativa-contexto-tecnico")).toBeNull();

    const dictamenes = screen.getAllByTestId("operativa-dictamen");
    expect(dictamenes).toHaveLength(1);
    expect(dictamenes[0].dataset.variant).toBe("compact");
    expect(
      screen.getByTestId("operativa-section-evidencia").contains(dictamenes[0]),
    ).toBe(true);
  });

  it("dock reparte el contenido en cinco grupos y mueve el dictamen a Recomendación", () => {
    renderPanel("dock");

    expect(
      screen.getByTestId("trading-operativa-panel").dataset.surface,
    ).toBe("dock");
    expect(screen.queryByTestId("operativa-recomendacion-principal")).toBeNull();

    const orden = screen
      .getAllByTestId(/^operativa-section-/)
      .map((node) => node.dataset.testid);
    expect(orden).toEqual([
      "operativa-section-recomendacion",
      "operativa-section-fundamental",
      "operativa-section-tecnico",
      "operativa-section-seguimientoDia",
      "operativa-section-evidencia",
    ]);

    const dictamenes = screen.getAllByTestId("operativa-dictamen");
    expect(dictamenes).toHaveLength(1);
    expect(dictamenes[0].dataset.variant).toBe("compact");
    expect(dictamenes[0].dataset.density).toBe("dock");
    expect(
      screen
        .getByTestId("operativa-section-recomendacion")
        .contains(dictamenes[0]),
    ).toBe(true);
    expect(
      screen
        .getByTestId("operativa-section-evidencia")
        .contains(dictamenes[0]),
    ).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// S5 · Certificación del rediseño: los seis escenarios de producto
// ─────────────────────────────────────────────────────────────────────────────

function openPosition() {
  return {
    id: "pos-s5-1",
    instrumentId: "inst-1",
    symbol: "BBVA",
    name: "BBVA",
    quantity: 10,
    avgCost: 100,
    lastPrice: 101,
    unrealizedPnlPct: 1,
  };
}

type S5Scenario = {
  id: string;
  name: string;
  setup: () => void;
  state: string;
  stateLabel: string;
  actionHint: string;
  actionLabel: string;
  blockedReason: string | null;
  /** Etiqueta S1 del dictamen, ya traducida. `null` = no hay dictamen. */
  stanceLabel: string | null;
};

const S5_SCENARIOS: readonly S5Scenario[] = [
  {
    id: "favorable_sin_posicion",
    name: "recomendación favorable sin posición",
    setup: () => {},
    state: "recomendacion_favorable",
    stateLabel: "Recomendación favorable",
    actionHint: "entrada_disponible",
    actionLabel: "Entrada disponible",
    blockedReason: null,
    stanceLabel: "Comprar",
  },
  {
    id: "posicion_con_respaldo",
    name: "posición abierta con respaldo",
    setup: () => {
      shared.context = context({ phase: "posicion", position: openPosition() });
      shared.opinion = opinion({ stance: "hold_watch", ioScore: 72 });
    },
    state: "posicion_abierta",
    stateLabel: "Posición abierta",
    actionHint: "salida_en_accion",
    actionLabel: "Salida en ACCIÓN",
    blockedReason: null,
    stanceLabel: "Mantener",
  },
  {
    id: "posicion_sin_respaldo",
    name: "posición sin respaldo",
    setup: () => {
      shared.context = context({ phase: "posicion", position: openPosition() });
      shared.opinion = opinion({ stance: "overbought", ioScore: 61 });
    },
    state: "posicion_sin_respaldo",
    stateLabel: "Posición sin respaldo",
    actionHint: "salida_en_accion",
    actionLabel: "Salida en ACCIÓN",
    blockedReason: null,
    stanceLabel: "Sin respaldo",
  },
  {
    id: "sin_datos",
    name: "sin datos suficientes",
    setup: () => {
      shared.opinion = null;
    },
    state: "sin_datos",
    stateLabel: "Sin datos suficientes",
    actionHint: "sin_actuacion",
    actionLabel: "Sin actuación",
    blockedReason: null,
    stanceLabel: null,
  },
  {
    id: "entrada_bloqueada",
    name: "entrada bloqueada",
    setup: () => {
      shared.entriesBlocked = true;
    },
    state: "recomendacion_favorable",
    stateLabel: "Recomendación favorable",
    actionHint: "entrada_bloqueada",
    actionLabel: "Entrada bloqueada",
    blockedReason: "entradas_bloqueadas",
    stanceLabel: "Comprar",
  },
  {
    id: "salida_con_entradas_bloqueadas",
    name: "salida permitida con entradas bloqueadas",
    setup: () => {
      shared.context = context({ phase: "posicion", position: openPosition() });
      shared.opinion = opinion({ stance: "hold_watch", ioScore: 72 });
      shared.entriesBlocked = true;
    },
    state: "posicion_abierta",
    stateLabel: "Posición abierta",
    actionHint: "salida_en_accion",
    actionLabel: "Salida en ACCIÓN",
    blockedReason: null,
    stanceLabel: "Mantener",
  },
];

describe("S5 · escenarios de producto de la ventana maximizada", () => {
  it.each(S5_SCENARIOS)(
    "$name: recomendación, cartera y vía de actuación son coherentes",
    (scenario) => {
      scenario.setup();
      renderPanel("maximized");

      const hero = screen.getByTestId("operativa-recomendacion-principal");
      expect(hero.dataset.state).toBe(scenario.state);
      expect(hero.dataset.actionHint).toBe(scenario.actionHint);

      const stateChip = screen.getByTestId("operativa-cartera-state");
      expect(stateChip.dataset.state).toBe(scenario.state);
      expect(stateChip.textContent).toBe(scenario.stateLabel);

      const actuacion = screen.getByTestId("operativa-actuacion");
      const hintChip = actuacion.querySelector("[data-action-hint]");
      expect(hintChip?.getAttribute("data-action-hint")).toBe(
        scenario.actionHint,
      );
      expect(hintChip?.textContent).toBe(scenario.actionLabel);
      expect(hintChip?.getAttribute("data-blocked-reason")).toBe(
        scenario.blockedReason,
      );

      // La recomendación visible es la del dictamen (S1), traducida: sin claves
      // internas. Si no hay dictamen, se declara en vez de inventar una postura.
      const dictamen = screen.getByTestId("operativa-dictamen");
      if (scenario.stanceLabel) {
        expect(dictamen.textContent).toContain(scenario.stanceLabel);
        expect(dictamen.textContent).not.toMatch(
          /buy|hold_watch|overbought|sell_exit|reduce|no_trade|review_strategy/,
        );
      } else {
        expect(dictamen.textContent).toContain("Sin recomendación todavía");
      }

      // Un solo dictamen y siempre dentro del hero: sin segunda recomendación.
      const dictamenes = screen.getAllByTestId("operativa-dictamen");
      expect(dictamenes).toHaveLength(1);
      expect(hero.contains(dictamenes[0])).toBe(true);

      // El aviso de alcance es fijo en todas las vías.
      expect(
        screen.getByTestId("operativa-recomendacion-aviso").textContent,
      ).toContain("la recomendación no ejecuta");
    },
  );

  it("la etiqueta de postura coincide con marketStanceLabel (S1)", () => {
    for (const stance of [
      "buy",
      "hold_watch",
      "overbought",
      "reduce",
      "sell_exit",
      "review_strategy",
    ] as const) {
      shared.opinion = opinion({ stance });
      const expected = marketStanceLabel({ stance, reasons: [] }).label;
      const { unmount } = render(
        <TradingOperativaPanel surface="maximized" maximized />,
      );
      expect(
        screen.getByTestId("operativa-dictamen").textContent,
      ).toContain(expected);
      unmount();
    }
  });

  it("sin actuación nunca se lee como «sin posición»", () => {
    shared.context = context({ positionMeasured: false });
    renderPanel("maximized");
    const heroText =
      screen.getByTestId("operativa-recomendacion-principal").textContent ?? "";
    expect(heroText).toContain("Sin datos suficientes");
    expect(heroText).toContain("Sin actuación");
    expect(heroText.toLowerCase()).not.toContain("sin posición");
  });

  it("entrada bloqueada declara el motivo que evalúa canPropose", () => {
    shared.entriesBlocked = true;
    renderPanel("maximized");
    const chip = screen
      .getByTestId("operativa-actuacion")
      .querySelector("[data-blocked-reason]");
    expect(chip?.getAttribute("data-blocked-reason")).toBe(
      "entradas_bloqueadas",
    );
    expect(chip?.textContent).toBe("Entrada bloqueada");
    expect(
      screen.getByTestId("operativa-recomendacion-principal").textContent ?? "",
    ).toContain("Solo se admiten cierres");
  });

  it("la salida sigue disponible aunque las entradas estén bloqueadas", () => {
    shared.context = context({ phase: "posicion", position: openPosition() });
    shared.opinion = opinion({ stance: "hold_watch" });
    shared.entriesBlocked = true;
    renderPanel("maximized");
    const hero = screen.getByTestId("operativa-recomendacion-principal");
    expect(hero.dataset.actionHint).toBe("salida_en_accion");
    expect(
      screen
        .getByTestId("operativa-actuacion")
        .querySelector("[data-blocked-reason]"),
    ).toBeNull();
  });

  it("el contexto técnico informa y no autoriza en todos los escenarios", () => {
    for (const scenario of S5_SCENARIOS) {
      scenario.setup();
      const { unmount } = render(
        <TradingOperativaPanel surface="maximized" maximized />,
      );
      const contexto = screen.getByTestId("operativa-contexto-tecnico");
      expect(contexto.textContent).toContain("Informan; no autorizan entradas");
      unmount();
      shared.context = context();
      shared.opinion = opinion();
      shared.entriesBlocked = false;
    }
  });
});
