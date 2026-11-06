/**
 * P1-01 — Resultados (Mercado): una consulta caída no es «aún no hay sesiones».
 *
 * Falsable: si el bloque vuelve a tratar `data ?? []` como verdad, la frase de
 * vacío reaparece con la API caída y estas pruebas fallan.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OperativaOutcomesBlock } from "@/features/trading/operativa-outcomes";

const listDecisionSessions = vi.fn();
const getDecisionSessionLearningSummary = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    listDecisionSessions: (...args: unknown[]) => listDecisionSessions(...args),
    getDecisionSessionLearningSummary: (...args: unknown[]) =>
      getDecisionSessionLearningSummary(...args),
    closeDecisionSessionOutcome: vi.fn(),
  },
}));

vi.mock("@/stores/alerts-store", () => ({
  useAlertsStore: (selector: (s: { pushToast: () => void }) => unknown) =>
    selector({ pushToast: () => {} }),
}));

function renderBlock() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <OperativaOutcomesBlock
        instrumentId="inst-1"
        accountId="acc-1"
        symbol="SAN"
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Resultados · Learning — error de lectura ≠ sin sesiones", () => {
  it("sesiones caídas declaran «No disponible» y no «Aún no hay sesiones»", async () => {
    listDecisionSessions.mockRejectedValue(new Error("network"));
    getDecisionSessionLearningSummary.mockRejectedValue(new Error("network"));

    renderBlock();

    const absence = await screen.findByTestId("operativa-sessions-absence");
    await waitFor(() => expect(absence).toHaveTextContent("No disponible"));
    expect(screen.queryByText(/Aún no hay sesiones/)).toBeNull();
  });

  it("aprendizaje caído no se disfraza de «Sin resumen aún»", async () => {
    listDecisionSessions.mockResolvedValue({ data: [] });
    getDecisionSessionLearningSummary.mockRejectedValue(new Error("network"));

    renderBlock();

    const absence = await screen.findByTestId("operativa-learning-absence");
    expect(absence).toHaveTextContent("No disponible");
    expect(screen.queryByText(/Sin resumen aún/)).toBeNull();
  });

  it("sin sesiones y con dato leído sí dice «Aún no hay sesiones»", async () => {
    listDecisionSessions.mockResolvedValue({ data: [] });
    getDecisionSessionLearningSummary.mockResolvedValue({ data: null });

    renderBlock();

    expect(await screen.findByText(/Aún no hay sesiones/)).toBeTruthy();
    expect(screen.queryByTestId("operativa-sessions-absence")).toBeNull();
  });
});
