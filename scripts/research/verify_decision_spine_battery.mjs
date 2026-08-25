#!/usr/bin/env node
/**
 * Battery: Decision Spine (Runtime → Package → Gate/Fit → confirm SEMI / router AUTO).
 *
 * Usage (repo root):
 *   pnpm test:decision-spine
 *   node scripts/research/verify_decision_spine_battery.mjs
 *
 * Sin API live. `pnpm test:semi` cubre UI/libro DEMO, no esta columna.
 *
 * Docs: docs/engineering/decision-spine-cadena-2026-08-24.md
 *       docs/CURRENT_SYSTEM.md
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

const pyTests = [
  'packages/py/application/tests/test_decision_spine.py',
  'packages/py/application/tests/test_golden_decision_scenario.py',
  'packages/py/application/tests/test_execute_trade_idempotency.py',
  'packages/py/application/tests/test_risk_engine.py',
  'packages/py/application/tests/test_risk_engine_portfolio_fit.py',
  'packages/py/application/tests/test_execution_router.py',
  'packages/py/application/tests/test_trade_plan.py',
  'packages/py/application/tests/test_confirm_trade_plan.py',
  'packages/py/application/tests/test_fill_pending_order.py',
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
  'packages/py/analytics/tests/test_exit_permission.py',
];

console.log('Bolsa V1 — Decision Spine battery');
console.log(`root: ${root}`);

const ok = run('1/1 pytest Decision Spine (sin API live)', 'python', [
  '-m',
  'pytest',
  ...pyTests,
  '-q',
]);

if (!ok) {
  console.error('\nDecision Spine battery FAILED');
  process.exit(1);
}
console.log('\nDecision Spine battery OK');
console.log('Mapa: docs/engineering/decision-spine-cadena-2026-08-24.md');
