/**
 * Gate unitario `heading-order` (deuda axe UI 6.x) — corre en `vitest` (Frontend CI), NO opt-in.
 *
 * La regla `heading-order` de axe exige que el nivel de encabezado no suba más de 1 respecto al
 * anterior. En las páginas L1 (`<h1>` + cards) el primer bloque anidaba un `CardTitle` (h3) y
 * saltaba `h2`. Este gate monta las páginas afectadas y comprueba, sobre el orden documental:
 *
 *   1. exactamente un `<h1>` por página;
 *   2. ningún salto de nivel (`level[i] - level[i-1] <= 1`);
 *   3. el primer encabezado es `h1`.
 *
 * `HEADING_GUARD` es la guarda de lista: para cubrir una página nueva hay que añadirla aquí de
 * forma explícita. Si un bloque no se puede montar en jsdom (p. ej. `/backtests`, cuyo modelo de
 * página compone el hub entero), se documenta en `HEADING_GUARD_EXCLUDED` y queda cubierto por el
 * barrido axe E2E `gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`.
 *
 * Reutiliza el patrón de los tests de página existentes: `MemoryRouter` + hooks de red/hook de
 * cuenta mockeados (no se levanta backend).
 */

import type { ReactElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { InvestmentAccountDto } from "@bolsa/shared";

// ---------------------------------------------------------------------------
// Mocks comunes (red + cuenta). `@tanstack/react-query` se sustituye por un stub
// determinista: las páginas de encabezados no necesitan datos reales para pintar
// su jerarquía, y así el gate es síncrono y no depende de la carrera de queries.
// ---------------------------------------------------------------------------

const queryState = vi.hoisted(() => ({
  byKey: {} as Record<string, unknown>,
}));

vi.mock("@tanstack/react-query", () => {
  const result = (opts: { queryKey?: readonly unknown[] }) => {
    const key = Array.isArray(opts?.queryKey) ? String(opts.queryKey[0]) : "";
    const data = queryState.byKey[key];
    return {
      data,
      isLoading: false,
      isPending: false,
      isError: false,
      isFetching: false,
      isSuccess: data !== undefined,
      refetch: () => {},
    };
  };
  return {
    useQuery: (opts: { queryKey?: readonly unknown[] }) => result(opts),
    useInfiniteQuery: () => result({}),
    useQueries: () => [],
    useMutation: () => ({
      mutate: () => {},
      mutateAsync: () => Promise.resolve(undefined),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      data: undefined,
      reset: () => {},
    }),
    useQueryClient: () => ({
      invalidateQueries: () => Promise.resolve(),
      setQueryData: () => {},
      getQueryData: () => undefined,
      removeQueries: () => {},
    }),
    QueryClient: class QueryClientStub {},
    QueryClientProvider: ({ children }: { children: ReactElement }) => children,
  };
});

vi.mock("@/lib/api", () => {
  const ok = async () => ({ data: undefined, meta: {} });
  return {
    api: new Proxy({}, { get: () => ok }),
    ApiError: class ApiError extends Error {},
  };
});

vi.mock("@/features/accounts/use-active-account", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/features/accounts/use-active-account")
    >();
  const { defaultAccountSettings } = await import("@bolsa/shared");
  const settings = defaultAccountSettings();
  const account: InvestmentAccountDto = {
    id: "acc-a11y",
    userId: "user-a11y",
    name: "Demo A11y",
    description: null,
    type: "simulated",
    status: "active",
    currency: "EUR",
    baseCurrency: "EUR",
    initialDeposit: 100_000,
    leverage: 1,
    marginCallLevelPct: null,
    isDefault: true,
    settings: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    lastActivityAt: null,
  };
  return {
    ...actual,
    useActiveAccount: () => ({
      account,
      effectiveAccountId: account.id,
      isLoading: false,
      accounts: [account],
    }),
    useActiveAccountSettings: () => ({
      settings,
      currency: "EUR",
      accountName: account.name,
      effectiveAccountId: account.id,
      isLoading: false,
    }),
    useActivateAccount: () => ({
      mutate: () => {},
      mutateAsync: () => Promise.resolve(undefined),
      isPending: false,
      isError: false,
      error: null,
      data: undefined,
      reset: () => {},
    }),
  };
});

