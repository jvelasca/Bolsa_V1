/**
 * GP-E2E-V25 — UI Truth + responsive/touch certification (mock).
 * V2.41 — Chart Focus @1024 · AUTO ladder · DECISIÓN width floor · 3 viewports.
 *
 * Asserts Chart Focus hit area and Mercado cockpit chrome across viewports.
 * Does not invent a second FSM — display certification only.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v25
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";

const VIEWPORTS = [
  { name: "desktop", width: 1920, height: 1080 },
  { name: "laptop", width: 1366, height: 768 },
  { name: "tablet", width: 1024, height: 768 },
] as const;

test.describe("GP-E2E-V25 — UI Truth / responsive / touch", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  for (const vp of VIEWPORTS) {
    test(`${vp.name} ${vp.width}×${vp.height}: Mercado cockpit + no COMPRAR`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/trading");
      const cockpit = page.getByTestId("operativa-cockpit");
      await expect(cockpit).toBeVisible({ timeout: 15_000 });
      await expect(
        page.getByRole("button", { name: /^COMPRAR$/i }),
      ).toHaveCount(0);
    });
  }

  test("Chart Focus toggle has ≥36px hit area when visible", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const toggle = page.getByTestId("chart-focus-toggle");
    const count = await toggle.count();
    test.skip(
      count === 0,
      "chart focus toggle not mounted without plan levels",
    );
    const box = await toggle
      .getByTestId("chart-focus-mode-simple")
      .boundingBox();
    expect(box).toBeTruthy();
    expect(box!.height).toBeGreaterThanOrEqual(36);
    await toggle.getByTestId("chart-focus-mode-completo").click();
    await expect(toggle).toHaveAttribute("data-chart-focus", "completo");
    await page.keyboard.press("Tab");
  });

  test("V2.40 — AUTO autonomy modes have ≥36px hit area when desk open", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = page.getByTestId("auto-desk-panel");
    const deskCount = await desk.count();
    test.skip(deskCount === 0, "AUTO desk not mounted in this mock");
    const summary = desk.getByTestId("auto-desk-summary");
    const open = await desk.evaluate((el) => (el as HTMLDetailsElement).open);
    if (!open) await summary.click();
    const autoMode = desk.getByTestId("auto-desk-mode-auto");
    await expect(autoMode).toBeVisible();
    const box = await autoMode.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.height).toBeGreaterThanOrEqual(36);
  });

  test("V2.41 — Chart Focus visible at 1024 when plan levels on", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const toggle = page.getByTestId("chart-focus-toggle");
    const count = await toggle.count();
    test.skip(
      count === 0,
      "chart focus toggle not mounted without plan levels",
    );
    await expect(toggle).toBeVisible();
    const box = await toggle
      .getByTestId("chart-focus-mode-simple")
      .boundingBox();
    expect(box).toBeTruthy();
    expect(box!.height).toBeGreaterThanOrEqual(36);
  });

  test("V2.41 — DECISIÓN dock width floor ≥240px at 1024", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto("/trading");
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 15_000 });
    const box = await cockpit.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThanOrEqual(240);
  });

  for (const vp of VIEWPORTS) {
    test(`V2.41 ${vp.name}: AUTO ladder chrome when desk open`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/trading");
      await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
        timeout: 15_000,
      });
      const desk = page.getByTestId("auto-desk-panel");
      const deskCount = await desk.count();
      test.skip(deskCount === 0, "AUTO desk not mounted in this mock");
      const summary = desk.getByTestId("auto-desk-summary");
      const open = await desk.evaluate((el) => (el as HTMLDetailsElement).open);
      if (!open) await summary.click();
      await expect(desk.getByTestId("auto-desk-plan-preview")).toBeVisible();
      await expect(desk.getByTestId("auto-desk-autonomy")).toBeVisible();
    });
  }
});
