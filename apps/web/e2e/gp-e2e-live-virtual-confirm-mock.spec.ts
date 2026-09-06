/**
 * GP-E2E — Confirm LIVE VIRTUAL híbrido (mock).
 *
 * Venue=live **simulado** en mocks: banner · telegrama · por qué · CTA VIRTUAL.
 * ≠ Accept LIVE · ≠ flip PAPER_D_EXECUTE · ≠ settlement XTB.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-live-virtual-confirm-mock
 *
 * @see docs/engineering/design-live-virtual-order-gateway-ui-2026-09-07.md
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installLiveVirtualConfirmMocks,
} from "./fixtures";

test.describe("GP-E2E — Confirm LIVE VIRTUAL (mock)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installLiveVirtualConfirmMocks(page);
  });

  test("shows hybrid gateway honesty chrome on /confirm", async ({ page }) => {
    await page.goto("/confirm");

    await expect(page.getByTestId("confirm-content")).toBeVisible();
    await expect(page.getByTestId("live-virtual-order-gateway")).toBeVisible({
      timeout: 15_000,
    });

    const banner = page.getByTestId("live-virtual-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(/LIVE VIRTUAL/i);
    await expect(banner).toContainText(/SIMULADO/i);
    await expect(banner).toContainText(/no capital real/i);

    await expect(page.getByTestId("live-virtual-telegram")).toBeVisible();
    await expect(page.getByTestId("live-virtual-telegram")).toContainText(
      /Broker \(VIRTUAL\)/i,
    );
    await expect(page.getByTestId("live-virtual-ladder")).toBeVisible();

    await expect(page.getByTestId("live-virtual-why")).toBeVisible();
    await expect(page.getByTestId("live-virtual-why-anti")).toContainText(
      /Ranking ≠ BUY/i,
    );
    await expect(page.getByTestId("live-virtual-why-anti")).toContainText(
      /Arm ≠ Execute/i,
    );

    await expect(page.getByTestId("confirm-live-venue-badge")).toHaveText(
      /LIVE VIRTUAL · SIMULADO/i,
    );

    const executeCta = page.getByTestId("confirm-execute-cta");
    await expect(executeCta).toBeVisible();
    await expect(executeCta).toContainText(/LIVE VIRTUAL/i);
    await expect(executeCta).toContainText(/simulado/i);
    await expect(executeCta).not.toHaveText(/^Ejecutar en LIVE$/);
  });
});
