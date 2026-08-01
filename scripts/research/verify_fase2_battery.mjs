#!/usr/bin/env node
/**
 * Battery: Fase 2 scientific domain (Evidence → Belief → Knowledge → Tree → MKL).
 *
 * Usage (repo root):
 *   pnpm test:fase2
 *   node scripts/research/verify_fase2_battery.mjs
 *
 * Policy: every Fase 2 change must extend tests, register them here, update
 * docs/engineering/research-lifecycle.md, then re-run this battery green.
 *
 * Phases:
 *   1) Python piece tests (P2.A–P2.F)
 *   2) Python assembly (end-to-end contracts)
 *   3) Optional API smoke (SKIP if API down; FASE2_API_REQUIRED=1 to force)
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

/** Keep in sync when adding Fase 2 test files. */
const pieceTests = [
  'packages/py/application/tests/test_research_evidence.py',
  'packages/py/application/tests/test_hypotheses.py',
  'packages/py/application/tests/test_belief_engine.py',
  'packages/py/application/tests/test_knowledge_consolidation.py',
  'packages/py/application/tests/test_research_tree.py',
  'packages/py/application/tests/test_mkl_sync.py',
  'packages/py/application/tests/test_run_and_save_backtest.py',
];

const assemblyTests = [
  'packages/py/application/tests/test_fase2_assembly_battery.py',
];

console.log('Bolsa V1 — Fase 2 scientific battery');
console.log(`root: ${root}`);
console.log('Policy: Evidence ≠ Belief ≠ Knowledge; Consolidation/MKL never auto-trade.');

const phases = [
  () =>
    run('1/3 Python Fase 2 pieces (P2.A–P2.F)', 'python', [
      '-m',
      'pytest',
      ...pieceTests,
      '-q',
      '--tb=short',
    ]),
  () =>
    run('2/3 Python Fase 2 assembly', 'python', [
      '-m',
      'pytest',
      ...assemblyTests,
      '-q',
      '--tb=short',
    ]),
  () => run('3/3 API smoke (optional)', 'python', ['scripts/research/verify_fase2_api_smoke.py']),
];

let failed = 0;
for (const phase of phases) {
  if (!phase()) failed += 1;
}

console.log('\n════════════════════════════');
if (failed === 0) {
  console.log('✓ Fase 2 battery PASSED (all phases)');
  console.log('Covers: Evidence · Hypothesis · Belief · Consolidation · Tree · MKL stub ·');
  console.log('        BT/optimize hooks · assembly chain · API smoke*');
  console.log('* API smoke SKIP if backend down; FASE2_API_REQUIRED=1 to require it.');
  process.exit(0);
}
console.error(`✗ Fase 2 battery FAILED (${failed} phase(s))`);
process.exit(1);
