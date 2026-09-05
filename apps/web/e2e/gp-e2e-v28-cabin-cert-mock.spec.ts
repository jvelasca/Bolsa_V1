/**
 * GP-E2E-V28 — Operator Cabin Certification (mock).
 * V2.44 — 3 viewports · teclado · ratón · touch · overflow · focus · dark/light.
 * V2.46 — AUTO state matrix chrome.
 * V2.48 — touch ≥44px.
 * V2.49 — layout zoom 100/125/150 (not body.style.zoom).
 * V2.51 — keyboard traversal AUTO → phrase → confirm.
 *
 * Display certification only. No second FSM · Arm ≠ execute · Ranking ≠ BUY.
 * Layout zoom = CSS viewport shrink + deviceScaleFactor. Not Chrome UI chrome zoom.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v28
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installMercadoApiMocks,
} from "./fixtures";
import {
  CABIN_VIEWPORTS,
  assertNoHorizontalOverflow,
  cssViewportForZoom,
  newCabinPage,
  openAutoDesk,
} from "./helpers/cabin-cert";

const TOUCH_MIN = 44;

test.describe("GP-E2E-V28 — Operator Cabin Certification", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoApiMocks(page);
  });

  for (const vp of CABIN_VIEWPORTS) {
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
      expect(confirmBox!.height).toBeGreaterThanOrEqual(TOUCH_MIN);
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

  test("V2.51 keyboard: AUTO mode → phrase → Confirm with focus-visible ring", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = await openAutoDesk(page);
    test.skip(desk == null, "AUTO desk not mounted in this mock");
    const autoMode = desk!.getByTestId("auto-desk-mode-auto");
    expect(await autoMode.getAttribute("class")).toMatch(/focus-visible:ring/);
    await autoMode.focus();
    await expect(autoMode).toBeFocused();
    await page.keyboard.press("Enter");
    const phrase = desk!.getByTestId("demo-book-auto-arm-phrase");
    await expect(phrase).toBeVisible();
    expect(await phrase.getAttribute("class")).toMatch(/focus-visible:ring/);
    await phrase.focus();
    await expect(phrase).toBeFocused();
    await page.keyboard.press("Tab");
    const confirm = desk!.getByTestId("demo-book-auto-arm-confirm");
    await expect(confirm).toBeFocused();
    expect(await confirm.getAttribute("class")).toMatch(/focus-visible:ring/);
    await page.keyboard.press("Tab");
    const cancel = desk!.getByTestId("demo-book-auto-arm-cancel");
    await expect(cancel).toBeFocused();
    expect(await cancel.getAttribute("class")).toMatch(/focus-visible:ring/);
  });

  test("V2.48 touch: hasTouch + AUTO mode and A3 confirm ≥44px", async ({
    browser,
  }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    const { context, page } = await newCabinPage(browser, {
      width: 1366,
      height: 768,
      hasTouch: true,
      isMobile: true,
    });
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
    expect(modeBox!.height).toBeGreaterThanOrEqual(TOUCH_MIN);
    await autoMode.tap();
    const confirm = desk!.getByTestId("demo-book-auto-arm-confirm");
    await expect(confirm).toBeVisible();
    const confirmBox = await confirm.boundingBox();
    expect(confirmBox).toBeTruthy();
    expect(confirmBox!.height).toBeGreaterThanOrEqual(TOUCH_MIN);
    const cancelBox = await desk!
      .getByTestId("demo-book-auto-arm-cancel")
      .boundingBox();
    expect(cancelBox).toBeTruthy();
    expect(cancelBox!.height).toBeGreaterThanOrEqual(TOUCH_MIN);
    await context.close();
  });

  for (const vp of CABIN_VIEWPORTS) {
    for (const zoom of [100, 125, 150] as const) {
      test(`V2.49 layout-zoom ${vp.name} ${zoom}%: no horizontal overflow on cockpit`, async ({
        browser,
      }) => {
        test.skip(!e2eEnabled(), E2E_SKIP_REASON);
        const css = cssViewportForZoom(vp.width, vp.height, zoom);
        const { context, page } = await newCabinPage(browser, {
          width: vp.width,
          height: vp.height,
          zoomPct: zoom,
        });
        await installMercadoApiMocks(page);
        await page.setViewportSize({ width: css.width, height: css.height });
        await page.goto("/trading");
        const cockpit = page.getByTestId("operativa-cockpit");
        const cockpitVisible = await cockpit
          .first()
          .isVisible()
          .catch(() => false);
        if (!cockpitVisible) {
          // 1024@150% → ~683 CSS px < md (768). Dock DECISIÓN is `hidden md:flex`.
          await assertNoHorizontalOverflow(page.locator("body"));
          await context.close();
          return;
        }
        await expect(cockpit).toBeVisible({ timeout: 15_000 });
        await assertNoHorizontalOverflow(cockpit);
        await context.close();
      });
    }
  }

  for (const scheme of ["light", "dark"] as const) {
    test(`V2.44 colorScheme ${scheme}: ARM chrome + A3 visible`, async ({
      browser,
    }) => {
      test.skip(!e2eEnabled(), E2E_SKIP_REASON);
      const { context, page } = await newCabinPage(browser, {
        width: 1366,
        height: 768,
        colorScheme: scheme,
      });
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

  test("V2.46 state matrix: MANUAL/SEMI/A3 never AUTO ARMADO; arm + auto → ARMADO", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    const desk = await openAutoDesk(page);
    test.skip(desk == null, "AUTO desk not mounted in this mock");

    await desk!.getByTestId("auto-desk-mode-manual").click();
    await expect(desk!.getByTestId("auto-desk-arm-state")).toHaveAttribute(
      "data-arm",
      "disarmed",
    );
    await expect(desk!.getByTestId("auto-desk-arm-state-label")).toHaveText(
      "AUTO DESARMADO",
    );

    await desk!.getByTestId("auto-desk-mode-semi").click();
    await expect(desk!.getByTestId("auto-desk-arm-state-label")).toHaveText(
      "AUTO DESARMADO",
    );

    await desk!.getByTestId("auto-desk-mode-auto").click();
    await expect(desk!.getByTestId("demo-book-auto-arm-form")).toBeVisible();
    await expect(desk!.getByTestId("auto-desk-arm-state-label")).toHaveText(
      "AUTO DESARMADO",
    );
    await expect(desk!.getByTestId("demo-book-auto-arm-estado")).toHaveText(
      "AUTO DESARMADO",
    );

    await desk!.getByTestId("demo-book-auto-arm-phrase").fill("ACTIVAR AUTO");
    await desk!.getByTestId("demo-book-auto-arm-confirm").click();
    await expect(desk!.getByTestId("auto-desk-arm-state")).toHaveAttribute(
      "data-arm",
      "armed",
    );
    await expect(desk!.getByTestId("auto-desk-arm-state-label")).toHaveText(
      "AUTO ARMADO",
    );
    await expect(desk!.getByTestId("auto-desk-execution-venue")).toHaveText(
      /EJECUCIÓN:\s*PAPER/,
    );
    await expect(desk!.getByTestId("auto-desk-arm-permission")).not.toHaveText(
      /operaci[oó]n autorizad/i,
    );
  });
});
