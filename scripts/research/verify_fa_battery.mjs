#!/usr/bin/env node
/**
 * Battery: Fundamental Intelligence Engine (F1–F4 + F2.5–F2.8 + Paper D + weekly).
 *
 * Usage (repo root):
 *   pnpm test:fa
 *   node scripts/research/verify_fa_battery.mjs
 *
 * Phases:
 *   1) Python unit (snapshot / Piotroski / valuation / gate / card / sector bands / …)
 *   2) Offline operativa (snapshot → card → gate → Composite → Screener → Paper D)
 *   3) Pipeline bench (contratos F2.5–F2.8 + presupuestos ms)
 *   4) Boot (import API + rutas FA; health live opcional)
 *   5) Optional API smoke (SKIP if API down; FA_API_REQUIRED=1 to force)
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

const unitTests = [
  'packages/py/market/tests/test_instrument_fundamentals_v2.py',
  'packages/py/market/tests/test_yahoo_fundamentals_timeseries.py',
  'packages/py/market/tests/test_piotroski.py',
  'packages/py/market/tests/test_valuation_f23.py',
  'packages/py/market/tests/test_wacc_f24.py',
  'packages/py/market/tests/test_dcf_scenarios_f25.py',
  'packages/py/market/tests/test_capm_f26.py',
  'packages/py/market/tests/test_adv_f26.py',
  'packages/py/market/tests/test_roic_f27.py',
  'packages/py/market/tests/test_beneish_f28.py',
  'packages/py/market/tests/test_filing_store_f2b.py',
  'packages/py/market/tests/test_sec_edgar_f2bp.py',
  'packages/py/market/tests/test_filing_rag_f2bpp.py',
  'packages/py/analytics/tests/test_fundamental_gate.py',
  'packages/py/analytics/tests/test_fundamental_card_f1.py',
  'packages/py/analytics/tests/test_fundamental_copilot_f1b.py',
  'packages/py/analytics/tests/test_sector_bands_f22.py',
  'packages/py/analytics/tests/test_filing_summary_f2b.py',
  'packages/py/analytics/tests/test_filing_ask_f2bpp.py',
  'packages/py/analytics/tests/test_composite_score_f3.py',
  'packages/py/analytics/tests/test_fundamental_screener_f4.py',
  'packages/py/application/tests/test_instrument_filings_sec_f2bp.py',
  'packages/py/application/tests/test_instrument_filings_ask_f2bpp.py',
  'packages/py/application/tests/test_get_instrument_composite_f3.py',
  'packages/py/application/tests/test_run_fundamental_screener_f4.py',
  'packages/py/application/tests/test_paper_d_propose.py',
  'packages/py/application/tests/test_fa_weekly_pipeline.py',
];

console.log('Bolsa V1 — FA / FIE battery (F1–F4 + F2.5–F2.8 + Paper D + weekly)');
console.log(`root: ${root}`);
console.log(
  'Policy: Python calcula; LLM solo explica; ROIC/Beneish + CAPM + Paper D + Screener.',
);

const phases = [
  () =>
    run('1/5 Python FA units', 'python', [
      '-m',
      'pytest',
      ...unitTests,
      '-q',
      '--tb=short',
    ]),
  () => run('2/5 Offline operativa', 'python', ['scripts/research/verify_fa_operativa.py']),
  () =>
    run('3/5 Pipeline bench + eficiencia', 'python', [
      'scripts/research/verify_fa_pipeline_bench.py',
    ]),
  () => run('4/5 Boot API/FA routes', 'node', ['scripts/research/verify_fa_boot.mjs']),
  () => run('5/5 API smoke (optional)', 'python', ['scripts/research/verify_fa_api_smoke.py']),
];

let ok = true;
for (const phase of phases) {
  if (!phase()) {
    ok = false;
    break;
  }
}

if (!ok) {
  console.error('\nFA battery FAILED');
  process.exit(1);
}
console.log('\nFA battery OK');
process.exit(0);
