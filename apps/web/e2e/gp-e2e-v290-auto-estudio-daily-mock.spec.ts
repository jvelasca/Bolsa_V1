/**
 * E5 — recorrido mock de la operativa diaria AUTO por valor.
 *
 * Cubre el circuito completo con la API simulada (sin stack Python):
 *   ESTUDIO (parte durable) → señal + decisión por valor → «Calcular operativa diaria»
 *   (job de la cola durable, progreso y desenlace) → «Ejecutar DÍA-D ahora» → artefacto.
 * Además, los dos modos de fallo que no deben parecer «sin datos»: API caída y parte ausente.
 *
 * Run (auto-starts Vite):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v290
 *
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installAutoDailyFlowMocks,
} from "./fixtures";

const ESTUDIO_DAILY_JOB_ID = "e2e-estudio-daily-job";
const DIA_D_JOB_ID = "e2e-dia-d-job";

function jobDto(input: {
  id: string;
  kind: string;
  day: string;
  status: string;
  phase?: string;
  percent?: number;
}) {
  return {
    id: input.id,
    kind: input.kind,
    status: input.status,
    day: input.day,
    accountId: "default-account-seed",
    payload: {},
    progress:
      input.phase === undefined
        ? {}
        : {
            phase: input.phase,
            done: 1,
            total: 2,
            percent: input.percent ?? 50,
          },
    result: {},
    error: null,
    attempt: 1,
    createdAt: "2026-10-18T20:00:00+00:00",
    startedAt: "2026-10-18T20:00:01+00:00",
    finishedAt: null,
    heartbeatAt: "2026-10-18T20:00:02+00:00",
  };
}

/** Progreso determinista: el primer GET declara `running`; el siguiente, `completed`. */
async function installJobPolling(page: Page, jobId: string, kind: string) {
  let polls = 0;
  await page.route(`**/api/auto/ops-jobs/${jobId}`, async (route) => {
    polls += 1;
    const body =
      polls === 1
        ? jobDto({
            id: jobId,
            kind,
            day: "2026-10-18",
            status: "running",
            phase: kind === "dia_d_replay" ? "replay" : "opinions",
            percent: 40,
          })
        : jobDto({
            id: jobId,
            kind,
            day: "2026-10-18",
            status: "completed",
          });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

test.describe("GP-E2E-V290 — operativa diaria AUTO por valor (mock)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installAutoDailyFlowMocks(page);
  });

  test("parte por valor: cuatro estados separados y huecos explícitos", async ({
    page,
  }) => {
    await page.goto("/auto-monitor?mode=daily");

    const panel = page.getByTestId("estudio-daily-ops-panel");
    await expect(panel).toBeVisible();
    // La pestaña «Operativa diaria» es la activa del toolbar.
    await expect(page.getByTestId("auto-monitor-mode-daily")).toHaveAttribute(
      "aria-selected",
      "true",
    );

    const values = page.getByTestId("estudio-daily-value");
    await expect(values).toHaveCount(2);
    await expect(page.getByTestId("estudio-daily-counts")).toContainText(
      "2 valores",
    );

    const aapl = page.locator(
      "[data-testid='estudio-daily-value'][data-symbol='AAPL']",
    );
    await expect(aapl).toHaveAttribute("data-status", "ok");
    // 1 · señal calculada.
    await expect(aapl.getByTestId("estudio-daily-value-signal")).toContainText(
      "4★",
    );
    // 2 · decisión tomada: SOLO niveles del TradePlan.
    await expect(aapl.getByTestId("estudio-daily-value-plan")).toContainText(
      "192.40",
    );
    await expect(aapl.getByTestId("estudio-daily-value-plan")).toContainText(
      "191.40",
    );
    // `target2` ausente ⇒ «Sin dato todavía», nunca 0.
    await expect(aapl.getByTestId("estudio-daily-value-plan")).toContainText(
      "Sin dato todavía",
    );
    // 3 · operación ejecutada: ciclo durable del audit.
    await expect(aapl.getByTestId("estudio-daily-value-cycle")).toHaveCount(1);
    // 4 · operativa validada: K/expectancy/veredicto OOS.
    await expect(
      aapl.getByTestId("estudio-daily-value-validation"),
    ).toContainText("K=8");
    await expect(
      aapl.getByTestId("estudio-daily-value-validation"),
    ).toContainText("MIXED");

    const gap = page.locator(
      "[data-testid='estudio-daily-value'][data-symbol='GAP']",
    );
    await expect(gap).toHaveAttribute("data-status", "no_plan");
    await expect(gap.getByTestId("estudio-daily-value-whynot")).toContainText(
      "gap_risk",
    );
    await expect(
      gap.getByTestId("estudio-daily-value-validation-absent"),
    ).toContainText("Sin dato todavía");

    // La ventana PAPER no se confunde con la validación por valor: publica el veredicto que
    // el gate declaró en el DTO de auditoría (O-4), no una constante de la vista.
    const windowVerdict = page.getByTestId("estudio-daily-global-validation");
    await expect(windowVerdict).toHaveAttribute("data-verdict", "MIXED");
    await expect(windowVerdict).toContainText("MIXED");
    await expect(windowVerdict).toContainText(
      "1 de 1 valores con veredicto medido en el gate",
    );
    // La vista sigue sin emitir el sello de OPERACIÓN.
    await expect(windowVerdict).toContainText("no emite");
    await expect(windowVerdict).toContainText("CONFIRMED");
    await expect(windowVerdict).not.toContainText("INCONCLUSIVE");
  });

  test("calcular operativa encola el job y muestra progreso y desenlace", async ({
    page,
  }) => {
    await installJobPolling(page, ESTUDIO_DAILY_JOB_ID, "estudio_daily");
    await page.goto("/auto-monitor?mode=daily");
    await expect(page.getByTestId("estudio-daily-value")).toHaveCount(2);

    await page.getByTestId("estudio-daily-run").click();

    await expect(page.getByTestId("estudio-daily-job-progress")).toBeVisible();
    await expect(page.getByTestId("estudio-daily-job-progress")).toContainText(
      "Fase opinions",
    );
    await expect(page.getByTestId("estudio-daily-job-status")).toHaveAttribute(
      "data-status",
      "completed",
    );
    // El parte durable sigue visible tras completar (no se vacía).
    await expect(page.getByTestId("estudio-daily-value")).toHaveCount(2);
  });

  test("DÍA-D manual: el botón encola el replay y conserva el artefacto", async ({
    page,
  }) => {
    await installJobPolling(page, DIA_D_JOB_ID, "dia_d_replay");
    await page.goto("/auto-monitor?mode=dia-d");

    await expect(page.getByTestId("dia-d-auto-days")).toContainText(
      "2026-09-30",
    );
    await expect(page.getByTestId("dia-d-auto-steps")).toBeVisible();

    const run = page.getByTestId("dia-d-auto-run");
    await expect(run).toBeEnabled();
    await run.click();

    await expect(page.getByTestId("dia-d-auto-job-progress")).toContainText(
      "Fase replay",
    );
    await expect(page.getByTestId("dia-d-auto-job-status")).toHaveAttribute(
      "data-status",
      "completed",
    );
    // El artefacto anterior sigue visible y etiquetado.
    await expect(page.getByTestId("dia-d-auto-steps")).toBeVisible();
    await expect(page.getByTestId("dia-d-auto-summary")).toContainText(
      "match 1",
    );
  });

  test("un fallo de la API no se pinta como «sin datos»", async ({ page }) => {
    await page.route("**/api/auto/estudio-daily*", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "api caída" }),
      });
    });

    await page.goto("/auto-monitor?mode=daily");

    await expect(page.getByTestId("estudio-daily-error")).toBeVisible();
    await expect(page.getByTestId("estudio-daily-error")).toHaveAttribute(
      "role",
      "alert",
    );
    await expect(page.getByTestId("estudio-daily-error")).toContainText(
      "api caída",
    );
    await expect(page.getByTestId("estudio-daily-empty")).toHaveCount(0);
  });

  test("sin parte calculado se declara «Sin dato todavía»", async ({
    page,
  }) => {
    await page.route("**/api/auto/estudio-daily*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          asOf: "2026-10-18",
          accountId: "default-account-seed",
          job: null,
          latestJob: null,
          report: null,
          notes: ["no_job_for_day"],
        }),
      });
    });

    await page.goto("/auto-monitor?mode=daily");

    await expect(page.getByTestId("estudio-daily-empty")).toContainText(
      "Sin dato todavía",
    );
    await expect(page.getByTestId("estudio-daily-value")).toHaveCount(0);
  });
});
