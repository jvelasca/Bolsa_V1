/**
 * Tests — sync Ayuda C1 (v1.8 HELP + Hoy honesty).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";
import { HoyEnLaMesaBlock } from "@/features/help/hoy-en-la-mesa";

afterEach(() => cleanup());

describe("help C1 v1.8 sync", () => {
  it("HELP_CONTENT_AS_OF is 2026-08-27", () => {
    expect(HELP_CONTENT_AS_OF).toBe("2026-08-27");
  });

  it("Hoy en la mesa states BUY only with TradePlan TRIGGERED", () => {
    render(
      <MemoryRouter>
        <HoyEnLaMesaBlock />
      </MemoryRouter>,
    );
    const text = screen.getByTestId("hoy-en-la-mesa").textContent ?? "";
    expect(text).toMatch(/BUY solo con TradePlan TRIGGERED/i);
    expect(text).toMatch(/nunca BUY/i);
    expect(text).toMatch(/T1\/T2 del plan son del TradePlan/i);
    expect(text).toMatch(/PositionState/i);
    expect(text).toMatch(/OPEN[\s\S]*PARTIAL[\s\S]*PROTECTED[\s\S]*CLOSED/i);
    expect(text).toMatch(/mark\/reduce ≠ orden broker/i);
    expect(text).toMatch(/ExitPlan/i);
    expect(text).toMatch(/razones canónicas/i);
    expect(text).toMatch(/≠ auto-exit/i);
    expect(text).toMatch(/ExecutionPlan/i);
    expect(text).toMatch(/plan de envío/i);
    expect(text).toMatch(/≠ broker/i);
    expect(text).toMatch(/ExitPermission/i);
    expect(text).toMatch(/veto de salida/i);
    expect(text).toMatch(/≠ check_opening/i);
    expect(text).toMatch(/Kill switch bloquea aperturas/i);
    expect(text).toMatch(/desriesgo humano SEMI/i);
    expect(text).toMatch(/plan persistido/i);
    expect(text).toMatch(/riesgo del TradePlan/i);
    expect(text).toMatch(/% caja/i);
    expect(text).toMatch(/Cadena de salida/i);
    expect(text).toMatch(/no es auto-exit/i);
    expect(text).toMatch(/Operaciones/i);
    expect(text).toMatch(/Proteger/i);
    expect(text).toMatch(/filtros/i);
    expect(text).toMatch(/No operar hoy/i);
    expect(text).toMatch(/session_verdict/i);
    expect(text).toMatch(/UNKNOWN ≠ ERROR/i);
    expect(text).toMatch(/no asumir que no se ejecutó/i);
    expect(text).toMatch(/CREATED ≠ FILLED/i);
    expect(text).toMatch(/orden creada no es fill/i);
    expect(text).toMatch(/PositionRevision/i);
    expect(text).toMatch(/historia auditada/i);
    expect(text).toMatch(/PortfolioReconciliation/i);
    expect(text).toMatch(/no auto-heal/i);
    expect(text).toMatch(/PaperBroker/i);
    expect(text).toMatch(/venue PAPER/i);
    expect(text).toMatch(/BrokerAdapter/i);
    expect(text).toMatch(/mock live no envía/i);
    expect(text).toMatch(/XTB/i);
    expect(text).toMatch(/fill ledger/i);
    expect(text).toMatch(/LiveLedgerReconciliation|live↔ledger|Paper\|Live/i);
    expect(text).toMatch(/protect_applied/i);
    expect(text).toMatch(/persist None/i);
    expect(text).toMatch(/Autoeval/i);
    expect(text).toMatch(/measure ≠ Accept/i);
  });
});
