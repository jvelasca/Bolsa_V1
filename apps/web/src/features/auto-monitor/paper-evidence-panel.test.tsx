/**
 * PAPER-2 — regresión de la superficie de evidencia durable PAPER (primer nivel).
 *
 * Fija lo que la UI no puede romper:
 *
 * 1. El usuario distingue «Incumplido» de «Sin dato todavía» (estado por criterio, nunca un
 *    comodín): un bloque no medido queda «Sin dato todavía», no «Incumplido».
 * 2. Los siete criterios se pintan con su origen y su medición.
 * 3. Nunca aparece la confirmación reservada como token suelto en el resultado.
 * 4. Sin cuenta activa se declara el hueco (fail-closed), no se lee un material global.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/api/schema";
import {
  buildPaperConfirmationVerdict,
  type PaperConfirmationContractInput,
} from "./paper-confirmation-contract";

type AutoPaperEvidenceDto = components["schemas"]["AutoPaperEvidenceDto"];

const INPUT: PaperConfirmationContractInput = {
  window: { loaded: true, days: 10, episodes: 3 },
  operations: { loaded: true, operations: 5, withCycleLineage: 5 },
  executions: { loaded: false, fills: null, attributed: null },
  closures: { loaded: false, settlements: null, reconciled: null },
  costs: { loaded: false, expected: null, complete: null },
  results: { loaded: false, withMeasuredResult: null, contradictions: null },
};

const VERDICT = buildPaperConfirmationVerdict(INPUT);

const DTO = {
  schemaVersion: "paper_evidence_adapter_v1",
  readOnly: true,
  accountId: "acc-1",
  asOf: null,
  verdict: "NO_CONFIRMED",
  criteria: [],
  metCriterionIds: [],
  unmetCriterionIds: [],
  unknownCriterionIds: [],
  unmetOrUnmeasuredCriterionIds: [],
  contradictions: ["settlement_pnl_mismatch:cyc-1"],
  perVersion: [],
  blockers: [],
  notes: ["fills_not_loaded", "unattributed_settlements_excluded"],
  fillsWindowFull: false,
  fillsTotalForAccount: null,
} as unknown as AutoPaperEvidenceDto;

const hookState = {
  verdict: VERDICT,
  dto: DTO as AutoPaperEvidenceDto | null,
  accountId: "acc-1" as string | null,
  isLoading: false,
  isError: false,
};

vi.mock("./use-auto-paper-evidence", () => ({
  useAutoPaperEvidence: () => hookState,
}));

import { PaperEvidencePanel } from "./paper-evidence-panel";

afterEach(() => {
  cleanup();
  hookState.verdict = VERDICT;
  hookState.dto = DTO;
  hookState.accountId = "acc-1";
  hookState.isLoading = false;
  hookState.isError = false;
});

describe("PaperEvidencePanel", () => {
  it("pinta los siete criterios y distingue Incumplido de Sin dato todavía", () => {
    render(<PaperEvidencePanel />);

    const rows = screen.getAllByTestId("paper-evidence-criterion");
    expect(rows).toHaveLength(7);
    expect(rows.map((row) => row.getAttribute("data-criterion"))).toEqual([
      "window",
      "operation_lineage",
      "execution_attribution",
      "closure_reconciliation",
      "cost_coverage",
      "durable_results",
      "non_contradiction",
    ]);

    const byStatus = Object.fromEntries(
      rows.map((row) => [
        row.getAttribute("data-criterion"),
        row.getAttribute("data-status"),
      ]),
    );
    expect(byStatus.window).toBe("met");
    expect(byStatus.operation_lineage).toBe("unmet");
    // Un bloque no cargado queda «Sin dato todavía», NO «Incumplido».
    expect(byStatus.closure_reconciliation).toBe("unknown");

    const windowRow = rows.find(
      (row) => row.getAttribute("data-criterion") === "window",
    );
    expect(windowRow?.textContent).toContain("Cumplido");
    expect(windowRow?.textContent).toContain("Origen:");

    const lineageRow = rows.find(
      (row) => row.getAttribute("data-criterion") === "operation_lineage",
    );
    expect(lineageRow?.textContent).toContain("Incumplido");

    const closureRow = rows.find(
      (row) => row.getAttribute("data-criterion") === "closure_reconciliation",
    );
    expect(closureRow?.textContent).toContain("Sin dato todavía");
  });

  it("declara los bloqueos y nunca emite la confirmación reservada", () => {
    render(<PaperEvidencePanel />);

    expect(screen.getByTestId("paper-evidence-verdict").textContent).toBe(
      "NO CONFIRMADO",
    );
    expect(screen.getByTestId("paper-evidence-blockers").textContent).toContain(
      "6 de 7",
    );
    // El token reservado no aparece suelto (frontera de palabra).
    expect(/\bCONFIRMED\b/.test(document.body.textContent ?? "")).toBe(false);
  });

  it("declara el hueco cuando no hay cuenta activa (fail-closed)", () => {
    hookState.accountId = null;
    hookState.verdict = null;
    hookState.dto = null;

    render(<PaperEvidencePanel />);

    expect(screen.getByTestId("paper-evidence-no-account")).toBeTruthy();
    expect(screen.queryByTestId("paper-evidence-panel")).toBeNull();
  });

  it("declara el fallo de lectura sin inventar material", () => {
    hookState.verdict = null;
    hookState.dto = null;
    hookState.isError = true;

    render(<PaperEvidencePanel />);

    expect(screen.getByTestId("paper-evidence-error")).toBeTruthy();
    expect(screen.queryByTestId("paper-evidence-panel")).toBeNull();
  });
});
