/**
 * DÍA-D AUTO — ejecución manual desde la UI (cola durable).
 *
 * Invariantes:
 * - el botón ENCOLA el job y la UI muestra el progreso del MISMO job;
 * - un fallo muestra el motivo y, si había artefacto, lo etiqueta «artefacto anterior»;
 * - un fallo de transporte se declara (no se confunde con «sin artefacto»);
 * - sin cuenta activa el botón no encola.
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

const state = vi.hoisted(() => ({ accountId: "acc-1" as string | null }));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: state.accountId,
    account: state.accountId ? { id: state.accountId } : null,
    isLoading: false,
    accounts: [],
  }),
}));

vi.mock("@/features/auto-monitor/dia-d-evidence-aggregate-panel", () => ({
  DiaDEvidenceAggregatePanel: () => null,
}));
vi.mock("@/features/auto-monitor/paper-evidence-panel", () => ({
  PaperEvidencePanel: () => null,
}));
vi.mock("@/features/auto-monitor/dia-d-auto-feedback-panel", () => ({
  DiaDAutoFeedbackPanel: () => null,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAutoDiaDReplayDays: vi.fn(async () => ({
      readOnly: true,
      days: ["2026-09-30"],
      notes: [],
    })),
    getAutoDiaDReplay: vi.fn(async (day: string) => ({
      available: true,
      readOnly: true,
      day,
      summary: { verdict: "PARTIAL", match: 1, divergent: 0, notMeasured: 0 },
      steps: [],
      oos: null,
      meta: { account: "acc-1" },
      limits: [],
      notes: [],
    })),
    createAutoDiaDReplayJob: vi.fn(async () => ({
      id: "job-1",
      status: "queued",
    })),
    getAutoOpsJob: vi.fn(),
    listAutoOpsJobs: vi.fn(async () => ({ jobs: [], notes: [] })),
  },
}));

import { api } from "@/lib/api";
import { DiaDAutoPanel } from "@/features/auto-monitor/dia-d-auto-panel";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/auto-monitor?mode=dia-d"]}>
        <DiaDAutoPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  state.accountId = "acc-1";
  vi.clearAllMocks();
});

/**
 * El botón arranca deshabilitado hasta que el día por defecto (el primero con
 * artefacto) se resuelve en un efecto. Pulsar antes no encola nada, así que
 * esperamos a que esté habilitado para probar el flujo real.
 */
async function clickRunWhenReady() {
  const run = await screen.findByTestId("dia-d-auto-run");
  await waitFor(() => expect((run as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(run);
}

describe("DiaDAutoPanel — ejecutar DÍA-D ahora", () => {
  it("encola el job y muestra fase/porcentaje del MISMO job", async () => {
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-1",
      kind: "dia_d_replay",
      status: "running",
      day: "2026-09-30",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "replay", done: 5, total: 10, percent: 50 },
      result: {},
      error: null,
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    renderPanel();

    await clickRunWhenReady();

    await waitFor(() =>
      expect(api.createAutoDiaDReplayJob).toHaveBeenCalledWith({
        day: "2026-09-30",
      }),
    );
    await waitFor(() =>
      expect(api.getAutoOpsJob).toHaveBeenCalledWith("job-1"),
    );

    const progress = await screen.findByTestId("dia-d-auto-job-progress");
    expect(progress.getAttribute("data-phase")).toBe("replay");
    expect(progress.textContent).toContain("Fase replay");
    expect(progress.textContent).toContain("50%");
    expect(
      screen.getByTestId("dia-d-auto-job-status").getAttribute("data-status"),
    ).toBe("running");
  });

  it("un fallo muestra el motivo y conserva el artefacto anterior etiquetado", async () => {
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-1",
      kind: "dia_d_replay",
      status: "failed",
      day: "2026-09-30",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "replay", percent: 40 },
      result: {},
      error: "El replay DÍA-D falló (exit 2): boom",
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    renderPanel();

    await clickRunWhenReady();

    const error = await screen.findByTestId("dia-d-auto-job-error");
    expect(error.getAttribute("role")).toBe("alert");
    expect(error.textContent).toContain("exit 2");

    const stale = await screen.findByTestId("dia-d-auto-stale-artifact");
    expect(stale.textContent).toContain("2026-09-30");
    // El artefacto anterior sigue visible (no se sustituye por un vacío).
    expect(screen.getByTestId("dia-d-auto-steps")).toBeTruthy();
  });

  it("declara el fallo de transporte sin confundirlo con «sin artefacto»", async () => {
    vi.mocked(api.getAutoOpsJob).mockRejectedValue(new Error("api caída"));

    renderPanel();
    await clickRunWhenReady();

    const transport = await screen.findByTestId(
      "dia-d-auto-job-transport-error",
    );
    expect(transport.getAttribute("role")).toBe("alert");
    expect(transport.textContent).toContain("api caída");
  });

  it("rehidrata un job durable ya lanzado (recarga / otra pestaña)", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValueOnce({
      jobs: [
        {
          id: "job-9",
          kind: "dia_d_replay",
          status: "running",
          day: "2026-09-30",
          accountId: "acc-1",
          payload: {},
          progress: { phase: "loading_bars", percent: 20 },
          result: {},
          error: null,
          attempt: 1,
          createdAt: null,
          startedAt: null,
          finishedAt: null,
          heartbeatAt: null,
        },
      ],
      notes: [],
    } as never);
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-9",
      kind: "dia_d_replay",
      status: "running",
      day: "2026-09-30",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "loading_bars", percent: 20 },
      result: {},
      error: null,
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    renderPanel();

    // Sin pulsar el botón: el job ya existía y se observa su progreso.
    const progress = await screen.findByTestId("dia-d-auto-job-progress");
    expect(progress.getAttribute("data-phase")).toBe("loading_bars");
    expect(progress.textContent).toContain("20%");
    expect(api.createAutoDiaDReplayJob).not.toHaveBeenCalled();
    expect(api.getAutoOpsJob).toHaveBeenCalledWith("job-9");
  });

  it("cambiar de cuenta no arrastra el job de la cuenta anterior", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValueOnce({
      jobs: [
        {
          id: "job-acc-1",
          kind: "dia_d_replay",
          status: "running",
          day: "2026-09-30",
          accountId: "acc-1",
          payload: {},
          progress: { phase: "replay", percent: 30 },
          result: {},
          error: null,
          attempt: 1,
          createdAt: null,
          startedAt: null,
          finishedAt: null,
          heartbeatAt: null,
        },
      ],
      notes: [],
    } as never);
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-acc-1",
      kind: "dia_d_replay",
      status: "running",
      day: "2026-09-30",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "replay", percent: 30 },
      result: {},
      error: null,
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    const view = renderPanel();
    await screen.findByTestId("dia-d-auto-job-progress");

    state.accountId = "acc-2";
    view.rerender(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={["/auto-monitor?mode=dia-d"]}>
          <DiaDAutoPanel />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(screen.queryByTestId("dia-d-auto-job-progress")).toBeNull(),
    );
  });

  it("sin cuenta activa no permite encolar", async () => {
    state.accountId = null;
    renderPanel();

    const run = await screen.findByTestId("dia-d-auto-run");
    expect((run as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("dia-d-auto-run-no-account")).toBeTruthy();
  });
});
