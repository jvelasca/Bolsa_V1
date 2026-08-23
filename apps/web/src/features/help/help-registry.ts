/**
 * Índice de coordinación Ayuda ↔ trackers ↔ docs.
 *
 * Regla: el contenido de seguimiento/info en Ayuda NO se escribe a mano en el menú;
 * sale de los trackers listados aquí. Al cambiar estado, actualiza el tracker + el doc
 * enlazado (misma fecha `HELP_CONTENT_AS_OF`).
 *
 * @see docs/HELP.md
 */

import { HELP_CONTENT_AS_OF as HELP_CONTENT_AS_OF_SOURCE } from "@/features/help/help-content-as-of";
import { AI_TRACKER_SYNC } from "@/features/settings/ai-platform-tracker";

/** Reexport: fuente única en `help-content-as-of.ts`. */
export const HELP_CONTENT_AS_OF = HELP_CONTENT_AS_OF_SOURCE;

export type HelpRegistrySectionId =
  | "guide"
  | "workflow"
  | "accounts"
  | "trading"
  | "watchlist"
  | "value-analysis"
  | "backtesting"
  | "ai"
  | "data"
  | "charts-status"
  | "fiscal"
  | "about";

export interface HelpSourceRef {
  /** Ruta repo (docs o código). */
  path: string;
  /** Rol del fichero. */
  role: "tracker" | "doc" | "adr" | "rfc" | "code";
  note?: string;
}

export interface HelpSectionMeta {
  id: HelpRegistrySectionId;
  label: string;
  kind: "guide" | "tracking" | "about";
  /** Fuentes que alimentan esta sección (orden: tracker primero). */
  sources: HelpSourceRef[];
}

/**
 * Mapa canónico. Si añades una sección de seguimiento en Ayuda, regístrala aquí
 * y apunta a un `*-tracker.ts` (no copies el texto solo en el JSX del menú).
 */
