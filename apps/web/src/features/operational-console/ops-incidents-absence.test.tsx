/**
 * P1-01 — Consola: «Sin incidentes activos» solo si la consulta se leyó.
 *
 * Falsable: quitar el `!isError` del vacío hace reaparecer la frase con la API
 * caída, y esta prueba falla.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { OpsIncidentsSection } from "@/features/operational-console/ops-incidents-and-links";

const getActiveOperationalIncidents = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getActiveOperationalIncidents: (...args: unknown[]) =>
      getActiveOperationalIncidents(...args),
  },
}));

function renderSection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OpsIncidentsSection accountId="acc-1" onManageIncident={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Consola · Incidentes activos", () => {
  it("con la consulta caída no afirma «Sin incidentes activos»", async () => {
    getActiveOperationalIncidents.mockRejectedValue(new Error("network"));

    renderSection();

    expect(
      await screen.findByText(/No se pudieron cargar incidentes/),
    ).toBeTruthy();
    expect(screen.queryByTestId("ops-incidents-empty")).toBeNull();
  });

  it("con la consulta leída y vacía sí declara «Sin incidentes activos»", async () => {
    getActiveOperationalIncidents.mockResolvedValue({
      data: { incidents: [] },
    });

    renderSection();

    expect(await screen.findByTestId("ops-incidents-empty")).toBeTruthy();
  });
});
