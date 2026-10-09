/**
 * GP-V187 — Evidencia durable PAPER, panel read-only contra API real (integrado).
 *
 * Cadena certificada: material durable (``sim_fill_finance_context`` +
 * ``decision_journal_entries``) → ``GET /api/auto/paper-evidence`` → ``useAutoPaperEvidence`` →
 * panel PAPER (P2). Sin mocks para el camino base: el panel se alimenta del endpoint real.
 *
 * Invariantes falsables:
 * - Una cuenta LEÍDA pero vacía declara ceros MEDIDOS (``data-status="unmet"``), jamás «sin dato».
 * - El veredicto reservado ``NO_CONFIRMED`` se conserva tras un reinicio real (``page.reload()``).
 * - El scope por cuenta se respeta: la cabecera ``X-Account-Id`` acota la lectura.
 * - Un hueco declarado (lectura no disponible o ventana sin fechar) se rotula «Sin dato todavía»,
 *   nunca se colapsa a un valor favorable ni a la confirmación.
 *
 * Run:
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v187
 */
import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  gateIntegratedE2eEnvironment,
  seedHoyBrowserState,
} from "./integration";

const PANEL = "paper-evidence-panel";
const CRITERION = "paper-evidence-criterion";

async function createEphemeralAccount(
  request: APIRequestContext,
  baseURL: string,
  prefix: string,
): Promise<string> {
  const suffix = Math.random().toString(36).slice(2, 10);
  const res = await request.post(new URL("/api/accounts", baseURL).toString(), {
    data: {
      name: `${prefix}-${suffix}`,
      currency: "EUR",
      initialDeposit: 100_000,
    },
  });
  if (!res.ok()) {
    throw new Error(
      `POST /api/accounts failed (${res.status()}): ${await res.text()}`,
    );
  }
  return (await res.json()).data.id as string;
}

async function gotoPaperPanel(page: Page, accountId: string) {
  await seedHoyBrowserState(page, { accountId });
  await page.goto("/auto-monitor?mode=dia-d");
  const panel = page.getByTestId(PANEL);
  await expect(panel).toBeVisible({ timeout: 20_000 });
  return panel;
}

function criterion(page: Page, id: string) {
  return page.locator(`[data-testid="${CRITERION}"][data-criterion="${id}"]`);
}

test.describe("GP-V187 — Paper evidence panel (API real)", () => {
  test.describe.configure({ mode: "serial" });

  let environmentSkip: string | null = null;
  let accountA: string | null = null;
  let accountB: string | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    accountA = await createEphemeralAccount(request, baseURL, "e2e-v187-a");
    accountB = await createEphemeralAccount(request, baseURL, "e2e-v187-b");
  });

  test.beforeEach(() => {
    if (environmentSkip) test.skip(true, environmentSkip);
    if (!accountA || !accountB) {
      throw new Error("GP-V187 fixture missing after environment gates.");
    }
  });

  test("GP-V187-01: cuenta leída y vacía declara ceros medidos, no huecos", async ({
    page,
  }) => {
    const panel = await gotoPaperPanel(page, accountA!);

    await expect(panel).toHaveAttribute("data-verdict", "NO_CONFIRMED");
    await expect(page.getByTestId("paper-evidence-verdict")).toContainText(
      "NO CONFIRMADO",
    );
    await expect(page.getByTestId(CRITERION)).toHaveCount(7);

    // Cuenta vacía PERO leída: los ceros son MEDIDOS ⇒ «Incumplido», jamás «Sin dato todavía».
    await expect(
      page.locator(`[data-testid="${CRITERION}"][data-status="unknown"]`),
    ).toHaveCount(0);
    await expect(criterion(page, "window")).toHaveAttribute(
      "data-status",
      "unmet",
    );
    await expect(criterion(page, "non_contradiction")).toHaveAttribute(
      "data-status",
      "met",
    );
  });

  test("GP-V187-02: el veredicto sobrevive a un reinicio real (reload)", async ({
    page,
  }) => {
    await gotoPaperPanel(page, accountA!);

    await page.reload();

    const panel = page.getByTestId(PANEL);
    await expect(panel).toBeVisible({ timeout: 20_000 });
    await expect(panel).toHaveAttribute("data-verdict", "NO_CONFIRMED");
    await expect(criterion(page, "non_contradiction")).toHaveAttribute(
      "data-status",
      "met",
    );
  });

  test("GP-V187-03: el scope por cuenta no se cruza entre cuentas", async ({
    page,
  }) => {
    await gotoPaperPanel(page, accountB!);

    // El detalle técnico declara la cuenta ACTIVA del scope, no la anterior.
    const detail = page.getByTestId("paper-evidence-technical");
    await detail.locator("summary").click();
    await expect(detail).toContainText(accountB!);
    await expect(detail).not.toContainText(accountA!);
  });

  test("GP-V187-04: una lectura no disponible se rotula «Sin dato todavía»", async ({
    page,
  }) => {
    // Inyecta el hueco DECLARADO del endpoint (fuente no leída): la UI no puede volverlo material.
    await page.route("**/api/auto/paper-evidence*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.reconciliation.fillsLoaded = false;
      json.reconciliation.settlementsLoaded = false;
      json.criteria = (json.criteria ?? []).map(
        (item: Record<string, unknown>) => ({
          ...item,
          counts: null,
        }),
      );
      await route.fulfill({ response, json });
    });

    await gotoPaperPanel(page, accountA!);

    await expect(page.getByTestId(PANEL)).toHaveAttribute(
      "data-verdict",
      "NO_CONFIRMED",
    );
    await expect(
      page.locator(`[data-testid="${CRITERION}"][data-status="unknown"]`),
    ).toHaveCount(7);
    await expect(
      page.locator(`[data-testid="${CRITERION}"][data-status="met"]`),
    ).toHaveCount(0);
    await expect(page.getByText("Sin dato todavía").first()).toBeVisible();
  });

  test("GP-V187-05: un dato parcial declara su hueco solo en el criterio afectado", async ({
    page,
  }) => {
    // Ventana sin fechar: el criterio de ventana es hueco; el resto sigue medido.
    await page.route("**/api/auto/paper-evidence*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.criteria = (json.criteria ?? []).map((item: { id: string }) =>
        item.id === "window"
          ? { ...item, counts: { days: null, episodes: null } }
          : item,
      );
      await route.fulfill({ response, json });
    });

    await gotoPaperPanel(page, accountA!);

    await expect(criterion(page, "window")).toHaveAttribute(
      "data-status",
      "unknown",
    );
    await expect(criterion(page, "window")).toContainText("Sin dato todavía");
    // El resto permanece medido: no se contagia el hueco ni se colapsa a 0.
    await expect(criterion(page, "non_contradiction")).toHaveAttribute(
      "data-status",
      "met",
    );
    await expect(page.getByTestId(PANEL)).toHaveAttribute(
      "data-verdict",
      "NO_CONFIRMED",
    );
  });
});
