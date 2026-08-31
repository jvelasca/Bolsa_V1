/**
 * V1.41 — Daily Desk inbox component.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DailyDeskInboxV1 } from "@bolsa/shared";
import { DailyDeskInbox } from "@/features/mesa/daily-desk-inbox";

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
}));

afterEach(() => cleanup());

function inbox(partial: Partial<DailyDeskInboxV1> = {}): DailyDeskInboxV1 {
  return {
    items: [],
    count: 0,
    emptyLabel: "Nada requiere tu atención",
    ...partial,
  };
}

describe("DailyDeskInbox V1.41", () => {
  it("shows empty state when nothing needs attention", () => {
    render(
      <MemoryRouter>
        <DailyDeskInbox inbox={inbox()} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("daily-desk-empty").textContent).toMatch(
      /Nada requiere/,
    );
    expect(
      screen.getByTestId("daily-desk-inbox").getAttribute("data-count"),
    ).toBe("0");
  });

  it("renders attention-ordered items with CTA", () => {
    render(
      <MemoryRouter>
        <DailyDeskInbox
          inbox={inbox({
            count: 2,
            items: [
              {
                id: "pending-confirm",
                kind: "pending_confirm",
                symbol: "Confirm",
                attention: "URGENT",
                reason: "1 pendiente de firma",
                ctaLabel: "Revisar y confirmar",
              },
              {
                id: "position-p1",
                kind: "position",
                symbol: "AAPL",
                attention: "ATTENTION",
                reason: "T1 alcanzado",
                ctaLabel: "Reducir",
                positionId: "p1",
              },
            ],
          })}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("daily-desk-items")).toBeTruthy();
    expect(
      screen
        .getByTestId("daily-desk-item-pending-confirm")
        .getAttribute("data-attention"),
    ).toBe("URGENT");
    expect(screen.getByTestId("daily-desk-cta-confirm").textContent).toBe(
      "Revisar y confirmar",
    );
    expect(screen.getByTestId("daily-desk-cta-AAPL").textContent).toBe(
      "Reducir",
    );
  });
});
