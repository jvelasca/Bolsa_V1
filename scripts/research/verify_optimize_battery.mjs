#!/usr/bin/env node
/**
 * Battery: verify the optimize lab (pieces + assembly + optional API).
 *
 * Usage (repo root):
 *   pnpm test:optimize
 *   node scripts/research/verify_optimize_battery.mjs
 *
 * When adding optimize features: add tests, register them here (pyTests/webTests),
 * update docs/engineering/research-lifecycle.md, then re-run this battery.
 *
 * Phases:
 *   1) Python analytics/application optimize tests
 *   2) OOS warm-up regression script
 *   3) Web UI optimize / paper-gate vitest
 *   4) Optional API smoke (SKIP if API down; set OPTIMIZE_API_REQUIRED=1 to force)
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const isWin = process.platform === 'win32';

function run(label, command, args, env = {}) {
  console.log(`\n── ${label} ──`);
  console.log(`$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    env: { ...process.env, ...env },
    shell: isWin,
  });
  const code = result.status ?? 1;
  if (code !== 0) {
    console.error(`\n✗ FAIL: ${label} (exit ${code})`);
    return false;
  }
  console.log(`✓ OK: ${label}`);
  return true;
}

/** Keep in sync when adding optimize test files. */
const pyTests = [
  'packages/py/analytics/tests/test_holdout.py',
  'packages/py/analytics/tests/test_walk_forward.py',
  'packages/py/analytics/tests/test_cpcv.py',
  'packages/py/analytics/tests/test_pbo.py',
  'packages/py/analytics/tests/test_lab_edge_report.py',
  'packages/py/analytics/tests/test_oos_warmup.py',
  'packages/py/analytics/tests/test_evidence_engine_d3.py',
  'packages/py/analytics/tests/test_sma_grid.py',
  'packages/py/analytics/tests/test_rsi_grid.py',
  'packages/py/analytics/tests/test_macd_grid.py',
  'packages/py/application/tests/test_oos_eval_warmup.py',
  'packages/py/application/tests/test_optimize_pipeline_battery.py',
  'packages/py/application/tests/test_optimization_runs.py',
  'packages/py/application/tests/test_optimize_live_progress.py',
  'packages/py/application/tests/test_paper_lab_evidence.py',
  'packages/py/application/tests/test_persist_lab_edge_report.py',
  'packages/py/application/tests/test_run_and_save_backtest.py',
  // R1/R3/R7 — gate P1 (medición neta), procedencia del slot TOP y fase del LAB.
  'packages/py/application/tests/test_instrument_strategy_tops_runid.py',
  'packages/py/application/tests/test_top_provenance.py',
  'packages/py/application/tests/test_strategy_lab_phase.py',
  'packages/py/application/tests/test_strategy_top3_coach_phase.py',
  // R2/R7 — contrato HTTP del disparador gobernado del embudo (hermético).
  'apps/api-python/tests/test_auto_orchestrator_route.py',
  // R6 — experimento TOP DÍA D durable (append-only en servidor + ruta HTTP).
  'packages/py/application/tests/test_dia_d_experiment_top.py',
  'apps/api-python/tests/test_dia_d_experiment_top_route.py',
];

const webTests = [
  'src/features/backtests/backtest-optimize-compare.test.ts',
  'src/features/backtests/backtest-optimize-space.test.ts',
  'src/features/backtests/backtest-optimize-from-seed.test.ts',
  'src/features/backtests/backtest-optimize-heatmap.test.ts',
  'src/features/backtests/lab-coach-handoff.test.ts',
  'src/features/backtests/lab-coach-caf-smoke.test.ts',
  'src/features/backtests/backtest-oos-evidence.test.ts',
  'src/features/backtests/backtest-paper-gate.test.ts',
  'src/features/backtests/backtest-walk-forward-metrics.test.ts',
  'src/features/backtests/backtest-lab-wfe.test.ts',
  'src/features/backtests/backtest-pbo.test.ts',
  'src/features/research/research-lab-evidence.test.ts',
  'src/features/backtests/backtest-optimize-validation-hint.test.ts',
  'src/features/accounts/paper-lab-evidence.test.ts',
  // R1/R3/R5 · gates del LAB en primer nivel (P1 neto, P2/P3, puerta única).
  'src/features/backtests/backtest-paper-checklist.test.tsx',
  'src/features/backtests/backtest-result-decision-card.test.tsx',
  'src/features/backtests/lab-research-section.test.tsx',
  'src/features/backtests/backtest-orchestrator-trigger.test.tsx',
  'src/features/backtests/instrument-top-match.test.ts',
  'src/features/backtests/instrument-strategy-top-promote.test.ts',
  'src/features/research/lab-trial-history-panel.test.tsx',
  'src/features/research/lab-trial-detail-panel.test.tsx',
  'src/features/research/research-history-redirect.test.tsx',
  'src/features/research/research-first-level.test.tsx',
  'src/features/confirm/daily-nav.test.ts',
  // R6 — el experimento F-D es durable: servidor → caché y hueco declarado.
  'src/features/backtests/dia-d-experiment-top.test.ts',
  'src/features/backtests/use-dia-d-experiment-top.test.tsx',
];

console.log('Bolsa V1 — optimize lab battery');
console.log(`root: ${root}`);
console.log('Policy: every optimize change must extend tests + pass this battery.');

const phases = [
  () => run('1/4 Python optimize suite', 'python', ['-m', 'pytest', ...pyTests, '-q', '--tb=short']),
  () => run('2/4 OOS warm-up script', 'python', ['scripts/research/verify_oos_warmup.py']),
  () =>
    run('3/4 Web optimize / paper UI', isWin ? 'pnpm.cmd' : 'pnpm', [
      '--filter',
      '@bolsa/web',
      'exec',
      'vitest',
      'run',
      ...webTests,
    ]),
  () => run('4/4 API smoke (optional)', 'python', ['scripts/research/verify_optimize_api_smoke.py']),
];

let failed = 0;
for (const phase of phases) {
  if (!phase()) failed += 1;
}

console.log('\n════════════════════════════');
if (failed === 0) {
  console.log('✓ Optimize battery PASSED (all phases)');
  console.log('Covers: hold-out · WF · CPCV · PBO · EdgeReport lite · WFE→evidence ·');
  console.log('        OOS warm-up · grids · assembly · UI · P5–P9 · paper · edge_reports · adopt · API smoke*');
  console.log('        LAB gates R1 (P1 neto) · R2 (disparador gobernado) · R3 (procedencia TOP) · R5 (puerta única)');
  console.log('        R6 (F-D durable en servidor)');
  console.log('* API smoke SKIP if backend down; OPTIMIZE_API_REQUIRED=1 to require it.');
  process.exit(0);
}
console.error(`✗ Optimize battery FAILED (${failed} phase(s))`);
process.exit(1);
