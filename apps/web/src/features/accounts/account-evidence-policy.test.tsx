import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountEvidencePolicy } from "./account-evidence-policy";

const getPolicy = vi.fn();
const putPolicy = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getAccountEvidencePolicy: (...a: unknown[]) => getPolicy(...a),
    putAccountEvidencePolicy: (...a: unknown[]) => putPolicy(...a),
  },
}));

const POLICY = {
  minWindows: 30,
  minTradesTotal: 100,
  minPositiveWindowPct: 60,
  minNetReturnPct: 0,
  maxDrawdownPct: 15,
  minExcessVsBuyHoldPct: 0,
  holdoutPct: 30,
  minCommissionBps: 5,
  minSlippageBps: 5,
  minSpreadBps: 2,
  isDefault: true,
  version: 0,
  minRoundTripCostBps: 22,
};

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AccountEvidencePolicy accountId="acc-1" />
    </QueryClientProvider>,
  );
}

describe("AccountEvidencePolicy", () => {
  afterEach(cleanup);
  beforeEach(() => {
    getPolicy.mockReset().mockResolvedValue(POLICY);
    putPolicy.mockReset().mockResolvedValue({ ...POLICY, isDefault: false });
  });

  it("muestra defaults y coste mínimo ida y vuelta", async () => {
    renderIt();
    expect(await screen.findByTestId("evidence-policy-minWindows")).toHaveValue(
      30,
    );
    expect(screen.getByText(/22 bps/)).toBeTruthy();
  });

  it("guarda los valores editados como números", async () => {
    renderIt();
    const input = await screen.findByTestId("evidence-policy-holdoutPct");
    fireEvent.change(input, { target: { value: "40" } });
    fireEvent.click(screen.getByTestId("evidence-policy-save"));
    await waitFor(() => expect(putPolicy).toHaveBeenCalled());
    const body = putPolicy.mock.calls[0]![1];
    expect(putPolicy.mock.calls[0]![0]).toBe("acc-1");
    expect(body.holdoutPct).toBe(40);
  });

  it("bloquea guardar con un campo vacío", async () => {
    renderIt();
    const input = await screen.findByTestId("evidence-policy-minWindows");
    fireEvent.change(input, { target: { value: "" } });
    expect(screen.getByTestId("evidence-policy-save")).toBeDisabled();
  });
});
