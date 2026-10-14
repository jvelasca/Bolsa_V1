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
 * UI 6.x — deuda `heading-order` (best-practice): se añaden las rutas L1 del censo
 * (`/overview`, `/backtests`, `/accounts`, `/screeners`, `/alerts`, `/fiscal`,
 * `/operational-console`, `/auto-monitor`) al mismo barrido; `expectNoHeadingOrderViolations`
 * exige jerarquía `h1→h2→h3` sin saltos en ellas.
 *
 * Ampliación 2026-10-14 (cobertura mock COMPLETA): se suman las rutas L1 del censo que aún
 * no barría este spec — `/instruments`, `/instruments/:id` y `/decision-journal`. Con ellas
 * el censo **no-AUTO** queda cubierto al completo (el espacio AUTO tiene su propio barrido
 * `gp-e2e-v28865-auto-axe-mock.spec.ts`). Además se rellenó el `meta`
 * (`priceSummary`/`lastSync`) del mock de instrumento suelto: sin él `/instruments/:id`
 * reventaba en el error boundary y el barrido nunca veía su jerarquía real.
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
  installApiMocks,
  installHoyPaperDayApiMocks,
  installLiveVirtualConfirmMocks,
  installMercadoApiMocks,
  installAutoWorkspaceMocks,
} from "./fixtures";
import { E2E_INSTRUMENT_ID } from "./integration";

const DESKTOP = { width: 1366, height: 768 } as const;
const MOBILE = { width: 390, height: 844 } as const;

type RouteCase = {
  name: string;
  path: string;
  install: (page: Page) => Promise<void>;
  ready: (page: Page) => Promise<void>;
  /**
   * Sustituye la aserción de `main` por defecto. `/backtests` monta su contenido en el host
   * keep-alive de `PlatformShell` (`data-testid="backtests-keepalive-host"`), que ES su `main`:
   * el helper genérico lo excluye y resolvería a 0.
   */
  expectMain?: (page: Page) => Promise<void>;
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
  {
    name: "asesor",
    path: "/research",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Asesor" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "historial",
    path: "/history",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Historial" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  // UI 6.x — deuda `heading-order`: rutas L1 con `<h1>` + cards que saltaban a `h3`.
  // Cubren el fix (`CardTitle level="h2"`) por el mismo barrido axe que el resto.
  {
    name: "overview",
    path: "/overview",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Overview" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "backtests",
    path: "/backtests",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Laboratorio" }),
      ).toBeVisible({ timeout: 15_000 });
    },
    // El `main` de `/backtests` es el host keep-alive del shell: se cuenta en vez de excluirlo.
    expectMain: expectSingleMainIncludingKeepAlive,
  },
  {
    name: "accounts",
    path: "/accounts",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Cuentas" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "screeners",
    path: "/screeners",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Señales" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "alerts",
    path: "/alerts",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Alertas de precio" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "fiscal",
    path: "/fiscal",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Informe fiscal" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "operational-console",
    path: "/operational-console",
    install: installApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Consola operacional" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "auto-monitor",
    path: "/auto-monitor",
    install: installAutoWorkspaceMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Monitor AUTO" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  // Cobertura mock COMPLETA — rutas L1 que aún no barría este spec (el resto del censo
  // no-AUTO ya estaba cubierto; el espacio AUTO tiene su propio barrido `gp-e2e-v28865`).
  {
    name: "instruments",
    path: "/instruments",
    install: installMercadoApiMocks,
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Instrumentos" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "instruments-detail",
    path: `/instruments/${E2E_INSTRUMENT_ID}`,
    install: installMercadoApiMocks,
    ready: async (page) => {
      // La ficha monta su `h1` (símbolo + nombre) cuando el instrumento cargó.
      await expect(
        page.getByRole("heading", { level: 1, name: "AAPL" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "decision-journal",
    path: "/decision-journal",
    install: installApiMocks,
    ready: async (page) => {
      await expect(page.getByTestId("decision-journal")).toBeVisible({
        timeout: 15_000,
      });
      await expect(
        page.getByRole("heading", { level: 1, name: "Decision Journal" }),
      ).toBeVisible();
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

/**
 * UI 6.x — deuda `heading-order` (best-practice). Exige jerarquía `h1→h2→h3` sin saltos
 * en las rutas L1 tocadas. `heading-order` no pertenece a los tags WCAG, por eso se pide
 * explícitamente con `withRules`.
 */
async function expectNoHeadingOrderViolations(page: Page, context: string) {
  const results = await new AxeBuilder({ page })
    .withRules(["heading-order"])
    .analyze();
  const detail = results.violations
    .map(
      (violation) =>
        `· ${violation.id} ×${violation.nodes.length} — ${violation.help}\n    ${violation.nodes
          .slice(0, 6)
          .map(
            (node) =>
              `${node.target.join(" ")} :: ${(node.html ?? "").slice(0, 120)}`,
          )
          .join("\n    ")}`,
    )
    .join("\n");
  expect(results.violations, `[${context}] ${detail}`).toEqual([]);
}

async function expectSingleMain(page: Page) {
  await expect(
    page.locator("main:not([data-testid='backtests-keepalive-host'])"),
  ).toHaveCount(1);
}

/**
 * `/backtests` — su `main` ES el host keep-alive de `PlatformShell`, así que aquí se cuenta
 * (a diferencia de `expectSingleMain`, que lo excluye porque en otras rutas puede estar montado
 * oculto). El requisito de accesibilidad es el mismo: exactamente un `main` en el documento.
 */
async function expectSingleMainIncludingKeepAlive(page: Page) {
  await expect(page.locator("main")).toHaveCount(1);
}

async function expectSingleH1(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
}

test.describe("GP-E2E UI5-0 — rutas tocadas (axe)", () => {
  test.beforeEach(async () => {
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
        await (route.expectMain ?? expectSingleMain)(page);
        await expectSingleH1(page);
        await expectNoHeadingOrderViolations(page, `${route.path} @${vp.name}`);
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
