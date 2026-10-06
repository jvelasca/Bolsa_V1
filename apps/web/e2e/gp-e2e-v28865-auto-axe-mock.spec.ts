/**
 * V2.88.65 — AUTO UI REFACTOR 3.0 (S4): certificación de accesibilidad de `/auto/*`.
 *
 * Barrido `axe-core` (tags WCAG 2.0/2.1 A+AA) sobre el espacio AUTO con la API mockeada: **0
 * violaciones `critical`/`serious`**. Cubre además:
 *   - navegación por teclado de las pestañas WAI-ARIA de ANÁLISIS,
 *   - responsive (viewport móvil),
 *   - estados carga / error / vacío / no-medido sin romper accesibilidad.
 *
 * Cierra `F-A2` (auditoría UI AUTO para usuario básico). UI/read-model puro: no toca motor.
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v28865
 * Against an existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-v28865
 *
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installAutoWorkspaceMocks,
} from "./fixtures";

const AUTO_ROUTES = [
  "/auto",
  "/auto/operar",
  "/auto/operar/operacion/e2e-cycle-aaa",
  "/auto/cartera",
  "/auto/riesgo",
  "/auto/analisis",
  "/auto/sistema",
  "/auto-monitor?mode=current",
] as const;

/** Falla con detalle accionable si hay violaciones `critical`/`serious`. */
async function expectNoCriticalSerious(page: Page, context: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter(
    (violation) =>
      violation.impact === "critical" || violation.impact === "serious",
  );
  const detail = blocking
    .map(
      (violation) =>
        `· ${violation.id} [${violation.impact}] ×${violation.nodes.length} — ${violation.help}\n    ${violation.nodes
          .slice(0, 3)
          .map((node) => node.target.join(" "))
          .join("\n    ")}`,
    )
    .join("\n");
  expect(blocking, `[${context}] ${detail}`).toEqual([]);
}

async function expectSingleMain(page: Page) {
  await expect(
    page.locator("main:not([data-testid='backtests-keepalive-host'])"),
  ).toHaveCount(1);
}

async function expectSingleH1(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
}

async function expectWorkspaceReady(page: Page) {
  await expect(
    page
      .getByTestId("auto-workspace")
      .or(page.getByTestId("auto-monitor-page")),
  ).toBeVisible();
}

test.describe("GP-E2E-V28865 — AUTO 3.0 accesibilidad (axe)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installAutoWorkspaceMocks(page);
  });

  // Un test por ruta: el barrido de 8 rutas con axe excede el timeout de un único test.
  for (const route of AUTO_ROUTES) {
    test(`0 violaciones critical/serious en ${route}`, async ({ page }) => {
      await page.goto(route);
      await expectWorkspaceReady(page);
      await expectSingleMain(page);
      await expectSingleH1(page);
      await expectNoCriticalSerious(page, route);
    });
  }

  test("responsive: móvil sin violaciones critical/serious", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of ["/auto", "/auto/analisis"] as const) {
      await page.goto(route);
      await expectWorkspaceReady(page);
      await expectNoCriticalSerious(page, `${route} @390×844`);
    }
  });

  test("teclado: las pestañas de ANÁLISIS son operables con flechas", async ({
    page,
  }) => {
    await page.goto("/auto/analisis");
    const diaD = page.getByTestId("auto-analisis-tab-dia-d");
    await expect(diaD).toBeVisible();
    await diaD.focus();
    await expect(diaD).toHaveAttribute("aria-selected", "true");

    await page.keyboard.press("ArrowRight");
    const evidencia = page.getByTestId("auto-analisis-tab-evidencia");
    await expect(evidencia).toHaveAttribute("aria-selected", "true");
    await expect(evidencia).toBeFocused();

    await page.keyboard.press("End");
    await expect(
      page.getByTestId("auto-analisis-tab-investigacion"),
    ).toBeFocused();
  });

  test("carga: el estado de carga es accesible y distinto del vacío", async ({
    page,
  }) => {
    await page.route("**/api/auto/operational-monitor", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.fallback();
    });
    await page.goto("/auto");
    await expect(page.getByTestId("auto-home-loading")).toBeVisible();
    await expect(page.getByTestId("auto-home-in-course-empty")).toHaveCount(0);
    await expectNoCriticalSerious(page, "/auto (carga)");
  });

  test("error: el fallo no se disfraza de vacío y es accesible", async ({
    page,
  }) => {
    await page.route("**/api/auto/operational-monitor", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: "{}",
      }),
    );
    await page.goto("/auto");
    await expect(page.getByTestId("auto-home-error")).toBeVisible();
    await expect(page.getByTestId("auto-home-in-course-empty")).toHaveCount(0);
    await expectNoCriticalSerious(page, "/auto (error)");
  });

  test("vacío y no-medido: se declaran y siguen siendo accesibles", async ({
    page,
  }) => {
    // Estado del motor `UNKNOWN` + ventana sin ciclos: ni un dato afirmado ni un `0` de relleno.
    await page.route("**/api/auto/operational-monitor", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          key: "auto_operational_monitor_v1",
          readOnly: true,
          accountId: "default-account-seed",
          asOf: "2026-10-06T00:00:00Z",
          header: {
            state: "UNKNOWN",
            lastDecisionAt: null,
            nextDecisionAt: null,
          },
          cycles: [],
          reservations: [],
          concurrency: {},
          notes: [],
        }),
      }),
    );
    await page.goto("/auto");
    await expect(page.getByTestId("auto-home-in-course-empty")).toBeVisible();
    await expect(page.getByTestId("auto-home-tile-auto")).toContainText(
      "Sin dato todavía",
    );
    await expectNoCriticalSerious(page, "/auto (vacío/no-medido)");
  });
});
