#!/usr/bin/env node
/**
 * Battery: SEMI DEMO libro operativo (MANUAL/SEMI · Confirm F3 · geo · cola BD).
 *
 * Usage (repo root):
 *   pnpm test:semi
 *
 * Manifest: scripts/research/daily-ops-manifest.mjs
 * Docs: docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
 */

import { repoRoot, runPhase, runPytest, runVitestWeb } from './battery-runner.mjs';
import { pySemiTests, semiWebTests } from './daily-ops-manifest.mjs';

console.log('Bolsa V1 — SEMI DEMO operativa battery');
console.log(`root: ${repoRoot}`);

let ok = true;
ok = runVitestWeb('1/3 Web SEMI libro + F3 (vitest)', semiWebTests) && ok;
ok = runPytest('2/3 Python Recommendation / F3 contract', pySemiTests) && ok;
ok =
  runPhase('3/3 API smoke SEMI F3 queue (optional)', 'python', [
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
