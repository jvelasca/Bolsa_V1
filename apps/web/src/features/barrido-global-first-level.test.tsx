/**
 * UI 6.x — gate falsable de primer nivel del barrido global (`R-G1`/`RT-02`/`UI5-14`).
 *
 * Cubre las superficies que el sello `v2.88.91` declaró fuera de alcance y que este
 * barrido sí recorta:
 * - Mercado: `chart-workspace-page.tsx` + toolbar/`app-top-bar.tsx`.
 * - Laboratorio: `backtests-page.tsx` (+ pestañas).
 * - Chrome/palette: `app-top-bar.tsx` + `command-registry.ts` / `command-palette.tsx`.
 * - Barrido del comodín `—`: dashboard, cuentas, instrumentos, fiscal y screeners.
 *
 * Los identificadores TS legítimos (`runId`, `presetKey`) y las `keywords` de búsqueda no
 * son copy visible: se neutralizan antes de auditar. Los comentarios tampoco lo son.
 *
 * @see apps/web/src/components/first-level-gate.ts
 * @see docs/engineering/entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md §4
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  findFirstLevelDashes,
  findFirstLevelGateLiterals,
  findFirstLevelViolations,
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const ROOT = resolve(process.cwd(), "src");

/** Fuente sin comentarios (no son copy de usuario). */
function readSurface(relative: string): string {
  return readFileSync(resolve(ROOT, relative), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/** Identificadores TS y metadatos de búsqueda que NO son copy de primer nivel. */
function neutralizeIdentifiers(source: string): string {
  return source
    .replace(/\brunId\b/g, "identificador_interno")
    .replace(/\bpresetKey\b/g, "clave_preset")
    .replace(/\bcampaignId\b/g, "identificador_campana")
    .replace(/\bproposedBy\b/g, "propuesto_por")
    .replace(/keywords:\s*\[[^\]]*\]/g, "keywords: []");
}

/**
 * `OpportunityScore` colisiona como subcadena con el componente `OpportunityScoreBars`;
 * no aparece en estas superficies y se excluye del set por simetría con el gate de Hoy.
 */
const FIRST_LEVEL_TOKENS = FORBIDDEN_FIRST_LEVEL_TOKENS.filter(
  (token) => token !== "OpportunityScore",
);

const TOKEN_SURFACES: Array<{ name: string; file: string }> = [
  {
    name: "Mercado · chart-workspace-page.tsx",
    file: "features/charts/chart-workspace-page.tsx",
  },
  {
    name: "Mercado · app-top-bar.tsx",
    file: "components/layout/app-top-bar.tsx",
  },
  {
    name: "Laboratorio · backtests-page.tsx",
    file: "features/backtests/backtests-page.tsx",
  },
  {
    name: "Laboratorio · backtests-page-run-tab.tsx",
    file: "features/backtests/backtests-page-run-tab.tsx",
  },
  {
    name: "Laboratorio · backtests-page-jobs-tab.tsx",
    file: "features/backtests/backtests-page-jobs-tab.tsx",
  },
  {
    name: "Chrome · command-registry.ts",
    file: "features/command-palette/command-registry.ts",
  },
  {
    name: "Chrome · command-palette.tsx",
    file: "features/command-palette/command-palette.tsx",
  },
  {
    name: "Mesa · opportunity-drawer.tsx",
    file: "features/mesa/opportunity-drawer.tsx",
  },
  {
    name: "Operaciones · mesa-operational-bar.tsx",
    file: "features/operations/mesa-operational-bar.tsx",
  },
  {
    name: "Screeners · saved-strategies-panel.tsx",
    file: "features/screeners/saved-strategies-panel.tsx",
  },
  {
    name: "Screeners · paper-d-propose-panel.tsx",
    file: "features/screeners/paper-d-propose-panel.tsx",
  },
  {
    name: "AUTO · auto-no-trade-labels.ts",
    file: "features/auto/auto-no-trade-labels.ts",
  },
  {
    name: "AUTO · auto-no-trade-explanation.ts",
    file: "features/auto/auto-no-trade-explanation.ts",
  },
  {
    name: "AUTO · dia-d-evidence-aggregate-labels.ts",
    file: "features/auto-monitor/dia-d-evidence-aggregate-labels.ts",
  },
  {
    name: "AUTO · dia-d-evidence-aggregate-panel.tsx",
    file: "features/auto-monitor/dia-d-evidence-aggregate-panel.tsx",
  },
];

const DASH_SURFACES: string[] = [
  "features/dashboard/dashboard-page.tsx",
  "features/accounts/account-detail-panel.tsx",
  "features/instruments/instruments-page.tsx",
  "features/instruments/instruments-hub-detail-panel.tsx",
  "features/instruments/instrument-detail-page.tsx",
  "features/fiscal/tax-report-page.tsx",
  "features/screeners/fundamental-screener-panel.tsx",
  "features/screeners/paper-d-propose-panel.tsx",
  "features/operations/mesa-operational-bar.tsx",
  "features/mesa/mesa-daily-header.tsx",
  "features/mesa/mesa-what-if-panel.tsx",
  "features/mesa/operational-plan-view.tsx",
  "features/trading/f3-confirm-what-if-block.tsx",
  "features/trading/f3-trade-plan-risk-first-block.tsx",
  "features/trading/operator-cabin-ui.tsx",
  "features/trading/decision-surface-compact.tsx",
  "features/trading/hoy-command-strip.tsx",
  "features/trading/position-decision-surface.ts",
  "features/trading/entry-decision-surface.ts",
  // Oleada UI5-14 · zonas operativas (trading/mesa/auto-monitor)
  "features/trading/instrument-analysis-summary.tsx",
  "features/trading/instrument-db-tab.tsx",
  "features/trading/instrument-info-dialog.tsx",
  "features/trading/lists-tab/list-item-accordion.tsx",
  "features/trading/lists-tab/list-process-status-cell.tsx",
  "features/trading/lists-tab/list-sync-status-cell.tsx",
  "features/trading/lists-tab/list-hub-panel.tsx",
  "features/trading/lists-tab/visualization-log-dialog.tsx",
  "features/trading/f3-risk-signature-block.tsx",
  "features/trading/f3-exit-risk-signature-block.tsx",
  "features/trading/f3-protect-stop-block.tsx",
  "features/trading/f3-order-projection.ts",
  "features/trading/order-dialog.tsx",
  "features/trading/auto-desk-panel.tsx",
  "features/trading/trading-operativa-panel.tsx",
  "features/trading/operativa-pulse.tsx",
  "features/trading/operativa-outcomes.tsx",
  "features/trading/operativa-dictamen.tsx",
  "features/trading/mandate-timeline-panel.tsx",
  "features/trading/use-trade-notional.ts",
  "features/trading/estudio-process-status.ts",
  "features/trading/dia-d-trades-panel.tsx",
  "features/trading/dia-d-reconciliation-panel.tsx",
  "features/trading/dia-d-evidence-archive-io.ts",
  "features/trading/trading-background-sync-summary.ts",
  "features/mesa/mesa-opportunity-language.ts",
  "features/mesa/decision-spine-detail-panel.tsx",
  "features/auto-monitor/dia-d-auto-error-list.tsx",
  "features/auto-monitor/dia-d-auto-panel.tsx",
  "features/auto-monitor/dia-d-auto-feedback-panel.tsx",
  // Oleada UI5-14 · resto de features/** (charts)
  "features/charts/chart-data-status-badge.tsx",
  "features/charts/chart-database-panel.tsx",
  "features/charts/chart-instrument-zone.tsx",
  "features/charts/chart-inspector-panel.tsx",
  "features/charts/chart-indicator-template-zone.tsx",
  "features/charts/chart-analysis-score-buttons.tsx",
  "features/charts/indicator-draft-feedback.tsx",
  // Oleada UI5-14 · resto de features/** (instruments + research)
  "features/instruments/fundamental-card-panel.tsx",
  "features/instruments/composite-leg-labels.ts",
  "features/instruments/instruments-hub-trackers.ts",
  "features/instruments/instruments-hub-column-layout.ts",
  "features/research/research-lab-evidence.ts",
  "features/research/asesor-daily-ops-panel.tsx",
  "features/research/asesor-opiniones-panel.tsx",
  // Oleada UI5-14 · resto de features/** (journal/screeners/settings/config/alerts/accounts)
  "features/decision-journal/journal-studies-table.tsx",
  "features/decision-journal/decision-ficha-panel.tsx",
  "features/decision-journal/journal-evolution-panel.tsx",
  "features/screeners/tracker-alarms.ts",
  "features/screeners/strategy-draft-feedback.tsx",
  "features/screeners/fa-weekly-pipeline-panel.tsx",
  "features/settings/effectiveness-panel.tsx",
  "features/config/platform-config-dialog.tsx",
  "features/alerts/alerts-page.tsx",
  "features/alerts/signal-alerts-section.tsx",
  "features/accounts/paper-lab-evidence.ts",
  // Oleada UI5-14 · resto de features/** (backtests · helpers)
  "features/backtests/backtest-strategy-matrix.ts",
  "features/backtests/dia-d-favorites.ts",
  "features/backtests/backtest-date-format.ts",
  "features/backtests/coach-profile-policy.ts",
  "features/backtests/backtest-list-auto-board.ts",
  "features/backtests/backtest-list-member-fa.ts",
  // Oleada UI5-14 · resto de features/** (backtests · paneles)
  "features/backtests/backtest-mass-compare-panel.tsx",
  "features/backtests/backtest-ranking-table.tsx",
  "features/backtests/backtest-list-auto-board-panel.tsx",
  "features/backtests/backtest-optimize-panel.tsx",
  "features/backtests/lab-board-activity-banner.tsx",
  "features/backtests/backtest-instrument-preview.tsx",
  "features/backtests/backtest-strategy-matrix-panel.tsx",
  "features/backtests/backtest-explore-battery-table.tsx",
  "features/backtests/backtest-optimize-compare.tsx",
  "features/backtests/backtest-cursor-panel.tsx",
  "features/backtests/backtest-movie-hud.tsx",
  "features/backtests/backtest-result-detail.tsx",
  "features/backtests/strategy-monitor-panel.tsx",
  "features/backtests/backtest-result-view.tsx",
  "features/backtests/backtest-global-bar.tsx",
  "features/backtests/backtest-explore-stars-grid.tsx",
  // Oleada UI5-14 · cierres puntuales (guion embebido detectado por el gate endurecido)
  "features/trading/trading-app-threads.tsx",
  // Oleada UI5-14 · nodos JSX desnudos (detectados por el gate endurecido)
  "features/screeners/scan-results-table.tsx",
  "features/charts/indicators-catalog-dialog.tsx",
  "features/charts/chart-cursor-zone.tsx",
  // Oleada S4 · agregador de evidencia (P4 · DÍA-D)
  "features/auto-monitor/dia-d-evidence-aggregate-labels.ts",
  "features/auto-monitor/dia-d-evidence-aggregate-panel.tsx",
];

describe("barrido global · primer nivel sin jerga de ingeniería (R-G1/RT-02)", () => {
  it.each(TOKEN_SURFACES)(
    "$name no expone tokens prohibidos fuera de TechnicalDetail",
    ({ file }) => {
      const source = neutralizeIdentifiers(readSurface(file));
      expect(findFirstLevelViolations(source, FIRST_LEVEL_TOKENS)).toEqual([]);
    },
  );

  it.each(TOKEN_SURFACES)(
    "$name no usa el comodín — como dato ausente",
    ({ file }) => {
      expect(findFirstLevelDashes(readSurface(file))).toEqual([]);
    },
  );
});

describe("barrido global · comodín — sustituido por vocabulario Opción B (UI5-14)", () => {
  it.each(DASH_SURFACES)("%s no usa el literal — como dato ausente", (file) => {
    expect(findFirstLevelDashes(readSurface(file))).toEqual([]);
  });
});

describe("barrido global · control de falsabilidad del gate", () => {
  it("el gate de tokens detecta una fuga conocida", () => {
    expect(findFirstLevelViolations("<p>Recommendation · runId</p>")).toEqual(
      expect.arrayContaining(["Recommendation", "runId"]),
    );
  });
  it("el gate de guion detecta el literal y respeta prosa y nivel 3", () => {
    expect(findFirstLevelDashes('{x ?? "—"}')).toHaveLength(1);
    expect(findFirstLevelDashes("<p>Editar — Nombre</p>")).toEqual([]);
    expect(
      findFirstLevelDashes('<TechnicalDetail>{"—"}</TechnicalDetail>'),
    ).toEqual([]);
  });

  it("el gate de guion detecta el guion embebido junto al delimitador", () => {
    expect(findFirstLevelDashes('const label = "Velas · —";')).toHaveLength(1);
    expect(findFirstLevelDashes("const label = `CORE-R —`;")).toHaveLength(1);
    expect(findFirstLevelDashes('const label = "— algo";')).toHaveLength(1);
  });

  it("el gate de guion detecta el nodo JSX desnudo y respeta el placeholder de prosa", () => {
    expect(findFirstLevelDashes("<span>—</span>")).toHaveLength(1);
    expect(findFirstLevelDashes("<span>\n  —\n</span>")).toHaveLength(1);
    expect(
      findFirstLevelDashes('<option value="">— elegir —</option>'),
    ).toEqual([]);
  });

  it("stripTechnicalDetailBlocks sigue retirando el nivel 3", () => {
    expect(
      stripTechnicalDetailBlocks("<TechnicalDetail>ledger</TechnicalDetail>"),
    ).not.toContain("ledger");
  });
});

const GATE_LITERAL_SURFACES: Array<{ name: string; file: string }> = [
  ...TOKEN_SURFACES,
  ...DASH_SURFACES.map((file) => ({ name: file, file })),
];

describe("barrido global · «Gate» sin valor crudo en primer nivel (R-G1 / H-03)", () => {
  it.each(GATE_LITERAL_SURFACES)(
    "$name no muestra «Gate» + valor crudo fuera de TechnicalDetail",
    ({ file }) => {
      expect(findFirstLevelGateLiterals(readSurface(file))).toEqual([]);
    },
  );

  it("el gate de rótulo detecta la fuga y respeta identificadores y nivel 3", () => {
    expect(findFirstLevelGateLiterals("Estado · Gate ${row.gate}")).toEqual([
      "Gate ${",
    ]);
    expect(findFirstLevelGateLiterals("<p>Gate PASS</p>")).toEqual(["Gate P"]);
    expect(findFirstLevelGateLiterals("const gateStatus = row.gate;")).toEqual(
      [],
    );
    expect(findFirstLevelGateLiterals("<DecisionGate />")).toEqual([]);
    expect(
      findFirstLevelGateLiterals(
        "<TechnicalDetail>Gate ${x}</TechnicalDetail>",
      ),
    ).toEqual([]);
  });
});
