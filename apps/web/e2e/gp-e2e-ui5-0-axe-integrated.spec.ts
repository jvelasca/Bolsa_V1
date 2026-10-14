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
 *   - `/operational-console`        (sin seed)
 *   - `/decision-journal`           (sin seed)
 *   - `/mesa`                       (cuenta efímera Hoy)
 *   - `/mesa?view=posiciones`       (cuenta efímera Hoy — Cartera)
 *   - `/trading`                    (cuenta + workspace efímeros)
 *   - `/auto-monitor?mode=current`  (cuenta efímera Hoy leída)
 *   - `/overview`                   (sin seed)
 *   - `/accounts`                   (sin seed)
 *   - `/fiscal`                     (sin seed)
 *   - `/screeners`                  (sin seed)
 *   - `/alerts`                     (sin seed)
 *   - `/research`                   (sin seed)
 *   - `/history`                    (sin seed)
 *   - `/backtests`                  (sin seed — `main` = host keep-alive del shell)
 *   - `/instruments`                (sin seed — catálogo real)
 *   - `/instruments/:id`            (id real del catálogo vía fixture Mercado)
 *
 * Ampliación 2026-10-14 (deuda «axe integrado desktop-only / acotado»): este barrido era
 * **desktop-only** (1366×768) y acotado a 5 rutas. Ahora se barre cada ruta en **desktop y
 * móvil 390×844**, y se suman las rutas L1 alcanzables contra el stack real (mismo censo
 * que el barrido mock, sin los `install*Mocks`: `/overview`, `/accounts`, `/fiscal`,
 * `/screeners`, `/alerts`, `/research`, `/history`, `/backtests`, `/mesa?view=posiciones`,
 * `/instruments` e `/instruments/:id`).
 * Las rutas que NO son alcanzables de forma determinista contra el stack real (p. ej.
 * `/confirm`, que exige una cola F3 sembrada) quedan declaradas como límite, no mockeadas
 * dentro de este spec integrado.
 *
 * Cada ruta exige: 0 violaciones `critical`/`serious` (WCAG A/AA), `heading-order` sin
 * saltos, y exactamente un `main` + un `h1`.
 *
 * Skip-by-default (opt-in): `E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1`. El gate
 * `gateIntegratedE2eEnvironment` exige API sana y `E2E_ALLOW_DEV_DB=1` (los fixtures
 * mutan PG creando cuentas `e2e-*` efímeras). Sin entorno ⇒ skip declarado con motivo.
 *
 * Modo REQUERIDO (GATE DURO del tag) — `E2E_AXE_REQUIRED=1`:
 *   espeja el patrón `E2E_S5_REQUIRED` del puente AUTO S5 (`gp-v288-s5-...-integrated.spec.ts`).
 *   Convierte en **FALLO** (no `skipped`) CUALQUIER precondición ausente —entorno integrado no
 *   disponible y/o fixtures/rutas no alcanzables— para que un skip mudo NO pueda dar verde.
 *   Se usa en el job `playwright-integrated-axe` de `.github/workflows/release-tag-ci.yml`,
 *   que es gate DURO de cada push de tag (está en `certify.needs`). Sin ese modo, `skipped`
 *   sigue siendo un skip declarado con motivo.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 \
 *     pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
 * Modo CI del tag (precondición = fallo, no skip):
 *   E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 E2E_AXE_REQUIRED=1 \
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
const MOBILE = { width: 390, height: 844 } as const;

/** Viewports barridos: la deuda «axe integrado desktop-only» se cierra añadiendo móvil. */
const VIEWPORTS = [
  { name: "desktop", ...DESKTOP },
  { name: "móvil 390×844", ...MOBILE },
] as const;

type Viewport = (typeof VIEWPORTS)[number];

/** Fixtures integradas compartidas (sembradas en `beforeAll`). */
type Fixtures = {
  hoy: HoyIntegrationFixture;
  mercado: MercadoIntegrationFixture;
};

/**
 * Una ruta L1 a barrer: `seed` deja la sesión del navegador lista (cuenta/workspace) y
 * `ready` espera a que la superficie esté montada antes de medir con axe. `pathFor` (opt.)
 * resuelve el path con las fixtures (p. ej. `/instruments/:id`). `expectMain` (opt.)
 * sustituye la aserción de `main` por defecto (host keep-alive de `/backtests`).
 */
type RouteCase = {
  name: string;
  path: string;
  pathFor?: (fixtures: Fixtures) => string;
  seed: (page: Page, fixtures: Fixtures) => Promise<void>;
  ready: (page: Page, vp: Viewport) => Promise<void>;
  expectMain?: (page: Page) => Promise<void>;
};

const noSeed = async () => {};

/**
 * `E2E_AXE_REQUIRED=1` (GATE DURO del tag): cualquier precondición ausente se convierte en
 * **FALLO**, no en `skipped` — espejo de `s5Required()` del puente AUTO S5. Así un entorno
 * no disponible (o unos fixtures/rutas no alcanzables) NO puede dar verde por skip mudo.
 */
