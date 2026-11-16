/**
 * R6 — el hook que hace durable el experimento F-D.
 *
 * Un navegador sin `localStorage` debe poder mostrar el experimento guardado en
 * servidor; y si el servidor declara el hueco (`data: null`), el hook **no**
 * fabrica un registro ni escribe nada en la caché.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Mock } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDiaDExperimentTop } from "@/features/backtests/use-dia-d-experiment-top";
import {
  DIA_D_EXPERIMENT_TOP_KEY,
  getDiaDExperimentTop as readLocalDiaDExperimentTop,
} from "@/features/backtests/dia-d-experiment-top";

vi.mock("@/lib/api", () => ({
  api: {
    getDiaDExperimentTop: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const getDiaDExperimentTop = api.getDiaDExperimentTop as unknown as Mock;

const SERVER_ROW = {
  id: "ev-7",
  instrumentId: "inst-1",
  timeframe: "1d",
  asOfDiaD: "2026-09-15",
  savedAt: "2026-11-16T10:00:00+00:00",
  level: "C",
  slots: [
    {
      rank: 1,
      label: "SMA 20/50",
      stars: 4,
      score: 1.2,
      source: "optimized",
      runId: "run-1",
    },
  ],
  coachHeadline: "Del servidor",
};

function Probe({ asOfDiaD }: { asOfDiaD: string | null }) {
  const { record, fromServer, isLoading } = useDiaDExperimentTop({
    instrumentId: "inst-1",
    timeframe: "1d",
    asOfDiaD,
  });
  return (
    <div>
      <span data-testid="slots">
        {record ? record.slots.length : "Sin dato todavía"}
      </span>
      <span data-testid="from-server">{fromServer ? "servidor" : "local"}</span>
      <span data-testid="loading">{isLoading ? "cargando" : "listo"}</span>
    </div>
  );
}

function renderProbe(asOfDiaD: string | null = "2026-09-15") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Probe asOfDiaD={asOfDiaD} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  getDiaDExperimentTop.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("useDiaDExperimentTop", () => {
  it("hydrates a server-only experiment into the local cache", async () => {
    getDiaDExperimentTop.mockResolvedValue({ data: SERVER_ROW });

    renderProbe();

    await waitFor(() =>
      expect(screen.getByTestId("from-server")).toHaveTextContent("servidor"),
    );
    expect(screen.getByTestId("slots")).toHaveTextContent("1");

    const cached = readLocalDiaDExperimentTop("inst-1", "1d", "2026-09-15");
    expect(cached?.coachHeadline).toBe("Del servidor");
    expect(cached?.savedAt).toBe("2026-11-16T10:00:00+00:00");
    expect(cached?.evidenceId).toBe("ev-7");
    expect(localStorage.getItem(DIA_D_EXPERIMENT_TOP_KEY)).toContain('"ev-7"');
  });

  it("declares the gap when the server has no experiment", async () => {
    getDiaDExperimentTop.mockResolvedValue({ data: null });

    renderProbe();

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("listo"),
    );
    expect(screen.getByTestId("slots")).toHaveTextContent("Sin dato todavía");
    expect(screen.getByTestId("from-server")).toHaveTextContent("local");
    // Ni fila inventada ni caché escrita: el hueco se declara.
    expect(localStorage.getItem(DIA_D_EXPERIMENT_TOP_KEY)).toBeNull();
  });

  it("does not query when there is no DÍA D", async () => {
    renderProbe(null);

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("listo"),
    );
    expect(getDiaDExperimentTop).not.toHaveBeenCalled();
    expect(screen.getByTestId("slots")).toHaveTextContent("Sin dato todavía");
  });
});
