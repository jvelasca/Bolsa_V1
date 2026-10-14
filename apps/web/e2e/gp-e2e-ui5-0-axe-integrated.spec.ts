/**
 * GP-E2E UI5-0 (integrado) — barrido `axe-core` (tags WCAG 2.0/2.1 A+AA) sobre un
 * subconjunto ACOTADO de rutas L1 contra el stack REAL (FastAPI + PostgreSQL), sin
 * mocks de `/api/*`.
 *
 * Hermano INTEGRADO de `gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` (que barre las
 * rutas L1 con la API mockeada). Aquí se reutiliza el stack real: sólo se siembra lo
 * mínimo con los helpers de `e2e/integration.ts` (cuenta efímera Hoy / Mercado), sin
 * reimplementar la maquinaria de mocks.
 *
 * Rutas cubiertas (deterministas con cuenta demo/seed, ya ejercitadas por los specs
 * integrados del repo):
 *   - `/operational-console`        (patrón `gp-v164-ui`, sin seed)
 *   - `/decision-journal`           (patrón `gp-v164-ui`, sin seed)
 *   - `/mesa`                       (patrón `gp-v168-hoy`, cuenta efímera Hoy)
 *   - `/trading`                    (patrón `gp-v167-mercado`, cuenta + workspace efímeros)
 *   - `/auto-monitor?mode=current`  (patrón `gp-v187`, cuenta efímera leída)
 *
 * Cada ruta exige: 0 violaciones `critical`/`serious` (WCAG A/AA), `heading-order` sin
 * saltos, y exactamente un `main` + un `h1`.
 *
 * Skip-by-default (opt-in): `E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1`. El gate
 * `gateIntegratedE2eEnvironment` exige API sana y `E2E_ALLOW_DEV_DB=1` (los fixtures
 * mutan PG creando cuentas `e2e-*` efímeras). Sin entorno ⇒ skip declarado con motivo.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
 *
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  ensureHoyIntegrationFixture,
  ensureMercadoIntegrationFixture,
  gateIntegratedE2eEnvironment,
  seedHoyBrowserState,
  seedMercadoBrowserState,
  type HoyIntegrationFixture,
  type MercadoIntegrationFixture,
} from "./integration";

const DESKTOP = { width: 1366, height: 768 } as const;

/** Fixtures integradas compartidas (sembradas en `beforeAll`). */
type Fixtures = {
  hoy: HoyIntegrationFixture;
  mercado: MercadoIntegrationFixture;
};

/**
 * Una ruta L1 a barrer: `seed` deja la sesión del navegador lista (cuenta/workspace) y
 * `ready` espera a que la superficie esté montada antes de medir con axe.
 */
type RouteCase = {
  name: string;
  path: string;
  seed: (page: Page, fixtures: Fixtures) => Promise<void>;
  ready: (page: Page) => Promise<void>;
};

const noSeed = async () => {};

const ROUTES: readonly RouteCase[] = [
  {
    name: "operational-console",
    path: "/operational-console",
    seed: noSeed,
    ready: async (page) => {
      await expect(page.getByTestId("operational-console")).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.getByRole("heading", { level: 1, name: "Consola operacional" }),
      ).toBeVisible();
    },
  },
  {
    name: "decision-journal",
    path: "/decision-journal",
    seed: noSeed,
    ready: async (page) => {
      await expect(page.getByTestId("decision-journal")).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.getByRole("heading", { level: 1, name: "Decision Journal" }),
      ).toBeVisible();
    },
  },
  {
    name: "mesa",
    path: "/mesa",
    seed: async (page, fixtures) => {
      await seedHoyBrowserState(page, { accountId: fixtures.hoy.accountId });
    },
    ready: async (page) => {
      await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.getByTestId("hoy-inbox")).toBeVisible();
    },
  },
  {
    name: "trading",
    path: "/trading",
    seed: async (page, fixtures) => {
      const { accountId, workspaceId, workspaceDocument } = fixtures.mercado;
      await seedMercadoBrowserState(page, {
        accountId,
        workspaceId,
        workspaceDocument,
      });
    },
    ready: async (page) => {
      await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
        timeout: 20_000,
      });
    },
  },
  {
    name: "auto-monitor-current",
    path: "/auto-monitor?mode=current",
    seed: async (page, fixtures) => {
      await seedHoyBrowserState(page, { accountId: fixtures.hoy.accountId });
    },
    ready: async (page) => {
      await expect(page.getByTestId("auto-monitor-page")).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.getByRole("heading", { level: 1, name: "Monitor AUTO" }),
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
 * `heading-order` (best-practice) no pertenece a los tags WCAG: se pide explícitamente.
 * Exige jerarquía `h1→h2→h3` sin saltos en las rutas L1 tocadas (deuda UI 6.x).
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

/** El host keep-alive de `PlatformShell` (oculto) queda excluido: no es el `main` visible. */
async function expectSingleMain(page: Page) {
  await expect(
    page.locator("main:not([data-testid='backtests-keepalive-host'])"),
  ).toHaveCount(1);
}

async function expectSingleH1(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
}

test.describe("GP-E2E UI5-0 — rutas L1 integradas (axe, API real)", () => {
  // El seed integrado (cuentas + workspace) y el arranque en frío de Vite en CI exceden el
  // timeout por defecto de 30 s; se da margen sin volver el barrido lento en local.
  test.describe.configure({ timeout: 120_000 });

  let environmentSkip: string | null = null;
  let fixtures: Fixtures | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    // Un mínimo de seed para las rutas que no caen sobre la cuenta demo por defecto.
    const hoy = await ensureHoyIntegrationFixture(request, baseURL);
    const mercado = await ensureMercadoIntegrationFixture(request, baseURL);
    fixtures = { hoy, mercado };
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      test.skip(true, environmentSkip);
    }
    if (!fixtures) {
      throw new Error(
        "Fixtures integradas ausentes tras los gates de entorno (fallo de producto).",
      );
    }
  });

  // Un test por ruta: el barrido de axe con `main`+`h1`+`heading-order` excede el timeout
  // si se acumula en un único test.
  for (const route of ROUTES) {
    test(`0 critical/serious + heading-order en ${route.path} @desktop`, async ({
      page,
    }) => {
      const ctx = fixtures;
      if (!ctx) throw new Error("fixtures required");

      await route.seed(page, ctx);
      await page.setViewportSize({
        width: DESKTOP.width,
        height: DESKTOP.height,
      });
      await page.goto(route.path);
      await route.ready(page);
      await expectSingleMain(page);
      await expectSingleH1(page);
      await expectNoHeadingOrderViolations(page, `${route.path} @desktop`);
      await expectNoCriticalSerious(page, `${route.path} @desktop`);
    });
  }
});
