#!/usr/bin/env node
/**
 * Battery: operativa reciente — DÍA D (as-of + Evidence + full-bleed prefs) + CORE-R
 * (Monitor / PnL / cola / cron shell / narración).
 *
 * Usage (repo root):
 *   pnpm test:operativa
 *   node scripts/research/verify_operativa_battery.mjs
 *
 * Phases:
 *   1) Web units (DÍA D gate/evidence/archive/session + CORE-R juicio/cola/scheduler/monitor + Ayuda guides)
 *   2) Python units (as_of FA + Evidence sesión + CORE-R narración + persist draft)
 *   3) Optional API smoke DÍA D (SKIP if API down; OPERATIVA_API_REQUIRED=1 to force)
 *
 * Policy: no auto-paper D · LLM solo narra · no pisa TOP.
 * Docs: docs/engineering/operativa-test-plan-2026-07-31.md · docs/HELP.md
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

const webTests = [
  'src/features/trading/dia-d-gate-equity.test.ts',
  'src/features/trading/dia-d-session-evidence.test.ts',
  'src/features/trading/dia-d-evidence-archive-io.test.ts',
  'src/stores/dia-d-evidence-archive-store.test.ts',
  'src/stores/dia-d-trading-session-store.test.ts',
  'src/features/backtests/core-r-judgment.test.ts',
  'src/features/backtests/core-r-scheduler.test.ts',
  'src/features/backtests/core-r-status.test.ts',
  'src/features/backtests/strategy-monitor.test.ts',
  'src/stores/core-r-review-queue-store.test.ts',
  'src/stores/alerts-store.test.ts',
  'src/features/settings/backtesting-tracker.test.ts',
  'src/features/settings/paper-paths-copy.test.ts',
];

const pyTests = [
  'packages/py/analytics/tests/test_as_of_cut.py',
  'packages/py/market/tests/test_fundamentals_as_of.py',
  'packages/py/analytics/tests/test_dia_d_session_evidence.py',
  'packages/py/analytics/tests/test_core_r_review_evidence.py',
  'packages/py/application/tests/test_explain_core_r_review.py',
  'packages/py/application/tests/test_research_evidence.py',
];

console.log('Bolsa V1 — operativa battery (DÍA D + CORE-R)');
console.log(`root: ${root}`);

let ok = true;
ok =
  run(
    '1/3 Web DÍA D + CORE-R (vitest)',
    'pnpm',
    ['--filter', '@bolsa/web', 'exec', 'vitest', 'run', ...webTests],
  ) && ok;

ok =
  run('2/3 Python as-of + Evidence + CORE-R', 'python', ['-m', 'pytest', ...pyTests, '-q']) &&
  ok;

ok =
  run('3/3 API smoke DÍA D (optional)', 'python', [
    'scripts/research/verify_dia_d_api_smoke.py',
  ]) && ok;

if (!ok) {
  console.error('\nOperativa battery FAILED');
  process.exit(1);
}
console.log('\nOperativa battery OK');
console.log('Tip: Smoke UI checklist en BACKTESTING_NEXT (Ayuda → Backtesting).');
