#!/usr/bin/env node
/**
 * Battery: coach ★ / TOP-3 / Finalistas (pilar del embudo) + CORE-P.
 *
 * Usage (repo root):
 *   pnpm test:coach
 *   pnpm test:coach:smoke   # solo API multi-perfil
 *   node scripts/research/verify_coach_battery.mjs
 *
 * Phases:
 *   1) Web units (coach / Lista AUTO / CORE-P offline)
 *   2) Optional live API smoke CORE-P multi-perfil (SKIP if :8000 down;
 *      CORE_P_API_REQUIRED=1 or OPERATIVA_API_REQUIRED=1 to force)
 * ASGI integration: apps/api-python/tests/integration/test_core_p_multi_profile.py
 *   (vía `pnpm test:py` cuando DB está arriba)
 *
 * Policy: changes to deep-coach, matrix→explore, Guardar TOP-3 or Finalistas
 * must extend tests and pass this battery.
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

const vitestFiles = [
  'src/features/backtests/backtest-deep-coach.test.ts',
  'src/features/backtests/backtest-coach-coherence.test.ts',
  'src/features/backtests/coach-dual-audit.test.ts',
  'src/features/backtests/coach-top-save.test.ts',
  'src/features/backtests/backtest-buy-hold.test.ts',
  'src/features/backtests/instrument-strategy-top-promote.test.ts',
  'src/features/backtests/lab-coach-caf-smoke.test.ts',
  'src/features/backtests/lab-adoption-memory.test.ts',
  'src/features/backtests/lab-coach-handoff.test.ts',
  'src/features/backtests/backtest-coach-lote.test.ts',
  'src/features/backtests/backtest-assistant-prefs.test.ts',
  'src/features/backtests/backtest-assistant-full-cycle.test.ts',
  'src/features/backtests/backtest-assistant-play-chain.test.ts',
  'src/features/backtests/backtest-list-auto.test.ts',
  'src/features/backtests/backtest-list-auto-board.test.ts',
  'src/features/backtests/backtest-list-auto-persist.test.ts',
  'src/features/backtests/backtest-finalists-freshness.test.ts',
  'src/features/backtests/backtest-finalists-freshness-restart.test.ts',
  'src/features/backtests/instrument-strategy-top-panel.test.ts',
  'src/features/backtests/finalist-propose-supervised.test.ts',
  'src/stores/supervised-f3-queue-store.test.ts',
  'src/features/backtests/strategy-monitor.test.ts',
  'src/features/settings/paper-paths-copy.test.ts',
  'src/features/backtests/ibex35-operativa-audit.test.ts',
  'src/features/backtests/coach-profile-policy.test.ts',
  'src/features/backtests/coach-profile-battery-scenario.test.ts',
];

console.log('Bolsa V1 — coach / TOP-3 coherence battery');
console.log(`root: ${root}`);
console.log('Policy: coach ranking + persist must stay multi-instrument coherent.');

let ok = true;
ok =
  run(
    '1/2 Web coach coherence (vitest)',
    'pnpm',
    ['--filter', '@bolsa/web', 'exec', 'vitest', 'run', ...vitestFiles],
  ) && ok;

ok =
  run('2/2 API smoke CORE-P multi-perfil (optional live)', 'python', [
    'scripts/research/verify_core_p_api_smoke.py',
  ]) && ok;

if (!ok) {
  console.error('\nCoach battery FAILED');
  process.exit(1);
}
console.log('\nCoach battery OK');
console.log('Tip: fuerza smoke con CORE_P_API_REQUIRED=1 pnpm test:coach:smoke');
