#!/usr/bin/env node
/**
 * Smoke del encadenado Play 1-valor (caso GRF / Grifols).
 *
 * Offline (siempre):
 *   node scripts/research/verify_play_chain_grf.mjs
 *   pnpm exec node scripts/research/verify_play_chain_grf.mjs
 *
 * Live (API + UI manual):
 *   1. Arranca API + web
 *   2. Abre Backtests → elige GRF (Grifols)
 *   3. Prefs Asistente: ciclo completo ON
 *   4. Un solo Play → debe llegar a Lab → Coach² → Finalistas sin 2º click
 *
 * Este script NO sustituye el click en UI; valida la política/regressions
 * del chain (progress same-tick + GRF coach offline + save decision).
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const isWin = process.platform === 'win32';

const files = [
  'src/features/backtests/backtest-assistant-play-chain.test.ts',
  'src/features/backtests/backtest-assistant-completion.test.ts',
  'src/features/backtests/backtest-assistant-full-cycle.test.ts',
  'src/features/backtests/coach-profile-policy.test.ts',
];

console.log('Bolsa V1 — Play chain smoke (GRF)');
console.log(`root: ${root}`);
console.log('Expect: 1 Play → Universo → Lab → Coach² → Finalistas (no 2º Play por race).');

const result = spawnSync(
  'pnpm',
  ['--filter', '@bolsa/web', 'exec', 'vitest', 'run', ...files],
  {
    cwd: root,
    stdio: 'inherit',
    env: process.env,
    shell: isWin,
  },
);

const code = result.status ?? 1;
if (code !== 0) {
  console.error('\n✗ FAIL: Play chain (GRF) smoke');
  process.exit(code);
}

console.log('\n✓ OK: Play chain regressions (incl. GRF offline)');
console.log('Manual: Backtests → GRF → 1× Play con ciclo completo.');
process.exit(0);
