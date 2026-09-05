/**
 * GP-E2E-V28 — Operator Cabin Certification (mock).
 * V2.44 — 3 viewports · teclado · ratón · touch · zoom · overflow · focus · dark/light.
 *
 * Display certification only. No second FSM · Arm ≠ execute · Ranking ≠ BUY.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v28
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installMercadoApiMocks,
} from "./fixtures";

const VIEWPORTS = [
  { name: "desktop", width: 1920, height: 1080 },
  { name: "laptop", width: 1366, height: 768 },
  { name: "tablet", width: 1024, height: 768 },
] as const;

async function openAutoDesk(page: Page) {
  const desk = page.getByTestId("auto-desk-panel");
  const count = await desk.count();
  if (count === 0) return null;
  const summary = desk.getByTestId("auto-desk-summary");
  const open = await desk.evaluate((el) => (el as HTMLDetailsElement).open);
  if (!open) await summary.click();
  return desk;
}

test.describe("GP-E2E-V28 — Operator Cabin Certification", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoApiMocks(page);
  });

  for (const vp of VIEWPORTS) {
    test(`V2.44 ${vp.name} ${vp.width}×${vp.height}: cockpit + ARM chrome + A3 touch`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/trading");
      const cockpit = page.getByTestId("operativa-cockpit");
      await expect(cockpit).toBeVisible({ timeout: 15_000 });
      const box = await cockpit.boundingBox();
      expect(box).toBeTruthy();
      expect(box!.width).toBeGreaterThanOrEqual(240);

      const desk = await openAutoDesk(page);
      test.skip(desk == null, "AUTO desk not mounted in this mock");
      await expect(desk!.getByTestId("auto-desk-arm-state")).toBeVisible();
      await expect(desk!.getByTestId("auto-desk-arm-state-label")).toHaveText(
        /AUTO DESARMADO|AUTO ARMADO/,
      );
      await expect(desk!.getByTestId("auto-desk-execution-venue")).toHaveText(
        /EJECUCIÓN:\s*PAPER/,
      );

      await desk!.getByTestId("auto-desk-mode-auto").click();
      const form = desk!.getByTestId("demo-book-auto-arm-form");
      await expect(form).toBeVisible();
      const confirmBox = await form
        .getByTestId("demo-book-auto-arm-confirm")
        .boundingBox();
      expect(confirmBox).toBeTruthy();
      expect(confirmBox!.height).toBeGreaterThanOrEqual(36);
    });
  }

  test("V2.44 mouse: Automático opens A3 · Cancelar closes without arm", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = await openAutoDesk(page);
    test.skip(desk == null, "AUTO desk not mounted in this mock");
    await desk!.getByTestId("auto-desk-mode-auto").click();
    await expect(desk!.getByTestId("demo-book-auto-arm-form")).toBeVisible();
    await desk!.getByTestId("demo-book-auto-arm-cancel").click();
    await expect(desk!.getByTestId("demo-book-auto-arm-form")).toHaveCount(0);
    await expect(desk!.getByTestId("auto-desk-arm-state")).toHaveAttribute(
      "data-arm",
      "disarmed",
    );
  });

  test("V2.44 keyboard: Tab reaches A3 phrase · focus-visible ring class", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = await openAutoDesk(page);
    test.skip(desk == null, "AUTO desk not mounted in this mock");
    await desk!.getByTestId("auto-desk-mode-auto").click();
    const phrase = desk!.getByTestId("demo-book-auto-arm-phrase");
    await expect(phrase).toBeVisible();
    expect(await phrase.getAttribute("class")).toMatch(/focus-visible:ring/);
    await phrase.focus();
    await expect(phrase).toBeFocused();
    await page.keyboard.press("Tab");
    const confirm = desk!.getByTestId("demo-book-auto-arm-confirm");
    await expect(confirm).toBeFocused();
    expect(await confirm.getAttribute("class")).toMatch(/focus-visible:ring/);
  });

  test("V2.44 touch: hasTouch + AUTO mode and A3 confirm ≥36px", async ({
    browser,
  }) => {
    const context = await browser.newContext({
      viewport: { width: 1366, height: 768 },
      hasTouch: true,
      isMobile: true,
    });
    const page = await context.newPage();
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoApiMocks(page);
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = await openAutoDesk(page);
    test.skip(desk == null, "AUTO desk not mounted in this mock");
    const autoMode = desk!.getByTestId("auto-desk-mode-auto");
    const modeBox = await autoMode.boundingBox();
    expect(modeBox).toBeTruthy();
    expect(modeBox!.height).toBeGreaterThanOrEqual(36);
    await autoMode.tap();
    const confirm = desk!.getByTestId("demo-book-auto-arm-confirm");
    await expect(confirm).toBeVisible();
    const confirmBox = await confirm.boundingBox();
    expect(confirmBox).toBeTruthy();
    expect(confirmBox!.height).toBeGreaterThanOrEqual(36);
    await context.close();
  });

  for (const zoom of [100, 125, 150] as const) {
    test(`V2.44 zoom ${zoom}%: no horizontal overflow on cockpit`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1366, height: 768 });
      await page.goto("/trading");
      await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
        timeout: 15_000,
      });
      await page.evaluate((z) => {
        (document.body.style as CSSStyleDeclaration & { zoom?: string }).zoom =
          String(z / 100);
      }, zoom);
      const overflow = await page
        .getByTestId("operativa-cockpit")
        .evaluate((el) => {
          const node = el as HTMLElement;
          return {
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
          };
        });
      expect(overflow.scrollWidth).toBeLessThanOrEqual(
        overflow.clientWidth + 1,
      );
    });
  }

  for (const scheme of ["light", "dark"] as const) {
    test(`V2.44 colorScheme ${scheme}: ARM chrome + A3 visible`, async ({
      browser,
    }) => {
      const context = await browser.newContext({
        viewport: { width: 1366, height: 768 },
        colorScheme: scheme,
      });
      const page = await context.newPage();
      test.skip(!e2eEnabled(), E2E_SKIP_REASON);
      await installMercadoApiMocks(page);
      await page.goto("/trading");
      await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
        timeout: 15_000,
      });
      const desk = await openAutoDesk(page);
      test.skip(desk == null, "AUTO desk not mounted in this mock");
      await expect(desk!.getByTestId("auto-desk-arm-state")).toBeVisible();
      await desk!.getByTestId("auto-desk-mode-auto").click();
      await expect(desk!.getByTestId("demo-book-auto-arm-form")).toBeVisible();
      await expect(
        desk!.getByTestId("demo-book-auto-arm-estado"),
      ).toBeVisible();
      await context.close();
    });
  }
});
