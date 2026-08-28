/**
 * Manifest — operativa diaria (Mesa/Hoy, Confirm, spine TS↔PY, DÍA D, SEMI).
 *
 * Slices reutilizados por verify_*_battery.mjs y verify_daily_ops_battery.mjs.
 * Docs: docs/engineering/decision-spine-cadena-2026-08-24.md
 *       docs/engineering/operativa-test-plan-2026-07-31.md
 */

/** @type {string[]} Shared — modelo Mesa/Hoy + espejos spine TS */
export const sharedDomainTests = [
  'src/cognitive/mesa-hoy-model.test.ts',
  'src/cognitive/mesa-status-dimensions.test.ts',
  'src/cognitive/mesa-next-action.test.ts',
  'src/cognitive/mesa-protection-state.test.ts',
  'src/cognitive/mesa-operable-ranking.test.ts',
  'src/mesa-entry-queue.test.ts',
  'src/hoy-queue.test.ts',
  'src/cognitive/operational-priority.test.ts',
  'src/operational-incident.test.ts',
  'src/operational-readiness.test.ts',
  'src/cognitive/investment-position-aggregate.test.ts',
  'src/cognitive/portfolio-risk-metrics.test.ts',
  'src/cognitive/portfolio-scenario.test.ts',
  'src/cognitive/policy-gate.test.ts',
  'src/cognitive/data-freshness.test.ts',
  'src/cognitive/opportunity-evidence.test.ts',
  'src/cognitive/opportunity-ranking.test.ts',
  'src/cognitive/operational-plan-view.test.ts',
  'src/accounts-origin.test.ts',
  'src/submit-intent.test.ts',
  'src/paper-order.test.ts',
  'src/paper-broker.test.ts',
  'src/broker-adapter.test.ts',
  'src/exit-permission.test.ts',
  'src/reconciliation-opening-veto.test.ts',
  'src/thesis-health.test.ts',
  'src/exit-plan.test.ts',
  'src/execution-plan.test.ts',
  'src/execution-record.test.ts',
  'src/position-state.test.ts',
  'src/position-revision.test.ts',
  'src/portfolio-reconciliation.test.ts',
  'src/live-ledger-reconciliation.test.ts',
  'src/risk-signature.test.ts',
  'src/protect-plan.test.ts',
  'src/exit-radar.test.ts',
  'src/mfe-mae.test.ts',
  'src/expectancy.test.ts',
  'src/trail-plan.test.ts',
  'src/bracket-plan.test.ts',
  'src/decision-journal-study.test.ts',
  'src/decision-journal-study-delta.test.ts',
  'src/cognitive/decision-journal-relevant-delta.test.ts',
];

/** @type {string[]} Web — nav L1, Mesa/Hoy, operations */
export const webMesaConfirmTests = [
  'src/features/confirm/daily-nav.test.ts',
  'src/features/confirm/confirm-nav.test.ts',
  'src/features/confirm/confirm-drawer.test.ts',
  'src/features/mesa/mesa-hoy-page.test.ts',
  'src/features/mesa/mesa-hoy-view.test.ts',
  'src/features/mesa/mesa-candidates-panel.test.ts',
  'src/features/mesa/mesa-zone1-redirects.test.ts',
  'src/components/layout/admin-rail.test.ts',
  'src/features/mesa/mesa-position-row.test.tsx',
  'src/features/operations/mesa-entry-queue-panel.test.tsx',
  'src/features/operations/mesa-incident-banner.test.tsx',
  'src/features/operations/mesa-operational-bar.test.tsx',
  'src/features/operations/propose-position-exit.test.ts',
  'src/features/help/hoy-en-la-mesa.test.tsx',
  'src/features/help/mesa-tip-button.test.tsx',
  'src/features/operational-console/operational-console-page.test.tsx',
  'src/features/platform/operating-mandate.test.ts',
  'src/features/decision-journal/decision-journal-helpers.test.ts',
];

