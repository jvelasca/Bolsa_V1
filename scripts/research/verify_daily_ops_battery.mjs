#!/usr/bin/env node
/**
 * Battery unificada — operativa diaria (Mesa/Hoy, Confirm, spine, DÍA D, CORE-R).
 *
 * Usage (repo root):
 *   pnpm test:daily-ops              # offline: fases 1–6
 *   pnpm test:daily-ops:offline      # alias explícito
 *   pnpm test:daily-ops -- --with-semi # incluye pytest F3 + slice SEMI ya en web-trading
 *   pnpm test:daily-ops -- --with-report # R1–R4 + digest infra
 *   pnpm test:daily-ops -- --smoke   # API smokes DÍA D + SEMI F3
 *
 * Freeze: Confirm = firma · PAPER_D_EXECUTE off · AUTO off · LIVE experimental.
 * Docs: docs/engineering/traspaso-relevo-tag-v1-20-beta-2026-08-27.md
 */

import {
  repoRoot,
  runPhase,
  runPytest,
  runVitestShared,
  runVitestWeb,
} from './battery-runner.mjs';
import {
  DAILY_OPS_PHASES,
  pyDailyOpsReportTests,
  pySemiTests,
} from './daily-ops-manifest.mjs';

const args = process.argv.slice(2);
const withSemi = args.includes('--with-semi');
const withReport = args.includes('--with-report');
const smoke = args.includes('--smoke');
const offlineOnly = args.includes('--offline') || !smoke;

console.log('Bolsa V1 — Daily ops battery (operativa diaria)');
console.log(`root: ${repoRoot}`);
console.log(
  `mode: ${offlineOnly ? 'offline' : 'offline+smoke'}${withSemi ? ' +semi-py' : ''}${withReport ? ' +report' : ''}`,
);

let ok = true;
let phase = 0;
const totalOffline = DAILY_OPS_PHASES.length + (withSemi ? 1 : 0) + (withReport ? 1 : 0);

for (const p of DAILY_OPS_PHASES) {
  phase += 1;
  const tag = `${phase}/${totalOffline}`;
  if (p.kind === 'shared') {
    ok = runVitestShared(`${tag} ${p.label}`, p.files) && ok;
  } else if (p.kind === 'web') {
    ok = runVitestWeb(`${tag} ${p.label}`, p.files) && ok;
  } else if (p.kind === 'py') {
    ok = runPytest(`${tag} ${p.label}`, p.files) && ok;
  }
}

if (withSemi) {
  phase += 1;
  ok = runPytest(`${phase}/${totalOffline} Python SEMI F3 contract`, pySemiTests) && ok;
}

if (withReport) {
  phase += 1;
  ok =
    runPytest(`${phase}/${totalOffline} Python daily ops report + digest`, pyDailyOpsReportTests) &&
    ok;
}

if (smoke) {
  ok =
    runPhase('API smoke DÍA D (optional)', 'python', [
      'scripts/research/verify_dia_d_api_smoke.py',
    ]) && ok;
  ok =
    runPhase('API smoke SEMI F3 queue (optional)', 'python', [
      'scripts/research/verify_semi_demo_api_smoke.py',
    ]) && ok;
}

if (!ok) {
  console.error('\nDaily ops battery FAILED');
  process.exit(1);
}

console.log('\nDaily ops battery OK');
console.log('Mapa: scripts/research/daily-ops-manifest.mjs');
console.log('Spine: pnpm test:decision-spine (subset py-spine) · Operativa: pnpm test:operativa · SEMI: pnpm test:semi');
