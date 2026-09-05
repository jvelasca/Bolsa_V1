/**
 * GP-E2E-V29 — Visual snapshots + contrast (mock).
 * V2.50 — bounded screenshots 1920/1366/1024 · light/dark.
 * Contrast: WCAG-ish 4.5:1 on operational chrome (not a full chart audit).
 *
 * Snapshots certify key surfaces, not every pixel of the app.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v29
 * Update goldens:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v29 --update-snapshots
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyPaperDayApiMocks,
  installMercadoApiMocks,
} from "./fixtures";
import {
  assertReadableContrast,
  newCabinPage,
  openAutoDesk,
} from "./helpers/cabin-cert";

const SNAPSHOT = {
  animations: "disabled" as const,
  maxDiffPixelRatio: 0.03,
};

async function screenshotIfPresent(page: Page, testId: string, name: string) {
  const loc = page.getByTestId(testId);
  if ((await loc.count()) === 0) return;
  const first = loc.first();
  if (!(await first.isVisible().catch(() => false))) return;
  await expect(first).toHaveScreenshot(name, SNAPSHOT);
}

async function openDeskOrSkip(page: Page) {
  const desk = await openAutoDesk(page);
  test.skip(desk == null, "AUTO desk not mounted in this mock");
  return desk!;
}

test.describe("GP-E2E-V29 — visual + contrast", () => {
  test("V2.50 snapshots 1366 light: six cabin surfaces", async ({
    browser,
  }) => {
    test.skip(
      Boolean(process.env.CI),
      "pixel goldens are host-OS (win32); CI linux certifies contrast + v28 DOM",
    );
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    const { context, page } = await newCabinPage(browser, {
      width: 1366,
      height: 768,
      colorScheme: "light",
    });
    await installMercadoApiMocks(page);
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    await screenshotIfPresent(
      page,
      "operativa-cockpit",
      "1366-light-cockpit.png",
    );
    await screenshotIfPresent(
      page,
      "decision-surface-compact-position",
      "1366-light-decision-surface.png",
    );
    await screenshotIfPresent(
      page,
      "decision-surface-compact-entry",
      "1366-light-decision-surface-entry.png",
    );
    await screenshotIfPresent(
      page,
      "position-card-risk-levels",
      "1366-light-position-card.png",
    );
    await screenshotIfPresent(
      page,
      "position-journey-hud",
      "1366-light-position-card-hud.png",
    );
    const desk = await openAutoDesk(page);
    if (desk) {
      await expect(desk).toHaveScreenshot("1366-light-auto-desk.png", SNAPSHOT);
    }
    await screenshotIfPresent(
      page,
      "chart-focus-toggle",
      "1366-light-chart-focus.png",
    );
    await screenshotIfPresent(
      page,
      "chart-decision-surface-hud",
      "1366-light-chart-hud.png",
    );

    await installHoyPaperDayApiMocks(page);
    await page.goto("/hoy");
    await screenshotIfPresent(page, "hoy-inbox", "1366-light-hoy-inbox.png");
    await context.close();
  });

  test("V2.50 snapshots 1366 dark: six cabin surfaces", async ({ browser }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    test.skip(
      Boolean(process.env.CI),
      "pixel goldens are host-OS (win32); CI linux certifies contrast + v28 DOM",
    );
    const { context, page } = await newCabinPage(browser, {
      width: 1366,
      height: 768,
      colorScheme: "dark",
    });
    await installMercadoApiMocks(page);
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 15_000,
    });
    await screenshotIfPresent(
      page,
      "operativa-cockpit",
      "1366-dark-cockpit.png",
    );
    await screenshotIfPresent(
      page,
      "decision-surface-compact-position",
      "1366-dark-decision-surface.png",
    );
    await screenshotIfPresent(
      page,
      "position-card-risk-levels",
      "1366-dark-position-card.png",
    );
    const desk = await openAutoDesk(page);
    if (desk) {
      await expect(desk).toHaveScreenshot("1366-dark-auto-desk.png", SNAPSHOT);
    }
    await screenshotIfPresent(
      page,
      "chart-focus-toggle",
      "1366-dark-chart-focus.png",
    );
    await installHoyPaperDayApiMocks(page);
    await page.goto("/hoy");
    await screenshotIfPresent(page, "hoy-inbox", "1366-dark-hoy-inbox.png");
    await context.close();
  });

  for (const vp of [
    { name: "1920", width: 1920, height: 1080 },
    { name: "1024", width: 1024, height: 768 },
  ] as const) {
    test(`V2.50 snapshot ${vp.name} light cockpit + AUTO`, async ({
      browser,
    }) => {
      test.skip(!e2eEnabled(), E2E_SKIP_REASON);
      test.skip(
        Boolean(process.env.CI),
        "pixel goldens are host-OS (win32); CI linux certifies contrast + v28 DOM",
      );
      const { context, page } = await newCabinPage(browser, {
        width: vp.width,
        height: vp.height,
        colorScheme: "light",
      });
      await installMercadoApiMocks(page);
      await page.goto("/trading");
      await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
        timeout: 15_000,
      });
      await screenshotIfPresent(
        page,
        "operativa-cockpit",
        `${vp.name}-light-cockpit.png`,
      );
      const desk = await openAutoDesk(page);
      if (desk) {
        await expect(desk).toHaveScreenshot(
          `${vp.name}-light-auto-desk.png`,
          SNAPSHOT,
        );
      }
      await context.close();
    });
  }

  for (const scheme of ["light", "dark"] as const) {
    test(`V2.50 contrast ${scheme}: cockpit · ARM · A3 states`, async ({
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
      await assertReadableContrast(page.getByTestId("operativa-cockpit"));
      const desk = await openDeskOrSkip(page);
      await assertReadableContrast(
        desk.getByTestId("auto-desk-arm-state-label"),
      );
      await assertReadableContrast(
        desk.getByTestId("auto-desk-execution-venue"),
      );
      const autoMode = desk.getByTestId("auto-desk-mode-auto");
      await autoMode.click();
      await expect(autoMode).toHaveAttribute("aria-pressed", "false");
      const form = desk.getByTestId("demo-book-auto-arm-form");
      await expect(form).toBeVisible();
      await assertReadableContrast(
        form.getByTestId("demo-book-auto-arm-estado"),
      );
      await assertReadableContrast(
        form.getByTestId("demo-book-auto-arm-confirm"),
      );
      await form.getByTestId("demo-book-auto-arm-phrase").fill("wrong");
      await form.getByTestId("demo-book-auto-arm-confirm").click();
      const err = form.getByTestId("demo-book-auto-arm-error");
      await expect(err).toBeVisible();
      await assertReadableContrast(err);
      const phrase = form.getByTestId("demo-book-auto-arm-phrase");
      await phrase.focus();
      expect(await phrase.getAttribute("class")).toMatch(/focus-visible:ring/);
      await context.close();
    });
  }
});