function axeRequired(): boolean {
  return process.env.E2E_AXE_REQUIRED === "1";
}

/**
 * Declara un hueco de precondición: `skipped` con motivo por defecto, o **FALLO** si el run
 * exige el barrido (`E2E_AXE_REQUIRED=1`, CI del tag) — un skip no puede dar verde.
 */
function declareGap(reason: string): void {
  if (axeRequired()) {
    throw new Error(
      `E2E_AXE_REQUIRED=1: precondición del barrido axe integrado ausente — ${reason}`,
    );
  }
  test.skip(true, reason);
}

/** Espera al `h1` accesible de la página (señal de que la superficie ya montó). */
async function expectH1(page: Page, name: string) {
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible({
    timeout: 20_000,
  });
}

const ROUTES: readonly RouteCase[] = [
  {
    name: "operational-console",
    path: "/operational-console",
    seed: noSeed,
    ready: async (page) => {
      await expect(page.getByTestId("operational-console")).toBeVisible({
        timeout: 20_000,
      });
      await expectH1(page, "Consola operacional");
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
      await expectH1(page, "Decision Journal");
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
    name: "mesa-posiciones",
    path: "/mesa?view=posiciones",
    seed: async (page, fixtures) => {
      await seedHoyBrowserState(page, { accountId: fixtures.hoy.accountId });
    },
    ready: async (page) => {
      await expect(page.getByTestId("hoy-view-posiciones")).toBeVisible({
        timeout: 20_000,
      });
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
    ready: async (page, vp) => {
      // La tira de salud del terminal está montada siempre; el cockpit DECISIÓN
      // solo es visible ≥ md (oculto en 390×844).
      await expect(page.getByTestId("trading-health-strip")).toBeVisible({
        timeout: 20_000,
      });
      if (vp.width >= 768) {
        await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
          timeout: 20_000,
        });
      }
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
      await expectH1(page, "Monitor AUTO");
    },
  },
  // --- Rutas L1 adicionales (censo del barrido mock) alcanzables contra el stack real ---
  {
    name: "overview",
    path: "/overview",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Overview");
    },
  },
  {
    name: "accounts",
    path: "/accounts",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Cuentas");
    },
  },
  {
    name: "fiscal",
    path: "/fiscal",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Informe fiscal");
    },
  },
  {
    name: "screeners",
    path: "/screeners",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Señales");
    },
  },
  {
    name: "alerts",
    path: "/alerts",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Alertas de precio");
    },
  },
  {
    name: "research",
    path: "/research",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Asesor");
    },
  },
  {
    name: "history",
    path: "/history",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Historial");
    },
  },
  {
    name: "backtests",
    path: "/backtests",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Laboratorio");
    },
    // El `main` de `/backtests` ES el host keep-alive del shell: se cuenta en vez de excluirlo.
    expectMain: expectSingleMainIncludingKeepAlive,
  },
  {
    name: "instruments",
    path: "/instruments",
    seed: noSeed,
    ready: async (page) => {
      await expectH1(page, "Instrumentos");
    },
  },
  {
    name: "instruments-detail",
    path: "/instruments/:id",
    pathFor: (fixtures) => `/instruments/${fixtures.mercado.instrumentId}`,
    seed: noSeed,
    // El `h1` de la ficha del instrumento se monta cuando el instrumento ya cargó.
    ready: async (page) => {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
        timeout: 20_000,
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
      // En modo requerido (GATE DURO del tag) un entorno no disponible es FAIL, no skip.
      declareGap(environmentSkip);
      return;
    }
    if (!fixtures) {
      // Fixtures no alcanzables: FALLO (no hay camino de skip: sin fixtures no hay barrido).
      throw new Error(
        axeRequired()
          ? "E2E_AXE_REQUIRED=1: fixtures integradas no alcanzables tras los gates de entorno."
          : "Fixtures integradas ausentes tras los gates de entorno (fallo de producto).",
      );
    }
  });

  // Un test por ruta × viewport: el barrido de axe con `main`+`h1`+`heading-order` excede
  // el timeout si se acumula en un único test.
  for (const route of ROUTES) {
    for (const vp of VIEWPORTS) {
      test(`0 critical/serious + heading-order en ${route.path} @${vp.name}`, async ({
        page,
      }) => {
        const ctx = fixtures;
        if (!ctx) throw new Error("fixtures required");

        await route.seed(page, ctx);
        await page.setViewportSize({ width: vp.width, height: vp.height });
        const path = route.pathFor ? route.pathFor(ctx) : route.path;
        await page.goto(path);
        await route.ready(page, vp);
        await (route.expectMain ?? expectSingleMain)(page);
        await expectSingleH1(page);
        await expectNoHeadingOrderViolations(page, `${path} @${vp.name}`);
        await expectNoCriticalSerious(page, `${path} @${vp.name}`);
      });
    }
  }
});
