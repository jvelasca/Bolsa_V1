#!/usr/bin/env node
/**
 * Battery: SEMI DEMO libro operativo (MANUAL/SEMI · Confirm F3 · geo · cola BD).
 *
 * Usage (repo root):
 *   pnpm test:semi
 *   node scripts/research/verify_semi_demo_battery.mjs
 *
 * Phases:
 *   1) Web units — prefs, geo rank, Finalistas path, F3 queue, Camino C copy, sync helper
 *   2) Python units — Recommendation.country + F3 contract
 *   3) Optional API smoke — supervised-f3-queue GET/PUT (SKIP if API down;
 *      SEMI_API_REQUIRED=1 to force)
 *
 * Freeze: AUTO execute · Belief pesos · Camino D — no cubiertos aquí.
 * Docs: docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
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

const pyTests = [
  'packages/py/analytics/tests/test_recommendation_f3.py',
];

console.log('Bolsa V1 — SEMI DEMO operativa battery');
console.log(`root: ${root}`);

let ok = true;
ok =
  run(
    '1/3 Web SEMI libro + F3 (vitest)',
    'pnpm',
    ['--filter', '@bolsa/web', 'exec', 'vitest', 'run', ...webTests],
  ) && ok;

ok =
  run('2/3 Python Recommendation / F3 contract', 'python', [
    '-m',
    'pytest',
    ...pyTests,
    '-q',
  ]) && ok;

ok =
  run('3/3 API smoke SEMI F3 queue (optional)', 'python', [
    'scripts/research/verify_semi_demo_api_smoke.py',
  ]) && ok;

if (!ok) {
  console.error('\nSEMI DEMO battery FAILED');
  process.exit(1);
}
console.log('\nSEMI DEMO battery OK');
console.log(
  'Tip: checklist UI en docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md',
);
