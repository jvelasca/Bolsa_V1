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
  console.log('* API smoke SKIP if backend down; OPTIMIZE_API_REQUIRED=1 to require it.');
  process.exit(0);
}
console.error(`✗ Optimize battery FAILED (${failed} phase(s))`);
process.exit(1);
