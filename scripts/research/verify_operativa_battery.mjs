#!/usr/bin/env node
/**
 * Battery: operativa reciente — DÍA D (as-of + Evidence) + CORE-R (Monitor / cola).
 *
 * Usage (repo root):
 *   pnpm test:operativa
 *
 * Manifest: scripts/research/daily-ops-manifest.mjs
 * Docs: docs/engineering/operativa-test-plan-2026-07-31.md
 */

import { repoRoot, runPhase, runPytest, runVitestWeb } from './battery-runner.mjs';
import { operativaWebTests, pyOperativaTests } from './daily-ops-manifest.mjs';

console.log('Bolsa V1 — operativa battery (DÍA D + CORE-R)');
console.log(`root: ${repoRoot}`);

let ok = true;
ok = runVitestWeb('1/3 Web DÍA D + CORE-R (vitest)', operativaWebTests) && ok;
ok = runPytest('2/3 Python as-of + Evidence + CORE-R', pyOperativaTests) && ok;
ok =
  runPhase('3/3 API smoke DÍA D (optional)', 'python', [
    'scripts/research/verify_dia_d_api_smoke.py',
  ]) && ok;

if (!ok) {
  console.error('\nOperativa battery FAILED');
  process.exit(1);
}
console.log('\nOperativa battery OK');
console.log('Tip: Smoke UI checklist en BACKTESTING_NEXT (Ayuda → Backtesting).');
