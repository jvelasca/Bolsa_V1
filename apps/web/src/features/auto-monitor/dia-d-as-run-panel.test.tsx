/**
 * DÍA-D as-run — regresión del panel (ADR-049).
 *
 * Invariantes clave:
 * 1. un brazo no medido se pinta como hueco con su motivo, nunca como `0`;
 * 2. el benchmark `market_bh` se mide en retorno y jamás se convierte en `0 R`;
 * 3. la certificación del método se ve, y su ausencia/fallo también;
 * 4. la ejecución declarada y los hashes de auditoría se muestran al usuario.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const AUDIT = {
  pointInTime: {
    day: "2026-09-30",
    toDay: "2026-10-18",
    stateSource: "sim_auto_positions",
    sourceIsReconstructed: false,
    legsHash:
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    legs: [
      {
        instrumentId: "AAA",
        direction: "long",
        quantity: 10,
        entry: 100,
        structuralStop: 95,
        target1: 110,
        target2: null,
      },
    ],
    candidateAsOf: "2026-09-30",
  },
  data: {
    barsSource: "postgres:ohlcv_bars",
    timeframe: "1d",
    barsHash:
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    instruments: [
      {
        instrument: "AAA",
        bars: 12,
        firstBar: "2026-10-01",
        lastBar: "2026-10-18",
      },
    ],
  },
  versions: {
    engine: "dia-d-as-run-v2",
    schema: "DiaDAsRunArtifactV2",
    bump: "2.11.189-beta",
    strategy: null,
    mandate: null,
    paramsHash:
      "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  },
  execution: {
    commissionBps: 10,
    slippageBps: 5,
    spreadBps: 2,
    roundTripBps: 32,
    executionCostBps: 22,
    maxParticipationPct: 0.1,
    gapPolicy: "open",
    realFillsCostBasis: "quoted" as const,
  },
  decisions: { as_run: [] },
  limits: ["Método DESCRIPTIVO, no causal"],
};

function payload(day: string) {
  return {
    available: true,
    readOnly: true,
    day,
    status: "measured",
    schemaVersion: "DiaDAsRunArtifactV2",
    costBps: 32,
    startingState: { legs: 1, instruments: ["AAA"], cashOnly: false },
    arms: [
      {
        arm: "as_run",
        measured: true,
        reason: null,
        realizedR: 1.25,
        pnlCurrency: 100,
        maeR: -0.4,
        mfeR: 2,
        capture: 0.62,
        returnPct: 1.5,
        exits: 1,
        stops: 0,
        targets: 1,
        legs: 1,
        reasonCodes: [],
        decisions: [],
      },
      {
        arm: "candidate",
        measured: false,
        reason: "candidate_not_provided",
        realizedR: null,
        pnlCurrency: null,
        maeR: null,
        mfeR: null,
        capture: null,
        returnPct: null,
        exits: 0,
        stops: 0,
        targets: 0,
        legs: 0,
        reasonCodes: [],
        decisions: [],
      },
      {
        arm: "market_bh",
        measured: true,
        reason: null,
        realizedR: null,
        pnlCurrency: null,
        maeR: null,
        mfeR: null,
        capture: null,
        returnPct: 2.4,
        exits: 1,
        stops: 0,
        targets: 0,
        legs: 1,
        reasonCodes: ["benchmark_return_only"],
        decisions: [],
      },
    ],
    gaps: [{ arm: "candidate", reason: "candidate_not_provided" }],
    hash: "0123456789abcdef",
    artifactModifiedAt: "2026-10-18T20:00:00+00:00",
    meta: { bump: "2.11.189-beta" },
    notes: [],
    audit: AUDIT,
    certification: {
      version: "DiaDCertificationV1",
      verdict: "certified",
      certified: true,
      checks: [{ name: "temporal_freeze", status: "PASS", reason: null }],
      failures: [],
      notEvaluated: [],
      reasons: [],
      hash: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    },
  };
}

vi.mock("@/lib/api", () => ({
  api: {
    getAutoDiaDAsRunDays: vi.fn(async () => ({
      readOnly: true,
      days: ["2026-09-30", "2026-09-29"],
      notes: [],
    })),
    getAutoDiaDAsRun: vi.fn(async (day: string) => payload(day)),
    createAutoDiaDAsRunJob: vi.fn(async () => ({
      id: "job-9",
      kind: "dia_d_as_run",
      status: "queued",
      day: "2026-09-30",
      created: true,
    })),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    account: { id: "acc-1" },
    effectiveAccountId: "acc-1",
    isLoading: false,
    accounts: [],
    isError: false,
    refetch: () => {},
  }),
}));

import { api } from "@/lib/api";
import { DiaDAsRunPanel } from "@/features/auto-monitor/dia-d-as-run-panel";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/auto-monitor?mode=as-run"]}>
        <DiaDAsRunPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DiaDAsRunPanel", () => {
  it("pinta los brazos y declara el hueco sin convertirlo en 0", async () => {
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("as-run-artifact")).toBeTruthy(),
    );

    expect(screen.getByTestId("as-run-status").textContent).toBe("MEDIDO");
    expect(screen.getByTestId("as-run-arm-as_run").textContent).toContain(
      "1.25",
    );
    const candidate = screen.getByTestId("as-run-arm-candidate");
    expect(candidate.textContent).toContain("candidate_not_provided");
    expect(candidate.textContent).not.toMatch(/\b0 R\b/);
    expect(screen.getByTestId("as-run-gaps").textContent).toContain(
      "candidate_not_provided",
    );
    expect(api.getAutoDiaDAsRun).toHaveBeenCalledWith("2026-09-30");
  });

  it("pinta la certificación del método y no autoriza nada", async () => {
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("as-run-certification")).toBeTruthy(),
    );

    expect(screen.getByTestId("as-run-certification").textContent).toBe(
      "MÉTODO CERTIFICADO",
    );
    // No hay botón de activación: este panel solo mide.
    expect(screen.queryByText(/activar/i)).toBeNull();
  });

  it("muestra el benchmark de mercado en retorno, nunca en R", async () => {
    renderPanel();

    const benchmark = await screen.findByTestId("as-run-arm-market_bh");
    expect(benchmark.textContent).toContain("2.4 %");
    expect(benchmark.textContent).not.toMatch(/\b0 R\b/);
    expect(benchmark.textContent).not.toContain("benchmark_return_only");
  });

  it("muestra la ejecución declarada y los hashes de auditoría", async () => {
    renderPanel();

    const execution = await screen.findByTestId("as-run-execution");
    expect(execution.textContent).toContain("10 bps");
    expect(execution.textContent).toContain("5 bps");
    expect(execution.textContent).toContain("10 % del volumen");
    expect(execution.textContent).toContain("open");

    const audit = screen.getByTestId("as-run-audit");
    expect(audit.textContent).toContain("aaaaaaaaaa");
    expect(audit.textContent).toContain("bbbbbbbbbb");
    expect(audit.textContent).toContain("dia-d-as-run-v2");
    expect(audit.textContent).toContain("(real)");
  });

  it("declara el fallo de certificación con su motivo", async () => {
    vi.mocked(api.getAutoDiaDAsRun).mockResolvedValueOnce({
      ...payload("2026-09-30"),
      certification: {
        version: "DiaDCertificationV1",
        verdict: "not_certified",
        certified: false,
        checks: [{ name: "benchmarks", status: "FAIL", reason: null }],
        failures: ["benchmarks"],
        notEvaluated: [],
        reasons: ["benchmarks:benchmark_not_measured:market_bh"],
        hash: "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      },
    } as never);

    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("as-run-certification").textContent).toBe(
        "MÉTODO NO CERTIFICADO",
      ),
    );
    expect(
      screen.getByTestId("as-run-certification-reasons").textContent,
    ).toContain("benchmarks:benchmark_not_measured:market_bh");
  });

  it("permite cambiar de día disponible", async () => {
    renderPanel();

    const select = await screen.findByTestId("as-run-day-select");
    expect((select as HTMLSelectElement).value).toBe("2026-09-30");

    await waitFor(() =>
      expect(api.getAutoDiaDAsRun).toHaveBeenCalledWith("2026-09-30"),
    );

    const option = screen.getByRole("option", {
      name: "2026-09-29",
    }) as HTMLOptionElement;
    option.selected = true;
    fireEvent.change(select, { target: { value: "2026-09-29" } });

    await waitFor(() =>
      expect(api.getAutoDiaDAsRun).toHaveBeenCalledWith("2026-09-29"),
    );
  });

  it("encola el replay y declara el job", async () => {
    renderPanel();

    const input = (await screen.findByTestId(
      "as-run-run-day",
    )) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "2026-09-30" } });

    const button = screen.getByTestId("as-run-run") as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false));
    button.click();

    await waitFor(() =>
      expect(api.createAutoDiaDAsRunJob).toHaveBeenCalledWith({
        day: "2026-09-30",
        to: null,
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("as-run-job").textContent).toContain("job-9"),
    );
  });
});
