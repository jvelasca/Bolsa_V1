/**
 * GP-E2E UI5-0 — Wave B (verificación/responsive · regla `UI5-01`).
 *
 * Barrido `axe-core` (tags WCAG 2.0/2.1 A+AA) sobre las rutas **no-AUTO** tocadas
 * por el cierre UI 5.0 con la API mockeada: **0 violaciones `critical`/`serious`**
 * en desktop y en móvil 390×844, y **un único `main` + un único `h1`** por ruta.
 *
 *   - `/trading` (Mercado — chart workspace)
 *   - `/mesa` (Hoy)
 *   - `/mesa?view=posiciones` (Cartera)
 *   - `/confirm`
 *   - command palette (overlay abierto con Ctrl/Cmd+K en `/mesa`)
 *
 * Patrón gemelo de `gp-e2e-v28865-auto-axe-mock.spec.ts` (skip-by-default).
 * UI/read-model puro: no toca motor (`Delta motor = 0`).
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-ui5-0-axe-touched-routes-mock
 * Against an existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-ui5-0-axe
 *
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyPaperDayApiMocks,
  installLiveVirtualConfirmMocks,
  installMercadoApiMocks,
} from "./fixtures";

const DESKTOP = { width: 1366, height: 768 } as const;
const MOBILE = { width: 390, height: 844 } as const;

type RouteCase = {
  name: string;
  path: string;
  install: (page: Page) => Promise<void>;
  ready: (page: Page) => Promise<void>;
};

const ROUTES: readonly RouteCase[] = [
  {
    name: "trading",
    path: "/trading",
    install: installMercadoApiMocks,
    ready: async (page) => {
      // La cabecera de salud del terminal está siempre montada; el cockpit
      // DECISIÓN solo es visible ≥ md (hidden en 390×844).
      await expect(page.getByTestId("trading-health-strip")).toBeVisible({
        timeout: 15_000,
      });
    },
  },
  {
    name: "mesa",
    path: "/mesa",
    install: installHoyPaperDayApiMocks,
    ready: async (page) => {
      await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("hoy-inbox")).toBeVisible();
    },
  },
  {
    name: "mesa-posiciones",
    path: "/mesa?view=posiciones",
    install: installHoyPaperDayApiMocks,
    ready: async (page) => {
      await expect(page.getByTestId("hoy-view-posiciones")).toBeVisible({
        timeout: 15_000,
      });
    },
  },
  {
    name: "confirm",
    path: "/confirm",
    install: installLiveVirtualConfirmMocks,
    ready: async (page) => {
      await expect(page.getByTestId("confirm-content")).toBeVisible({
        timeout: 15_000,
      });
    },
  },
];

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

test.describe("GP-E2E UI5-0 — rutas tocadas (axe)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
  });

  // Un test por ruta × viewport: el barrido de axe excede el timeout en un único test.
  for (const route of ROUTES) {
    for (const vp of [
      { name: "desktop", ...DESKTOP },
      { name: "móvil 390×844", ...MOBILE },
    ] as const) {
      test(`0 critical/serious en ${route.path} @${vp.name}`, async ({
        page,
      }) => {
        await route.install(page);
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(route.path);
        await route.ready(page);
        await expectSingleMain(page);
        await expectSingleH1(page);
        await expectNoCriticalSerious(page, `${route.path} @${vp.name}`);
      });
    }
  }

  test("command palette: overlay accesible (Ctrl+K) con un único dialog", async ({
    page,
  }) => {
    await installHoyPaperDayApiMocks(page);
    await page.setViewportSize({
      width: DESKTOP.width,
      height: DESKTOP.height,
    });
    await page.goto("/mesa");
    await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
      timeout: 15_000,
    });

    await page.keyboard.press("ControlOrMeta+k");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toHaveCount(1);
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(page.getByRole("listbox")).toBeVisible();

    await expectNoCriticalSerious(page, "command palette @desktop");

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
});
