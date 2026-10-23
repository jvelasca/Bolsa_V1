/**
 * `useDiaDValueReplayJob` — rehidratación y aislamiento por (cuenta, día, símbolo).
 *
 * Invariantes:
 * - al montar se adopta el job durable del día SOLO si su `payload.symbol` es el pedido;
 * - el job de otro símbolo no se pinta (la cola serializa; el otro valor no es este);
 * - cambiar de cuenta/día/símbolo limpia el job observado;
 * - encolar devuelve el job correcto una sola vez y el de otro símbolo se declara ocupado.
 */

import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const state = vi.hoisted(() => ({ accountId: "acc-1" as string | null }));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: state.accountId,
    account: state.accountId ? { id: state.accountId } : null,
    isLoading: false,
    accounts: [],
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listAutoOpsJobs: vi.fn(async () => ({ jobs: [], notes: [] })),
    getAutoOpsJob: vi.fn(),
    createAutoDiaDValueReplayJob: vi.fn(),
  },
}));

import { api } from "@/lib/api";
import { useDiaDValueReplayJob } from "@/features/auto-monitor/use-dia-d-value-replay";

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    kind: "dia_d_value_replay",
    status: "running",
    day: "2026-10-16",
    accountId: "acc-1",
    payload: { symbol: "AAA" },
    progress: {},
    result: {},
    error: null,
    attempt: 1,
    createdAt: null,
    startedAt: null,
    finishedAt: null,
    heartbeatAt: null,
    ...overrides,
  };
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function render(
  day: string | null = "2026-10-16",
  symbol: string | null = "AAA",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = renderHook(
    ({ d, s }: { d: string | null; s: string | null }) =>
      useDiaDValueReplayJob(d, s),
    { wrapper: wrapper(client), initialProps: { d: day, s: symbol } },
  );
  return view;
}

beforeEach(() => {
  state.accountId = "acc-1";
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("useDiaDValueReplayJob", () => {
  it("rehidrata el job durable del MISMO símbolo al montar", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValue({
      jobs: [job()],
      notes: [],
    } as never);
    vi.mocked(api.getAutoOpsJob).mockResolvedValue(job() as never);

    const { result } = render();

    await waitFor(() => expect(result.current.job?.id).toBe("job-1"));
    expect(api.getAutoOpsJob).toHaveBeenCalledWith("job-1");
    expect(api.createAutoDiaDValueReplayJob).not.toHaveBeenCalled();
    expect(result.current.isRunning).toBe(true);
  });

  it("no adopta el job de otro símbolo del mismo día", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValue({
      jobs: [job({ id: "job-other", payload: { symbol: "BBB" } })],
      notes: [],
    } as never);

    const { result } = render("2026-10-16", "AAA");

    await waitFor(() => expect(api.listAutoOpsJobs).toHaveBeenCalled());
    expect(result.current.job).toBeNull();
    expect(api.getAutoOpsJob).not.toHaveBeenCalled();
  });

  it("cambiar de cuenta o de símbolo limpia el job observado", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValue({
      jobs: [job()],
      notes: [],
    } as never);
    vi.mocked(api.getAutoOpsJob).mockResolvedValue(job() as never);

    const { result, rerender } = render();
    await waitFor(() => expect(result.current.job?.id).toBe("job-1"));

    state.accountId = "acc-2";
    rerender({ d: "2026-10-16", s: "AAA" });

    await waitFor(() => expect(result.current.job).toBeNull());
    expect(api.listAutoOpsJobs).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "dia_d_value_replay",
        day: "2026-10-16",
      }),
    );
  });

  it("encola el símbolo pedido una sola vez y declara el job de otro valor", async () => {
    vi.mocked(api.createAutoDiaDValueReplayJob).mockResolvedValue(
      job({ id: "job-other", payload: { symbol: "BBB" } }) as never,
    );

    const { result } = render();

    result.current.run();

    await waitFor(() => expect(result.current.occupiedBy).toBe("BBB"));
    expect(api.createAutoDiaDValueReplayJob).toHaveBeenCalledTimes(1);
    expect(api.createAutoDiaDValueReplayJob).toHaveBeenCalledWith({
      day: "2026-10-16",
      symbol: "AAA",
    });
    // No se pinta el job ajeno como si fuera la verificación de este valor.
    expect(result.current.job).toBeNull();
  });

  it("sin cuenta no consulta ni encola", async () => {
    state.accountId = null;
    const { result } = render();

    expect(result.current.hasAccount).toBe(false);
    expect(api.listAutoOpsJobs).not.toHaveBeenCalled();
    result.current.run();
    expect(api.createAutoDiaDValueReplayJob).not.toHaveBeenCalled();
  });

  it("usa la verdad de servidor: slot.matchesRequest decide, no el payload", async () => {
    vi.mocked(api.createAutoDiaDValueReplayJob).mockResolvedValue(
      job({
        id: "job-other",
        payload: { symbol: "BBB" },
        slot: {
          state: "active_other_symbol",
          activeJobId: "job-other",
          activeSymbol: "BBB",
          requestedSymbol: "AAA",
          matchesRequest: false,
          startedAt: "2026-10-16T09:00:00Z",
          message:
            "Verificación en curso para BBB (job job-other, iniciada 2026-10-16T09:00:00Z). La cola admite una por cuenta y día; AAA queda pendiente.",
        },
      }) as never,
    );

    const { result } = render();
    result.current.run();

    await waitFor(() => expect(result.current.occupiedBy).toBe("BBB"));
    expect(result.current.slot?.state).toBe("active_other_symbol");
    expect(result.current.slotMessage).toContain("BBB");
    expect(result.current.job).toBeNull();
  });

  it("un slot con matchesRequest adopta el job aunque el payload no coincida", async () => {
    vi.mocked(api.createAutoDiaDValueReplayJob).mockResolvedValue(
      job({
        id: "job-mine",
        payload: { symbol: "aaa" },
        slot: {
          state: "active_same_request",
          activeJobId: "job-mine",
          activeSymbol: "AAA",
          requestedSymbol: "AAA",
          matchesRequest: true,
          startedAt: "2026-10-16T09:00:00Z",
          message: "Verificación ya en curso para AAA (job job-mine).",
        },
      }) as never,
    );
    vi.mocked(api.getAutoOpsJob).mockResolvedValue(
      job({ id: "job-mine", payload: { symbol: "aaa" } }) as never,
    );

    const { result } = render();
    result.current.run();

    await waitFor(() => expect(result.current.job?.id).toBe("job-mine"));
    expect(result.current.occupiedBy).toBeNull();
    expect(result.current.slot?.matchesRequest).toBe(true);
  });
});
