#!/usr/bin/env node
/**
 * OE-1 — Autoevaluación operativa SEMI + AUTO (read-only).
 * Prefiere GET /api/risk/ops-self-eval; fallback a thaw snapshot pattern si API down.
 *
 * Usage:
 *   node scripts/ops_operativa_self_eval.mjs
 *   node scripts/ops_operativa_self_eval.mjs --json
 *   node scripts/ops_operativa_self_eval.mjs --account default-account-seed
 *
 * Env: API_URL / VITE_API_URL · LOOKBACK_DAYS · DEMO_ACCOUNT_ID
 * Rule: measure ≠ Accept estricto · ≠ flip PAPER_D_EXECUTE
 */

const API_URL = (
  process.env.VITE_API_URL ??
  process.env.API_URL ??
  'http://127.0.0.1:8000'
).replace(/\/$/, '');
const LOOKBACK = Number(process.env.LOOKBACK_DAYS ?? 120);
const asJson = process.argv.includes('--json');
const accountArg = process.argv.find((a) => a.startsWith('--account='));
const ACCOUNT =
  (accountArg && accountArg.split('=')[1]) ||
  process.env.DEMO_ACCOUNT_ID ||
  'default-account-seed';

async function fetchJson(path) {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

function printHuman(report) {
  console.log('=== OPS OPERATIVA SELF-EVAL (OE-1, read-only) ===');
  console.log(`api=${API_URL} account=${report.accountId} lookback=${report.lookbackDays}`);
  console.log(`rule: ${report.rule}`);
  console.log('');
  const semi = report.lanes?.semi ?? {};
  const auto = report.lanes?.auto ?? {};
  console.log(`--- SEMI / MANUAL --- [${semi.mark}]`);
  console.log(
    `confirmSeed=${semi.confirmSeed} journalSeed=${semi.journalSeed} buysSeed=${semi.buysSeed} tradeLike=${semi.tradeLike}`,
  );
  console.log('');
  console.log(`--- AUTO / Camino D --- [${auto.mark}]`);
  console.log(
    `paperDExecuteEnv=${auto.paperDExecuteEnv} strictAcceptReady=${auto.strictAcceptReady}`,
  );
  const p1 = auto.p1 ?? {};
  const p2 = auto.p2 ?? {};
  const p3 = auto.p3 ?? {};
  const p4 = auto.p4 ?? {};
  const p5 = auto.p5 ?? {};
  console.log(`P1 days=${p1.daysWithOpinions} [${p1.mark}] need≥${p1.need}`);
  console.log(`P2 confirmSeed=${p2.confirmSeed} [${p2.mark}] need≥${p2.need}`);
  console.log(
    `P3 prec=${p3.buyPrecision5d} alarmaBuy=${p3.alarmaBuyCount} mature=${p3.matureBuySample} [${p3.mark}]`,
  );
  console.log(`P4 recall=${p4.buyRecall5d} [${p4.mark}]`);
  console.log(
    `P5 tradeLike=${p5.tradeLike} cashMaxDdFrac=${p5.cashMaxDdFrac} [${p5.mark}]`,
  );
  if (p5.note) console.log(`P5 note: ${p5.note}`);
  console.log('');
  const rt = report.runtime ?? {};
  console.log(
    `runtime kill=${rt.killSwitchEffective} venue=${rt.brokerVenue} accountPref=${rt.accountVenuePreference ?? 'unset'}`,
  );
  console.log(
    `recon=${report.portfolioReconciliation?.status ?? JSON.stringify(report.portfolioReconciliation)}`,
  );
  console.log('');
  console.log('docs: docs/engineering/ops-autoeval-checklist-2026-08-26.md');
  console.log('thaw debt: docs/engineering/deuda-thaw-estricto-runbook-2026-08-25.md');
}

async function main() {
  const path = `/api/risk/ops-self-eval?accountId=${encodeURIComponent(ACCOUNT)}&lookbackDays=${LOOKBACK}`;
  try {
    const report = await fetchJson(path);
    if (asJson) {
      console.log(JSON.stringify(report, null, 2));
    } else {
      printHuman(report);
    }
    return 0;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (asJson) {
      console.log(
        JSON.stringify(
          {
            schemaVersion: 'ops_self_eval_v0',
            error: 'UNAVAILABLE',
            message: msg,
            hint: 'Start API :8000 or see thaw_estricto_snapshot.mjs',
          },
          null,
          2,
        ),
      );
    } else {
      console.log('=== OPS OPERATIVA SELF-EVAL (OE-1) ===');
      console.log(`API UNAVAILABLE: ${msg}`);
      console.log('hint: start API then retry; or node scripts/thaw_estricto_snapshot.mjs');
    }
    return 2;
  }
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