// Operational Console: se mockean SOLO los hooks de datos; las secciones reales se
// renderizan (el encabezado `h2` que arreglamos vive en `OpsReconSection`).
vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({
    data: {
      schemaVersion: "1.0.0",
      rule: "gate-unit",
      accountId: "acc-a11y",
      lookbackDays: 120,
      lanes: {
        semi: {
          mark: "UNAVAILABLE",
          confirmSeed: null,
          journalSeed: null,
          buysSeed: null,
          tradeLike: null,
        },
        auto: {
          mark: "UNAVAILABLE",
          paperDExecuteEnv: false,
          executeOptIn: false,
          strictAcceptReady: false,
          p1: { mark: "UNAVAILABLE", need: 0 },
          p2: { mark: "UNAVAILABLE", need: 0 },
          p3: { mark: "UNAVAILABLE", need: 0 },
          p4: { mark: "UNAVAILABLE", need: 0 },
          p5: {
            mark: "UNAVAILABLE",
            need: 0,
            tradeLike: null,
            cashMaxDdFrac: null,
            note: null,
          },
        },
      },
      portfolioReconciliation: { status: "ok" },
      operationalReadiness: {
        state: "PAPER_READY",
        venue: "paper",
        reasons: [],
        notes: [],
        rule: "gate-unit",
      },
    },
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: () => {},
  }),
  portfolioReconStatusFromReport: () => "clean",
}));

vi.mock("@/features/operational-console/use-estudio-auto-telemetry", () => ({
  useEstudioAutoTelemetry: () => ({
    data: { data: null },
    isLoading: false,
    isError: false,
    refetch: () => {},
  }),
}));

