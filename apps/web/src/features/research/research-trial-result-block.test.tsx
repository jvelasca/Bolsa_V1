/**
 * Asesor → Laboratorio · bloque de resultado — guarda `UNKNOWN ≠ 0` (slice A4).
 *
 * Los costes del experimento viven en nivel 3, donde el guion de auditoría está
 * permitido. Lo que NO está permitido es presentar un hueco como `0 bps` medido.
 */

import { MemoryRouter } from "react-router-dom";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ResearchTrialResultBlock } from "@/features/research/research-trial-result-block";

afterEach(() => cleanup());

function renderBlock(fallback?: {
  commissionBps?: number | null;
  slippageBps?: number | null;
}) {
  return render(
    <MemoryRouter>
      <ResearchTrialResultBlock
        trialId="trial-1"
        metrics={{}}
        fallback={fallback}
      />
    </MemoryRouter>,
  );
}

describe("ResearchTrialResultBlock · costes no medidos", () => {
  it("declara el hueco con el guion de auditoría, no con 0 bps", () => {
    const { container } = renderBlock();
    const text = container.textContent ?? "";
    expect(text).toContain("Commission: —");
    expect(text).toContain("Slippage: —");
    expect(text).toContain("Spread: —");
    expect(text).not.toContain("0 bps");
  });

  it("un coste medido conserva su valor", () => {
    const { container } = renderBlock({
      commissionBps: 4,
      slippageBps: 2,
    });
    const text = container.textContent ?? "";
    expect(text).toContain("Commission: 4 bps");
    expect(text).toContain("Slippage: 2 bps");
    // El spread no llega en el fallback: sigue declarado como hueco.
    expect(text).toContain("Spread: —");
  });
});