export const HELP_SECTIONS: HelpSectionMeta[] = [
  {
    id: "guide",
    label: "Guía de la aplicación",
    kind: "guide",
    sources: [
      { path: "docs/HELP.md", role: "doc", note: "Mapa Ayuda ↔ trackers" },
      { path: "docs/ONBOARDING.md", role: "doc" },
      { path: "docs/UI_PLATFORM.md", role: "doc" },
    ],
  },
  {
    id: "workflow",
    label: "Flujo y módulos",
    kind: "guide",
    sources: [
      {
        path: "docs/engineering/research-lifecycle.md",
        role: "doc",
        note: "Flujo operativo LAB → trading",
      },
      {
        path: "docs/adr/019-dual-universes-lab-vs-trading.md",
        role: "adr",
        note: "LAB ≠ TRADING",
      },
      {
        path: "docs/engineering/dual-universes-lab-trading-design-2026-08-02.md",
        role: "doc",
        note: "Diseño universos UI",
      },
      {
        path: "docs/domain-language.md",
        role: "doc",
        note: "Términos y universos",
      },
      { path: "docs/ARCHITECTURE.md", role: "doc", note: "Capas monorepo" },
      { path: "docs/README.md", role: "doc", note: "Índice documentación" },
      {
        path: "docs/engineering/demo-operating-modes-brief-2026-08-03.md",
        role: "doc",
        note: "MANUAL / SEMI / AUTO",
      },
    ],
  },
  {
    id: "accounts",
    label: "Cuentas y efectivo",
    kind: "guide",
    sources: [
      {
        path: "docs/engineering/account-premises-demo-vs-paper-2026-07-31.md",
        role: "doc",
        note: "Premisa: Activa · DEMO hoy · Paper = broker futuro",
      },
      { path: "docs/PORTFOLIO_AND_CASH.md", role: "doc" },
      {
        path: "docs/DATA_MODEL.md",
        role: "doc",
        note: "investment_accounts types",
      },
      { path: "apps/web/src/features/accounts/", role: "code" },
    ],
  },
  {
    id: "trading",
    label: "Trading y gráficos",
    kind: "guide",
    sources: [
      { path: "docs/CHART_DATA_BAR.md", role: "doc" },
      {
        path: "docs/engineering/research-radar-unification-2026-07-31.md",
        role: "doc",
        note: "§3b Inbox · poller on_bar_close · F3 desde alarma",
      },
      {
        path: "docs/engineering/instruments-hub-2026-07-31.md",
        role: "doc",
        note: "Hub Instrumentos I0–I3 · Seguimiento = Radar (chips/Activar)",
      },
      {
        path: "docs/adr/019-dual-universes-lab-vs-trading.md",
        role: "adr",
        note: "LAB ≠ TRADING · panel Operativa",
      },
      {
        path: "docs/adr/020-operating-mandate-tenure.md",
        role: "adr",
        note: "Mandato operativo · tenure · trades enlazados",
      },
      {
        path: "docs/engineering/trading-operativa-panel-2026-08-04.md",
        role: "doc",
        note: "Operativa full-height · IO · modos en barra/Cuentas",
      },
      {
        path: "docs/adr/024-estudio-supervision-universe.md",
        role: "adr",
        note: "Universo Estudio · Supervisión ON · 3 capas",
      },
      {
        path: "docs/engineering/estudio-supervision-model-2026-08-06.md",
        role: "doc",
        note: "Modelo supervisión · cadencias · unsubscribe",
      },
      {
        path: "docs/engineering/estudio-process-status-ui-2026-08-06.md",
        role: "doc",
        note: "Iconos V·F·R · Actualizar/Redescubrir · OPERATIVA barra",
      },
      {
        path: "docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md",
        role: "doc",
        note: "Handoff UI procesos (retomar agente)",
      },
      {
        path: "docs/engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md",
        role: "doc",
        note: "Prep AUTO A0–A5 · flag off · SEMI OK",
      },
      {
        path: "docs/adr/023-camino-d-thaw.md",
        role: "adr",
        note: "Thaw Camino D · Proposed · evidencia ☐",
      },
      {
        path: "docs/engineering/risk-engine-or-re-2026-08-04.md",
        role: "doc",
        note: "Risk Engine check_opening · kill switch",
      },
      {
        path: "apps/web/src/features/trading/demo-book-mode-panel.tsx",
        role: "code",
        note: "MANUAL/SEMI · AUTO No disponible (BETA) · kill (Cuentas)",
      },
      {
        path: "apps/web/src/features/trading/trading-status-bar.tsx",
        role: "code",
        note: "Badge OPERATIVA · enlace Cuentas",
      },
      {
        path: "apps/web/src/features/trading/estudio-supervision-panel.tsx",
        role: "code",
        note: "Banner Supervisión · chips cadencia V·F·R",
      },
      {
        path: "apps/web/src/features/trading/estudio-process-status.ts",
        role: "code",
        note: "Estados capas · summarize subtítulo",
      },
      {
        path: "docs/engineering/chart-top1-indicator-switch-2026-08-03.md",
        role: "doc",
        note: "Finalista #1 · todos / este",
      },
      {
        path: "apps/web/src/features/trading/trading-operativa-panel.tsx",
        role: "code",
      },
      {
        path: "apps/web/src/features/platform/operating-mandate.ts",
        role: "code",
      },
      {
        path: "docs/engineering/account-premises-demo-vs-paper-2026-07-31.md",
        role: "doc",
        note: "Cuenta activa DEMO",
      },
      {
        path: "docs/WORKSPACE_PERSISTENCE.md",
        role: "doc",
        note: "Chip / gestor / arranque / capas",
      },
      { path: "docs/CONFIGURATION_MODEL.md", role: "doc" },
      { path: "docs/PERFORMANCE.md", role: "doc" },
      { path: "docs/HYBRID_TRACKERS.md", role: "doc" },
      {
        path: "apps/web/src/features/workspace/workspace-picker-dialog.tsx",
        role: "code",
      },
      { path: "apps/web/src/stores/workspace-store.ts", role: "code" },
    ],
  },
  {
    id: "watchlist",
    label: "Watchlist (Listas / Valores)",
    kind: "tracking",
    sources: [
      {
        path: "docs/adr/024-estudio-supervision-universe.md",
        role: "adr",
        note: "Estudio API · Supervisión · Eliminar de la lista",
      },
      {
        path: "docs/engineering/visualizados-list-ux-2026-08-06.md",
        role: "doc",
        note: "Visualizados = pestañas · Por IO · columnas · foco lista",
      },
      {
        path: "docs/engineering/session-handoff-2026-08-06-visualizados-list-ux.md",
        role: "doc",
        note: "Handoff agente Visualizados / listas UX",
      },
      {
        path: "docs/engineering/estudio-process-status-ui-2026-08-06.md",
        role: "doc",
        note: "Actualizar / Redescubrir · subtítulo procesos",
      },
      {
        path: "apps/web/src/features/trading/lists-tab/list-values-panel.tsx",
        role: "code",
        note: "Valores · Visualizados · Por IO · foco Cartera→Estudio",
      },
      {
        path: "apps/web/src/features/settings/watchlist-lists-tracker.ts",
        role: "tracker",
        note: "Listas / Índices / Personales · suscribir · congelar · carrusel",
      },
      {
        path: "docs/engineering/lists-universes-design-2026-07-30.md",
        role: "doc",
        note: "Diseño A→B→C · v1.0 cerrado",
      },
      {
        path: "docs/WORKSPACE_PERSISTENCE.md",
        role: "doc",
        note: "carouselListIds / persistencia",
      },
      {
        path: "docs/MARKET_DATA.md",
        role: "doc",
        note: "Ciclo de vida listas↔BD",
      },
      {
        path: "apps/web/src/features/trading/lists-tab/watchlist-panel.tsx",
        role: "code",
      },
    ],
  },
  {
    id: "value-analysis",
    label: "Análisis del valor",
    kind: "guide",
    sources: [
      {
        path: "apps/web/src/features/settings/value-analysis-tracker.ts",
        role: "tracker",
        note: "Ayuda: inventario FIE F0–F2.8 + checklist prueba",
      },
      {
        path: "docs/engineering/fa-status-and-test-plan-2026-07-31.md",
        role: "doc",
        note: "Estado FA + plan prueba/optimización",
      },
      {
        path: "docs/engineering/fundamental-intelligence-engine-2026-07-30.md",
        role: "doc",
        note: "Diseño canónico FIE · pnpm test:fa",
      },
      {
        path: "packages/py/market/src/bolsa_market/instrument_fundamentals.py",
        role: "code",
        note: "Snapshot Yahoo → derived (Altman…Beneish)",
      },
      {
        path: "packages/py/analytics/src/bolsa_analytics/knowledge/score_fund.py",
        role: "code",
        note: "Score_FUND pilares value|quality|growth|risk",
      },
      {
        path: "packages/py/analytics/src/bolsa_analytics/knowledge/composite_score.py",
        role: "code",
        note: "Composite Investment Score (F3)",
      },
      {
        path: "packages/py/market/src/bolsa_market/roic.py",
        role: "code",
        note: "ROIC NOPAT/IC (F2.7)",
      },
      {
        path: "packages/py/market/src/bolsa_market/beneish.py",
        role: "code",
        note: "Beneish M-Score (F2.8)",
      },
      {
        path: "packages/py/application/src/bolsa_application/run_fundamental_screener.py",
        role: "code",
        note: "Screener FA gate-only + whitelist snapshot",
      },
      {
        path: "packages/py/application/src/bolsa_application/paper_d_propose.py",
        role: "code",
        note: "Paper D propose + execute → ExecutionRouter",
      },
      {
        path: "packages/py/application/src/bolsa_application/fa_weekly_pipeline.py",
        role: "code",
        note: "Pipeline semanal FA→D (cron off-by-default)",
      },
      {
        path: "packages/py/market/src/bolsa_market/filing_store.py",
        role: "code",
        note: "Filings disco (≠ Score_FUND)",
      },
      {
        path: "packages/py/analytics/src/bolsa_analytics/cognitive/decision_session.py",
        role: "code",
        note: "ART-DECISION-SESSION",
      },
      { path: "docs/AI_PLATFORM_SOLUTION.md", role: "doc" },
      {
        path: "docs/rfc/008-cognitive-decision-architecture.md",
        role: "rfc",
        note: "§22 Assessment → Runtime; Session audita el propose",
      },
    ],
  },
  {
    id: "backtesting",
    label: "Backtesting",
    kind: "tracking",
    sources: [
      {
        path: "apps/web/src/features/settings/backtesting-tracker.ts",
        role: "tracker",
        note: "Resumen básico + pantallas + seguimiento",
      },
      {
        path: "docs/engineering/research-lifecycle.md",
        role: "doc",
        note: "Flujo operativo · embudo · Monitor · narrativa paper",
      },
      {
        path: "docs/engineering/session-handoff-2026-08-01.md",
        role: "doc",
        note: "Cierre racha · frescura v1.3 · CORE-B v0.2 · CAPM Tarjeta · smoke UI siguiente",
      },
      {
        path: "docs/engineering/list-auto-ops-2026-07-29.md",
        role: "doc",
        note: "Lista AUTO: frescura v1.3 (bar_hysteresis), keep-alive, CORE-R v1.8",
      },
      {
        path: "docs/engineering/backtesting-funnel-handoff-2026-07-29.md",
        role: "doc",
        note: "Handoff embudo→paper/monitor (índice código)",
      },
      {
        path: "docs/engineering/backtesting-dia-d-premises-2026-07-31.md",
        role: "doc",
        note: "DÍA D v0.11: as-of · full-bleed efímero · Evidence · archivo Trading+Ayuda",
      },
      {
        path: "docs/adr/021-dia-d-reconciliation.md",
        role: "adr",
        note: "F-hoy · F-D · V · veredictos SAME/DRIFT",
      },
      {
        path: "docs/engineering/operativa-test-plan-2026-07-31.md",
        role: "doc",
        note: "Plan prueba D1–D12 + R1–R9 · pnpm test:operativa",
      },
      {
        path: "docs/adr/009-backtesting-research-platform-h0.md",
        role: "adr",
        note: "Motor H0 / contrato",
      },
      { path: "docs/BACKTESTING_DATA_ARCHITECTURE.md", role: "doc" },
      {
        path: "docs/adr/018-fase2-evidence-store-v0.md",
        role: "adr",
        note: "Evidence / Belief / Knowledge v0",
      },
      {
        path: "apps/web/src/features/backtests/",
        role: "code",
      },
    ],
  },
  {
    id: "ai",
    label: "Plataforma IA",
    kind: "tracking",
    sources: [
      {
        path: "apps/web/src/features/settings/ai-platform-tracker.ts",
        role: "tracker",
        note: "UI de esta sección",
      },
      {
        path: "apps/web/src/stores/supervised-f3-queue-store.ts",
        role: "code",
        note: "Cola session scan→F3 · openHelpAiPlatform F3 → /confirm",
      },
      {
        path: "apps/web/src/features/confirm/confirm-page.tsx",
        role: "code",
        note: "UI Confirmar `/confirm` · reutiliza SupervisedF3Panel",
      },
      {
        path: "apps/web/src/features/settings/supervised-f3-panel.tsx",
        role: "code",
        note: "Panel cola F3 (también en Ayuda → Plataforma IA)",
      },
      {
        path: AI_TRACKER_SYNC.solutionDoc,
        role: "doc",
        note: "Encabezado de estado",
      },
      { path: AI_TRACKER_SYNC.rfcIndex, role: "rfc" },
      {
        path: AI_TRACKER_SYNC.cognitiveRfc,
        role: "rfc",
        note: "Decision Engine D0–D7 + Amendment-2 (Assessment→Runtime→Gate); tracker AI_DECISION_PIPELINE + AI_COGNITIVE_PHASES + F3",
      },
      { path: AI_TRACKER_SYNC.governanceRfc, role: "rfc" },
      { path: AI_TRACKER_SYNC.featureRfc, role: "rfc" },
    ],
  },
  {
    id: "data",
    label: "Datos de mercado",
    kind: "tracking",
    sources: [
      {
        path: "apps/web/src/features/settings/data-market-tracker.ts",
        role: "tracker",
        note: "Resumen + sync + validación + BD + ciclo de vida",
      },
      {
        path: "docs/MARKET_DATA.md",
        role: "doc",
        note: "Ingesta Yahoo/XTB · listas↔BD",
      },
      {
        path: "docs/DATA_MODEL.md",
        role: "doc",
        note: "Tablas + ciclo de vida instrumento",
      },
      { path: "docs/adr/002-yahoo-primary-xtb-secondary.md", role: "adr" },
      {
        path: "docs/adr/007-intraday-ohlcv-persistence.md",
        role: "adr",
        note: "Caché intradía",
      },
      {
        path: "apps/web/src/features/config/database-config-panel.tsx",
        role: "code",
        note: "Configuración → BD",
      },
    ],
  },
  {
    id: "charts-status",
    label: "Estado gráficos",
    kind: "tracking",
    sources: [
      {
        path: "apps/web/src/features/settings/chart-platform-tracker.ts",
        role: "tracker",
        note: "UI de esta sección",
      },
      { path: "docs/adr/006-chart-platform-and-settings.md", role: "adr" },
      { path: "docs/CHART_DATA_BAR.md", role: "doc" },
      {
        path: "docs/WORKSPACE_PERSISTENCE.md",
        role: "doc",
        note: "Una pestaña por instrumento (§2b)",
      },
    ],
  },
  {
    id: "fiscal",
    label: "Fiscal y comisiones",
    kind: "guide",
    sources: [
      { path: "docs/PORTFOLIO_AND_CASH.md", role: "doc" },
      { path: "packages/shared/src/account-settings.ts", role: "code" },
    ],
  },
  {
    id: "about",
    label: "Acerca de",
    kind: "about",
    sources: [
      { path: "docs/HELP.md", role: "doc" },
      { path: "docs/AI_PLATFORM_SOLUTION.md", role: "doc" },
      { path: "README.md", role: "doc" },
    ],
  },
];

export function helpSectionMeta(id: HelpRegistrySectionId): HelpSectionMeta {
  const found = HELP_SECTIONS.find((s) => s.id === id);
  if (!found) throw new Error(`Help section not in registry: ${id}`);
  return found;
}

export function trackingSections(): HelpSectionMeta[] {
  return HELP_SECTIONS.filter((s) => s.kind === "tracking");
}
