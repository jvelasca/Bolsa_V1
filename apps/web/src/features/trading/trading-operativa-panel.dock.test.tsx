/**
 * Dock minimizado de DECISIÓN — los cinco grupos plegables.
 *
 * Guarda el reparto aprobado: Recomendación (dictamen + cockpit) · Fundamental
 * (rueda FA) · Técnico (rueda TA + análisis técnico + estructura) · Seguimiento
 * del día (parte de seguimiento + enlaces Lab + mandato) · Evidencia (rueda IO +
 * ranking + chips + Aprendizaje + AUTO). Usa la sección real para comprobar que
 * el estado de plegado es el del store.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md § Grupos del dock
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import {
  DEFAULT_OPERATIVA_SECTION_HEIGHTS,
  useTradingLayoutStore,
} from "@/stores/trading-layout-store";

const shared = vi.hoisted(() => ({
  context: null as unknown,
  opinion: null as unknown,
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
  useAlertsStore: (sel: (s: unknown) => unknown) => sel({ pushToast: vi.fn() }),
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
    entriesBlocked: false,
    paperDExecuteEnv: false,
    killOn: false,
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

// ── Bloques hijos: stubs que declaran qué reciben ─────────────────────────
vi.mock("@/features/trading/operativa-cockpit-card", () => ({
  OperativaCockpitCard: () => <div data-testid="cockpit-stub" />,
}));

vi.mock("@/features/trading/operativa-analisis-diario", () => ({
  OperativaAnalisisDiario: ({
    part,
    density,
  }: {
    part?: string;
    density?: string;
  }) => (
    <div data-testid={`analisis-${part ?? "all"}`} data-density={density} />
  ),
}));

vi.mock("@/features/market-structure/market-structure-readout", () => ({
  MarketStructureReadout: ({ density }: { density?: string }) => (
    <div data-testid="estructura-stub" data-density={density} />
  ),
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
  OperativaPulseBlock: ({
    gauges,
    density,
    showRank,
  }: {
    gauges?: readonly string[];
    density?: string;
    showRank?: boolean;
  }) => (
    <div
      data-testid="pulse-stub"
      data-gauges={(gauges ?? []).join(",")}
      data-density={density}
      data-rank={String(showRank ?? true)}
    />
  ),
}));

vi.mock("@/features/trading/operativa-outcomes", () => ({
  OperativaOutcomesBlock: () => <div data-testid="outcomes-stub" />,
}));

vi.mock("@/features/trading/operativa-auto-panel", () => ({
  OperativaAutoPanel: () => <div data-testid="auto-stub" />,
}));

import { TradingOperativaPanel } from "@/features/trading/trading-operativa-panel";

function allSectionsOpen(open: boolean) {
  return {
    recomendacion: open,
    fundamental: open,
    tecnico: open,
    seguimientoDia: open,
    lab: open,
    mandato: open,
    evidencia: open,
    resultados: open,
    auto: open,
  };
}

beforeEach(() => {
  shared.context = {
    instrumentId: "inst-1",
    accountId: "acc-1",
    phase: "descubierto",
    plan: {
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
    },
    showsPlanLevels: false,
    trailing: {
      show: false,
      stopVigente: null,
      stopSugerido: null,
      applied: false,
      label: "↗ Trailing sugerido",
      stopVigenteLabel: "Stop operativo",
      stopSugeridoLabel: "Stop sugerido",
    },
    study: null,
    position: null,
    positionMeasured: true,
    studiesMeasured: true,
    inEstudio: true,
    inConfirmQueue: false,
    orderPendingFill: false,
    submitIntent: null,
    originStudy: null,
    confirmQueueCount: 0,
    studiesTruncated: false,
    loading: false,
    portfolioError: false,
    studiesError: false,
  };
  shared.opinion = {
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance: "hold_watch",
    dictamenStars: 3,
    ioScore: 68,
    distress: false,
    reasons: [],
    source: "eod_batch",
    engineVersion: "opinion_v1",
    idempotencyKey: "k",
    computedAt: "2026-11-12T18:00:00.000Z",
    createdAt: "2026-11-12T18:00:00.000Z",
    updatedAt: "2026-11-12T18:00:00.000Z",
  };

  useTradingLayoutStore.setState({
    operativaMaximized: false,
    operativaSections: allSectionsOpen(true),
    operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
  });
});

afterEach(() => cleanup());

describe("TradingOperativaPanel — dock en cinco grupos", () => {
  it("ordena los cinco grupos con las etiquetas de producto", () => {
    render(<TradingOperativaPanel surface="dock" />);

    const headers = screen
      .getAllByTestId(/^operativa-section-/)
      .map((node) => node.dataset.testid);
    expect(headers).toEqual([
      "operativa-section-recomendacion",
      "operativa-section-fundamental",
      "operativa-section-tecnico",
      "operativa-section-seguimientoDia",
      "operativa-section-evidencia",
    ]);

    const expected = [
      ["operativa-section-recomendacion", "Recomendación"],
      ["operativa-section-fundamental", "Fundamental"],
      ["operativa-section-tecnico", "Técnico"],
      ["operativa-section-seguimientoDia", "Seguimiento del día"],
      ["operativa-section-evidencia", "Evidencia"],
    ] as const;
    for (const [id, label] of expected) {
      const header = screen.getByTestId(id).querySelector("button");
      expect(header?.textContent).toContain(label);
    }
  });

  it("cada grupo declara su variante, su contenido y sin asa de altura", () => {
    render(<TradingOperativaPanel surface="dock" />);

    for (const id of [
      "operativa-section-recomendacion",
      "operativa-section-fundamental",
      "operativa-section-tecnico",
      "operativa-section-seguimientoDia",
      "operativa-section-evidencia",
    ]) {
      const section = screen.getByTestId(id);
      expect(section.dataset.variant).toBe("group");
      expect(section.querySelector('[role="separator"]')).toBeNull();
    }
  });

  it("Recomendación lleva el dictamen y el cockpit; Evidencia no repite el dictamen", () => {
    render(<TradingOperativaPanel surface="dock" />);

    const recomendacion = screen.getByTestId("operativa-section-recomendacion");
    const evidencia = screen.getByTestId("operativa-section-evidencia");

    const dictamenes = screen.getAllByTestId("operativa-dictamen");
    expect(dictamenes).toHaveLength(1);
    expect(dictamenes[0].dataset.density).toBe("dock");
    expect(recomendacion.contains(dictamenes[0])).toBe(true);
    expect(evidencia.contains(dictamenes[0])).toBe(false);

    expect(
      recomendacion.contains(screen.getByTestId("cockpit-stub")),
    ).toBe(true);
  });

  it("Fundamental, Técnico y Evidencia usan una sola rueda cada uno y en su grupo", () => {
    render(<TradingOperativaPanel surface="dock" />);

    const pulses = screen.getAllByTestId("pulse-stub");
    expect(pulses.map((node) => node.dataset.gauges)).toEqual([
      "fa",
      "ta",
      "io",
    ]);
    for (const pulse of pulses) {
      expect(pulse.dataset.density).toBe("dock");
    }

    expect(
      screen
        .getByTestId("operativa-section-fundamental")
        .contains(screen.getAllByTestId("pulse-stub")[0]!),
    ).toBe(true);
    expect(
      screen
        .getByTestId("operativa-section-tecnico")
        .contains(screen.getAllByTestId("pulse-stub")[1]!),
    ).toBe(true);
    expect(
      screen
        .getByTestId("operativa-section-evidencia")
        .contains(screen.getAllByTestId("pulse-stub")[2]!),
    ).toBe(true);

    // Solo Evidencia conserva el ranking «El n de N en Estudio».
    expect(screen.getAllByTestId("pulse-stub").map((n) => n.dataset.rank)).toEqual(
      ["false", "false", "true"],
    );
  });

  it("Técnico recibe el parte técnico y la estructura; Seguimiento, el del día y el mandato", () => {
    render(<TradingOperativaPanel surface="dock" />);

    const tecnico = screen.getByTestId("operativa-section-tecnico");
    const seguimiento = screen.getByTestId("operativa-section-seguimientoDia");

    expect(tecnico.contains(screen.getByTestId("analisis-tecnico"))).toBe(true);
    expect(tecnico.contains(screen.getByTestId("estructura-stub"))).toBe(true);
    expect(
      seguimiento.contains(screen.getByTestId("analisis-seguimiento")),
    ).toBe(true);
    expect(seguimiento.contains(screen.getByTestId("mandate-stub"))).toBe(true);
    expect(
      seguimiento.contains(screen.getByText("Abrir estudio (LAB)")),
    ).toBe(true);

    expect(screen.queryByTestId("analisis-all")).toBeNull();
  });

  it("Evidencia reúne el avance técnico, el aprendizaje y AUTO", () => {
    render(<TradingOperativaPanel surface="dock" />);

    const evidencia = screen.getByTestId("operativa-section-evidencia");
    expect(evidencia.contains(screen.getByTestId("chips-stub"))).toBe(true);
    expect(evidencia.contains(screen.getByTestId("outcomes-stub"))).toBe(true);
    expect(evidencia.contains(screen.getByTestId("auto-stub"))).toBe(true);
  });
});

describe("TradingOperativaPanel — dock con el estado guardado por defecto", () => {
  it("solo Recomendación arranca abierta", () => {
    useTradingLayoutStore.setState({
      operativaSections: {
        recomendacion: true,
        fundamental: false,
        tecnico: false,
        seguimientoDia: false,
        lab: false,
        mandato: false,
        evidencia: false,
        resultados: false,
        auto: false,
      },
    });

    render(<TradingOperativaPanel surface="dock" />);

    for (const id of [
      "operativa-section-recomendacion",
      "operativa-section-fundamental",
      "operativa-section-tecnico",
      "operativa-section-seguimientoDia",
      "operativa-section-evidencia",
    ]) {
      const header = screen
        .getByTestId(id)
        .querySelector("button") as HTMLButtonElement;
      expect(header.getAttribute("aria-expanded")).toBe(
        id === "operativa-section-recomendacion" ? "true" : "false",
      );
    }

    expect(screen.getByTestId("cockpit-stub")).toBeTruthy();
    expect(screen.queryByTestId("pulse-stub")).toBeNull();
  });
});