/** @type {string[]} Web — F3, SEMI libro, DÍA D gate, trading desk */
export const webTradingDeskTests = [
  'src/features/trading/f3-order-projection.test.ts',
  'src/features/trading/f3-protect-stop-block.test.tsx',
  'src/features/trading/f3-risk-signature-block.test.tsx',
  'src/features/trading/f3-risk-input-baseline.test.ts',
  'src/features/trading/f3-trade-plan-risk-first-block.test.tsx',
  'src/features/trading/f3-ticket-preview.test.ts',
  'src/features/trading/supervised-f3-sync.test.ts',
  'src/features/trading/semi-demo-operativa.test.ts',
  'src/features/trading/semi-confirm-mandate.test.ts',
  'src/features/trading/semi-hm-conflict.test.ts',
  'src/features/trading/demo-book-prefs.test.ts',
  'src/features/trading/demo-book-geo-rank.test.ts',
  'src/features/trading/demo-book-auto-arm.test.ts',
  'src/features/trading/demo-book-auto-copy.test.ts',
  'src/features/trading/propose-instrument-supervised.test.ts',
  'src/features/trading/decision-package-chips.test.ts',
  'src/features/trading/trading-background-status.test.ts',
  'src/features/trading/operativa-index.test.ts',
  'src/features/trading/dia-d-gate-equity.test.ts',
  'src/features/trading/dia-d-session-evidence.test.ts',
  'src/features/trading/dia-d-evidence-archive-io.test.ts',
  'src/features/trading/dia-d-verify-continuity.test.ts',
  'src/stores/dia-d-trading-session-store.test.ts',
  'src/stores/dia-d-evidence-archive-store.test.ts',
  'src/stores/supervised-f3-queue-store.test.ts',
  'src/features/backtests/finalist-propose-supervised.test.ts',
  'src/features/settings/paper-paths-copy.test.ts',
];

/** @type {string[]} Web — CORE-R / monitor (operativa lab replay) */
export const webCoreRTests = [
  'src/features/backtests/core-r-judgment.test.ts',
  'src/features/backtests/core-r-scheduler.test.ts',
  'src/features/backtests/core-r-status.test.ts',
  'src/features/backtests/strategy-monitor.test.ts',
  'src/stores/core-r-review-queue-store.test.ts',
  'src/stores/alerts-store.test.ts',
  'src/features/settings/backtesting-tracker.test.ts',
];

/** @type {string[]} Python — Decision Spine (offline, sin API) */
export const pyDecisionSpineTests = [
  'packages/py/application/tests/test_decision_spine.py',
  'packages/py/application/tests/test_golden_decision_scenario.py',
  'packages/py/application/tests/test_execute_trade_idempotency.py',
  'packages/py/application/tests/test_risk_engine.py',
  'packages/py/application/tests/test_risk_engine_portfolio_fit.py',
  'packages/py/application/tests/test_execution_router.py',
  'packages/py/application/tests/test_trade_plan.py',
  'packages/py/application/tests/test_confirm_trade_plan.py',
  'packages/py/application/tests/test_fill_pending_order.py',
  'packages/py/application/tests/test_persist_position_from_fill.py',
  'packages/py/application/tests/test_confirm_risk_signature.py',
  'packages/py/application/tests/test_confirm_execution_record.py',
  'packages/py/application/tests/test_confirm_crash_restart.py',
  'packages/py/application/tests/test_dex2_crash_restart_cross_pid.py',
  'packages/py/application/tests/test_dex3_operational_incident.py',
  'packages/py/application/tests/test_dex4_confirm_orchestrator.py',
  'packages/py/application/tests/test_dex5_operational_invariants.py',
  'packages/py/application/tests/test_confirm_paper_order.py',
  'packages/py/application/tests/test_paper_broker.py',
  'packages/py/application/tests/test_broker_adapter.py',
  'packages/py/application/tests/test_confirm_broker_adapter.py',
  'packages/py/application/tests/test_confirm_exit_chain.py',
  'packages/py/application/tests/test_persist_position_from_exit.py',
  'packages/py/application/tests/test_post_fill_position_sync.py',
  'packages/py/application/tests/test_persist_position_from_protect.py',
  'packages/py/application/tests/test_semi_triggered_confirm_protect.py',
  'packages/py/application/tests/test_v126_semi_position_birth.py',
  'packages/py/application/tests/test_v127_golden_path.py',
  'packages/py/application/tests/test_v127_golden_path_fail.py',
  'packages/py/application/tests/test_backtest_risk_policy_wiring.py',
  'packages/py/application/tests/test_reconcile_portfolio_integrity.py',
  'packages/py/application/tests/test_reconcile_live_ledger.py',
  'packages/py/application/tests/test_reconciliation_opening_gate.py',
  'packages/py/application/tests/test_or5_broker_execution_scenarios.py',
  'packages/py/application/tests/test_operational_readiness.py',
  'packages/py/application/tests/test_ops_self_eval.py',
  'packages/py/application/tests/test_record_session_verdict.py',
  'packages/py/application/tests/test_opening_permission.py',
  'packages/py/application/tests/test_execute_gated_portfolio_trade.py',
  'packages/py/application/tests/test_decision_board_session_echo.py',
  'packages/py/application/tests/test_decision_journal.py',
  'packages/py/analytics/tests/test_thesis_health.py',
  'packages/py/analytics/tests/test_protect_plan.py',
  'packages/py/analytics/tests/test_exit_radar.py',
  'packages/py/analytics/tests/test_mfe_mae.py',
  'packages/py/analytics/tests/test_expectancy.py',
  'packages/py/analytics/tests/test_trail_plan.py',
  'packages/py/analytics/tests/test_bracket_plan.py',
  'packages/py/analytics/tests/test_position_state.py',
  'packages/py/analytics/tests/test_exit_plan.py',
  'packages/py/analytics/tests/test_execution_plan.py',
  'packages/py/analytics/tests/test_execution_record.py',
  'packages/py/analytics/tests/test_submit_intent.py',
  'packages/py/analytics/tests/test_operational_incident.py',
  'packages/py/analytics/tests/test_paper_order.py',
  'packages/py/analytics/tests/test_paper_broker_receipt.py',
  'packages/py/analytics/tests/test_broker_adapter_receipt.py',
  'packages/py/analytics/tests/test_position_revision.py',
  'packages/py/analytics/tests/test_portfolio_reconciliation.py',
  'packages/py/analytics/tests/test_live_ledger_reconciliation.py',
  'packages/py/analytics/tests/test_exit_permission.py',
  'packages/py/analytics/tests/test_risk_signature.py',
  'packages/py/analytics/tests/test_operational_levels.py',
  'packages/py/analytics/tests/test_position_decision.py',
];

