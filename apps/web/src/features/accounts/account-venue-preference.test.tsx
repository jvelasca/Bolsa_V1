import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountVenuePreference } from "@/features/accounts/account-venue-preference";

vi.mock("@/lib/api", () => ({
  api: {
    getAccountBrokerVenue: vi.fn(async () => ({
      accountId: "acc-1",
      preference: null,
      effective: "paper",
    })),
    setAccountBrokerVenue: vi.fn(
      async (_id: string, venue: "paper" | "live") => ({
        accountId: "acc-1",
        preference: venue,
        effective: venue,
      }),
    ),
  },
}));

function renderPref() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AccountVenuePreference accountId="acc-1" />
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("AccountVenuePreference OR-6/PA-1", () => {
  it("shows Paper|Live account preference (not the mesa global toggle)", async () => {
    renderPref();
    const box = await screen.findByTestId("account-venue-preference");
    await waitFor(() => {
      expect(box.textContent ?? "").toMatch(/Paper/i);
    });
    expect(screen.getByTestId("account-venue-preference-paper")).toBeTruthy();
    expect(screen.getByTestId("account-venue-preference-live")).toBeTruthy();
    expect(box.textContent ?? "").toMatch(/experimental/i);
  });
});
