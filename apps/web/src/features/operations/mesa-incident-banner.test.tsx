import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OperationalIncidentV1 } from "@bolsa/shared";
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";

vi.mock("@/lib/api", () => ({
  api: {
    getActiveOperationalIncidents: vi.fn(),
    resolveOperationalIncident: vi.fn(),
    clearOperationalIncident: vi.fn(),
  },
}));

import { api } from "@/lib/api";

function makeIncident(
  overrides: Partial<OperationalIncidentV1> = {},
): OperationalIncidentV1 {
  return {
    incidentId: "inc-1",
    accountId: "acc-1",
    kind: "portfolio_drift",
    status: "open",
    snapshot: "portfolio_drift",
    openedAt: "2026-08-26T10:00:00Z",
    reviewedAt: null,
    reviewedBy: null,
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    clearedAt: null,
    ...overrides,
  };
}

function renderBanner(
  props: { accountId?: string; portfolioReconStatus?: string | null } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MesaIncidentBanner
        accountId={props.accountId ?? "acc-1"}
        portfolioReconStatus={props.portfolioReconStatus ?? "drift"}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("MesaIncidentBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: { accountId: "acc-1", incidents: [], total: 0 },
    } as never);
  });

  it("oculto sin incidentes activos", async () => {
    renderBanner();
    await waitFor(() =>
      expect(api.getActiveOperationalIncidents).toHaveBeenCalledWith("acc-1"),
    );
    expect(screen.queryByTestId("mesa-incident-banner")).toBeNull();
  });

  it("muestra copy cuando hay incidente activo", async () => {
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: {
        accountId: "acc-1",
        incidents: [makeIncident()],
        total: 1,
      },
    } as never);
    renderBanner();
    const banner = await screen.findByTestId("mesa-incident-banner");
    expect(banner.textContent).toMatch(/Incidente operacional/i);
    expect(banner.textContent).toMatch(/Sin auto-heal/i);
    expect(banner.textContent).toMatch(/Deriva portfolio/i);
  });

  it("resolve exige nota y clear disabled hasta resolved+clean", async () => {
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: {
        accountId: "acc-1",
        incidents: [makeIncident()],
        total: 1,
      },
    } as never);
    renderBanner({ portfolioReconStatus: "drift" });
    fireEvent.click(await screen.findByTestId("mesa-incident-manage"));
    expect(await screen.findByTestId("mesa-incident-panel")).toBeTruthy();
    expect(screen.getByTestId("mesa-incident-clear")).toBeDisabled();

    fireEvent.click(screen.getByTestId("mesa-incident-resolve"));
    expect(await screen.findByTestId("mesa-incident-error")).toBeTruthy();

    fireEvent.change(screen.getByTestId("mesa-incident-note"), {
      target: { value: "top-up manual verificado" },
    });
    vi.mocked(api.resolveOperationalIncident).mockResolvedValue({
      data: makeIncident({
        status: "resolved",
        resolutionNote: "top-up manual verificado",
      }),
    } as never);
    fireEvent.click(screen.getByTestId("mesa-incident-resolve"));
    await waitFor(() =>
      expect(api.resolveOperationalIncident).toHaveBeenCalledWith(
        "acc-1",
        "inc-1",
        { resolutionNote: "top-up manual verificado" },
      ),
    );
  });

  it("clear habilitado cuando resolved y recon ok", async () => {
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: {
        accountId: "acc-1",
        incidents: [makeIncident({ status: "resolved", resolutionNote: "ok" })],
        total: 1,
      },
    } as never);
    renderBanner({ portfolioReconStatus: "ok" });
    fireEvent.click(await screen.findByTestId("mesa-incident-manage"));
    const clearBtn = screen.getByTestId("mesa-incident-clear");
    expect(clearBtn).not.toBeDisabled();
    vi.mocked(api.clearOperationalIncident).mockResolvedValue({
      data: makeIncident({ status: "cleared" }),
    } as never);
    fireEvent.click(clearBtn);
    await waitFor(() =>
      expect(api.clearOperationalIncident).toHaveBeenCalledWith(
        "acc-1",
        "inc-1",
      ),
    );
  });
});
