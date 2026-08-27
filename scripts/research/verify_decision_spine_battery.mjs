#!/usr/bin/env node
/**
 * Battery: Decision Spine (Runtime → Package → Gate/Fit → confirm SEMI / router AUTO).
 *
 * Usage (repo root):
 *   pnpm test:decision-spine
 *
 * Sin API live. Manifest: scripts/research/daily-ops-manifest.mjs
 * Docs: docs/engineering/decision-spine-cadena-2026-08-24.md
 */

import { repoRoot, runPytest } from './battery-runner.mjs';
import { pyDecisionSpineTests } from './daily-ops-manifest.mjs';

console.log('Bolsa V1 — Decision Spine battery');
console.log(`root: ${repoRoot}`);

const ok = runPytest('1/1 pytest Decision Spine (sin API live)', pyDecisionSpineTests);

if (!ok) {
  console.error('\nDecision Spine battery FAILED');
  process.exit(1);
}
console.log('\nDecision Spine battery OK');
console.log('Mapa: docs/engineering/decision-spine-cadena-2026-08-24.md');