vi.mock("@/features/operational-console/use-lifecycle-outbox-stats", () => ({
  useLifecycleOutboxStats: () => ({
    data: {
      pending: 0,
      processing: 0,
      dead: 0,
      oldestPendingAgeSeconds: null,
      oldestProcessingAgeSeconds: null,
      oldestDeadAgeSeconds: null,
      slaBreached: false,
      operationalState: "OK",
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/operational-console/use-lifecycle-reconciliation", () => ({
  useLifecycleReconciliation: () => ({
    data: {
      accountId: "acc-a11y",
      status: "clean",
      checked: 0,
      driftCount: 0,
      lagCount: 0,
      blockedCount: 0,
      issues: [],
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/operational-console/use-financial-integrity", () => ({
  useFinancialIntegrity: () => ({
    data: {
      accountId: "acc-a11y",
      status: "clean",
      operationalState: "OK",
      portfolioStatus: "clean",
      lifecycle: {
        accountId: "acc-a11y",
        status: "clean",
        checked: 0,
        driftCount: 0,
        lagCount: 0,
        blockedCount: 0,
        issues: [],
      },
      fillLinkIssues: [],
      outboxDead: 0,
      slaBreached: false,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/operational-console/auto-evidence-section", () => ({
  OpsAutoEvidenceSection: () => null,
}));

// Imports DESPUÉS de los `vi.mock` (comportamiento estándar de Vitest).
import { OverviewPage } from "@/features/dashboard/dashboard-page";
import { AccountsPage } from "@/features/accounts/accounts-page";
import { AlertsPage } from "@/features/alerts/alerts-page";
import { TaxReportPage } from "@/features/fiscal/tax-report-page";
import { OperationalConsolePage } from "@/features/operational-console/operational-console-page";
import { AutoMonitorPage } from "@/features/auto-monitor/auto-monitor-page";
import { ScreenersPage } from "@/features/screeners/screeners-page";
import { InstrumentDetailPage } from "@/features/instruments/instrument-detail-page";

afterEach(cleanup);

function levelOf(element: HTMLElement): number {
  const match = /^h([1-6])$/.exec(element.tagName.toLowerCase());
  if (match) return Number(match[1]);
  const aria = element.getAttribute("aria-level");
  return aria ? Number(aria) : 2;
}

/** Asierta la jerarquía documental completa (h1 único · sin saltos · arranca en h1). */
function assertHeadingOrder(path: string) {
  const headings = screen.queryAllByRole("heading") as HTMLElement[];
  const sequence = headings.map((h) => ({
    level: levelOf(h),
    tag: h.tagName.toLowerCase(),
    text: (h.textContent ?? "").trim().slice(0, 48),
  }));

  const h1Count = sequence.filter((item) => item.level === 1).length;
  expect(
    h1Count,
    `[${path}] debe haber exactamente un <h1> · secuencia=${JSON.stringify(sequence)}`,
  ).toBe(1);

  expect(
    sequence[0]?.level,
    `[${path}] el primer encabezado debe ser h1 · secuencia=${JSON.stringify(sequence)}`,
  ).toBe(1);

  const jumps: string[] = [];
  for (let i = 1; i < sequence.length; i += 1) {
    const prev = sequence[i - 1]!;
    const cur = sequence[i]!;
    if (cur.level - prev.level > 1) {
      jumps.push(`${prev.tag}("${prev.text}") → ${cur.tag}("${cur.text}")`);
    }
  }
  expect(
    jumps,
    `[${path}] saltos de nivel de encabezado · secuencia=${JSON.stringify(sequence)}`,
  ).toEqual([]);
}

/**
 * Guarda de lista: rutas/páginas objetivo. Añadir una página al gate es explícito.
 * `render` monta la página con sus providers mínimos.
 */
const HEADING_GUARD: readonly {
  path: string;
  render: () => void;
}[] = [
  {
    path: "/overview",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/overview"]}>
          <OverviewPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/accounts",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/accounts"]}>
          <AccountsPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/alerts",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/alerts"]}>
          <AlertsPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/fiscal",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/fiscal"]}>
          <TaxReportPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/operational-console",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/operational-console"]}>
          <OperationalConsolePage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/auto-monitor?mode=operation",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/auto-monitor?mode=operation"]}>
          <AutoMonitorPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/auto-monitor?mode=current",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/auto-monitor?mode=current"]}>
          <AutoMonitorPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/screeners",
    render: () =>
      render(
        <MemoryRouter initialEntries={["/screeners"]}>
          <ScreenersPage />
        </MemoryRouter>,
      ),
  },
  {
    path: "/instruments/:id",
    render: () => {
      // La página exige instrumento cargado (`isLoading`/`!instrument` → rama sin encabezados).
      queryState.byKey.instrument = {
        data: {
          id: "AAPL",
          symbol: "AAPL",
          name: "Apple E2E",
          exchange: "NASDAQ",
          yahooSymbol: "AAPL",
          currency: "USD",
        },
        meta: {
          priceSummary: { lastClose: 102, changePct: 2, barCount: 30 },
          lastSync: { status: "ok", barsAdded: 5 },
        },
      };
      render(
        <MemoryRouter initialEntries={["/instruments/AAPL"]}>
          <Routes>
            <Route path="/instruments/:id" element={<InstrumentDetailPage />} />
          </Routes>
        </MemoryRouter>,
      );
    },
  },
];

/**
 * Páginas del censo que NO se montan aquí (se declaran para que la exclusión sea explícita).
 * `/backtests` compone el modelo de página entero (asistente + jobs + DÍA-D + keep-alive) y
 * queda cubierto por el barrido axe E2E, donde sí se añade a `ROUTES`.
 */
const HEADING_GUARD_EXCLUDED: readonly { path: string; reason: string }[] = [
  {
    path: "/backtests",
    reason:
      "BacktestsPage compone el modelo de página completo (useBacktestPageModel) fuera del alcance del montaje unitario; se cubre en el barrido axe E2E (gp-e2e-ui5-0-axe-touched-routes-mock).",
  },
];

describe("heading-order — jerarquía h1→h2→h3 sin saltos", () => {
  it("la guarda de lista no deja rutas del censo sin cubrir ni excluir", () => {
    const covered = new Set(HEADING_GUARD.map((entry) => entry.path));
    const excluded = new Set(HEADING_GUARD_EXCLUDED.map((entry) => entry.path));
    for (const entry of [...HEADING_GUARD, ...HEADING_GUARD_EXCLUDED]) {
      expect(covered.has(entry.path) || excluded.has(entry.path)).toBe(true);
    }
    // Ninguna ruta puede estar cubierta y excluida a la vez.
    for (const path of covered) expect(excluded.has(path)).toBe(false);
  });

  for (const entry of HEADING_GUARD) {
    it(`${entry.path} — sin saltos de nivel`, () => {
      entry.render();
      assertHeadingOrder(entry.path);
    });
  }
});
