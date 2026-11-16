/**
 * R2 — disparador gobernado del embudo desde Finalistas (auditoría LAB 2026-11-16).
 *
 * Test DOM del comportamiento visible del contrato:
 *
 * - `dryRun` arranca ENCENDIDO y se declara (sin escrituras del lifecycle).
 * - El recibo muestra fase, gates y `runId`; `not_evaluated` cae en «Sin dato todavía»
 *   (`UNKNOWN ≠ 0`), nunca en «Cumple» ni en «No cumple».
 * - Un recibo `INCOMPLETE` se rotula como incompleto (fail-closed), con sus motivos.
 * - `promoted`/`activeVersionId` se denuncian como violación de contrato.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BacktestOrchestratorTrigger,
  gateStatusLabel,
} from "@/features/backtests/backtest-orchestrator-trigger";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { runAutoOrchestrator: vi.fn() },
}));

const runAutoOrchestrator = api.runAutoOrchestrator as unknown as ReturnType<
  typeof vi.fn
>;

function receipt(overrides: Record<string, unknown> = {}) {
  return {
    runId: "trigger:abc123",
    instrumentId: "inst-1",
    accountId: "acc-1",
    dryRun: true,
    status: "COMPLETED",
    phaseReached: "finalista",
    cycle: "2026-11-16",
    idempotencyKey: "INST-1|acc-1|-|2026-11-16|dry",
    gates: [
      { gate: "p1", status: "pass", detail: "neto de costes" },
      { gate: "dsr", status: "not_evaluated", detail: null },
    ],
    candidates: 3,
    evaluated: 3,
    promoted: false,
    activeVersionId: null,
    reasons: [],
    writes: ["save_candidate", "save_finalist"],
    replayed: false,
    auditEventId: "ev-1",
    computedAt: "2026-11-16T12:00:00Z",
    notes: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BacktestOrchestratorTrigger", () => {
  it("gateStatusLabel declarado: PASS cumple, FAIL no cumple, NOT_EVALUATED sin dato", () => {
    expect(gateStatusLabel("pass")).toBe("Cumple");
    expect(gateStatusLabel("fail")).toBe("No cumple");
    expect(gateStatusLabel("not_evaluated")).toBe(ABSENT_DATA_NOT_MEASURED);
    expect(gateStatusLabel(null)).toBe(ABSENT_DATA_NOT_MEASURED);
  });

  it("arranca en dryRun y lo envía al servidor con techo finalista", async () => {
    runAutoOrchestrator.mockResolvedValue(receipt());
    render(<BacktestOrchestratorTrigger instrumentId="inst-1" symbol="ACA" />);

    const toggle = screen.getByRole("checkbox") as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    expect(
      screen.getByText(/Simulación: no escribe nada del lifecycle/i),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar embudo/i }));

    await waitFor(() => expect(runAutoOrchestrator).toHaveBeenCalledTimes(1));
    expect(runAutoOrchestrator).toHaveBeenCalledWith(
      expect.objectContaining({
        instrumentId: "inst-1",
        dryRun: true,
        toPhase: "finalista",
      }),
    );
  });

  it("el recibo declara fase, gates y escrituras suprimidas (dryRun)", async () => {
    runAutoOrchestrator.mockResolvedValue(receipt());
    render(<BacktestOrchestratorTrigger instrumentId="inst-1" symbol="ACA" />);

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar embudo/i }));

    await waitFor(() => expect(screen.getByText(/Completado/)).toBeTruthy());
    expect(screen.getByText(/finalista/)).toBeTruthy();
    expect(screen.getByText(/2 escrituras suprimidas/)).toBeTruthy();
    expect(screen.getByText(/ACTIVE no escrito/)).toBeTruthy();
    expect(screen.getByText(/p1 · Cumple/)).toBeTruthy();
    // Un gate no evaluado NO se rotula como cumple ni como fallo.
    expect(screen.getByText(`dsr · ${ABSENT_DATA_NOT_MEASURED}`)).toBeTruthy();
    expect(screen.getByText(/trigger:abc123/)).toBeTruthy();
  });

  it("un recibo incompleto se rotula y muestra motivos (fail-closed)", async () => {
    runAutoOrchestrator.mockResolvedValue(
      receipt({
        status: "INCOMPLETE",
        phaseReached: "laboratorio",
        notes: ["fase_no_alcanzada:laboratorio"],
        gates: [{ gate: "p1", status: "not_evaluated", detail: null }],
      }),
    );
    render(<BacktestOrchestratorTrigger instrumentId="inst-1" symbol="ACA" />);

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar embudo/i }));

    await waitFor(() =>
      expect(screen.getByText(/Incompleto \(fail-closed\)/)).toBeTruthy(),
    );
    expect(screen.getByText(/fase_no_alcanzada:laboratorio/)).toBeTruthy();
  });

  it("denuncia la violación de contrato si el recibo trae ACTIVE", async () => {
    runAutoOrchestrator.mockResolvedValue(
      receipt({ promoted: true, activeVersionId: "ver-1" }),
    );
    render(<BacktestOrchestratorTrigger instrumentId="inst-1" symbol="ACA" />);

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar embudo/i }));

    await waitFor(() =>
      expect(screen.getByText(/contrato violado: ACTIVE escrito/)).toBeTruthy(),
    );
  });

  it("un 409 de ámbito se muestra como error, no como recibo", async () => {
    runAutoOrchestrator.mockRejectedValue(
      new Error(
        "instrument_out_of_estudio_scope: ACA no pertenece al universo",
      ),
    );
    render(<BacktestOrchestratorTrigger instrumentId="inst-1" symbol="ACA" />);

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar embudo/i }));

    await waitFor(() =>
      expect(screen.getByText(/out_of_estudio_scope/)).toBeTruthy(),
    );
    expect(screen.queryByText(/Completado/)).toBeNull();
  });
});