/** @type {string[]} Python — DÍA D + CORE-R evidence + daily ops report (H1 offline) */
export const pyOperativaTests = [
  'packages/py/analytics/tests/test_as_of_cut.py',
  'packages/py/market/tests/test_fundamentals_as_of.py',
  'packages/py/analytics/tests/test_dia_d_session_evidence.py',
  'packages/py/analytics/tests/test_core_r_review_evidence.py',
  'packages/py/application/tests/test_explain_core_r_review.py',
  'packages/py/application/tests/test_research_evidence.py',
  'packages/py/application/tests/test_daily_ops_report.py',
];

/** @type {string[]} Python — SEMI F3 contract */
export const pySemiTests = ['packages/py/analytics/tests/test_recommendation_f3.py'];

/** @type {string[]} Python — daily ops digest infra (--with-report only; report unit tests are offline in pyOperativaTests) */
export const pyDailyOpsReportTests = [
  'packages/py/infrastructure/tests/test_daily_ops_digest_email.py',
  'packages/py/infrastructure/tests/test_daily_ops_digest_pdf.py',
];

/** Slice DÍA D + CORE-R (legacy test:operativa). */
export const operativaWebTests = [
  'src/features/trading/dia-d-gate-equity.test.ts',
  'src/features/trading/dia-d-session-evidence.test.ts',
  'src/features/trading/dia-d-evidence-archive-io.test.ts',
  'src/stores/dia-d-evidence-archive-store.test.ts',
  'src/stores/dia-d-trading-session-store.test.ts',
  ...webCoreRTests,
];

export const semiWebTests = [
  'src/features/trading/demo-book-prefs.test.ts',
  'src/features/trading/demo-book-geo-rank.test.ts',
  'src/features/trading/supervised-f3-sync.test.ts',
  'src/features/trading/semi-demo-operativa.test.ts',
  'src/features/trading/semi-confirm-mandate.test.ts',
  'src/features/trading/semi-hm-conflict.test.ts',
  'src/features/backtests/finalist-propose-supervised.test.ts',
  'src/stores/supervised-f3-queue-store.test.ts',
  'src/features/settings/paper-paths-copy.test.ts',
  'src/features/platform/operating-mandate.test.ts',
];

export const DAILY_OPS_PHASES = [
  {
    id: 'shared-domain',
    label: 'Shared domain (Mesa/Hoy + spine mirrors TS)',
    kind: 'shared',
    files: sharedDomainTests,
  },
  {
    id: 'web-mesa-confirm',
    label: 'Web Mesa + Confirm + nav L1',
    kind: 'web',
    files: webMesaConfirmTests,
  },
  {
    id: 'web-trading-desk',
    label: 'Web Trading desk (F3, DÍA D, SEMI libro)',
    kind: 'web',
    files: webTradingDeskTests,
  },
  {
    id: 'web-core-r',
    label: 'Web CORE-R monitor / cola',
    kind: 'web',
    files: webCoreRTests,
  },
  {
    id: 'py-spine',
    label: 'Python Decision Spine (DEX, confirm, opening)',
    kind: 'py',
    files: pyDecisionSpineTests,
  },
  {
    id: 'py-operativa',
    label: 'Python DÍA D + CORE-R + daily ops report',
    kind: 'py',
    files: pyOperativaTests,
  },
];
