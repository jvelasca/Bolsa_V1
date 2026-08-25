#!/usr/bin/env node
/**
 * Read-only P1–P5 snapshot for strict Camino D thaw debt (ADR-023 BETA-D).
 * Does NOT invent opinions, flip PAPER_D_EXECUTE, or Accept strict thaw.
 *
 * Usage (repo root, API up):
 *   node scripts/thaw_estricto_snapshot.mjs
 *   node scripts/thaw_estricto_snapshot.mjs --no-db
 *
 * Env: API_URL / VITE_API_URL (default http://127.0.0.1:8000)
 *      LOOKBACK_DAYS (default 120)
 *      DEMO_ACCOUNT_ID (default default-account-seed)
 *      POSTGRES_CONTAINER (default bolsa-postgres)
 */

const API_URL = (
  process.env.VITE_API_URL ??
  process.env.API_URL ??
  'http://127.0.0.1:8000'
).replace(/\/$/, '');
const LOOKBACK = Number(process.env.LOOKBACK_DAYS ?? 120);
const DEMO = process.env.DEMO_ACCOUNT_ID ?? 'default-account-seed';
const PG = process.env.POSTGRES_CONTAINER ?? 'bolsa-postgres';
const skipDb = process.argv.includes('--no-db');

const TESTISH =
  'idempotency|stamp auth|tax test|test fees|http retry|position policy|sin policy|perfil custom';

function mark(ok, warn = false) {
  if (ok) return 'PASS';
  if (warn) return 'WARN';
  return 'FAIL';
}

async function fetchJson(path) {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

async function psql(sql) {
  const { spawnSync } = await import('node:child_process');
  const r = spawnSync(
    'docker',
    ['exec', PG, 'psql', '-U', 'bolsa', '-d', 'bolsa_v1', '-t', '-A', '-c', sql],
    { encoding: 'utf8', windowsHide: true },
  );
  if (r.error) throw r.error;
  if (r.status !== 0) {
    throw new Error((r.stderr || r.stdout || `psql exit ${r.status}`).trim());
  }
  return (r.stdout || '').trim();
}

async function main() {
  console.log('=== THAW ESTRICTO SNAPSHOT (read-only) ===');
  console.log(`api=${API_URL} lookbackDays=${LOOKBACK} demo=${DEMO}`);
  console.log('rule: measure ≠ Accept strict · no PAPER_D_EXECUTE flip');
  console.log('');

  let healthRisk = {};
  try {
    const health = await fetchJson('/api/health');
    const risk = health?.components?.risk ?? {};
    healthRisk = risk?.details ?? risk;
    console.log(
      `health.paperDExecuteEnv=${healthRisk.paperDExecuteEnv ?? '?'} kill=${healthRisk.effective ?? healthRisk.killSwitchEffective ?? '?'}`,
    );
  } catch (e) {
    console.log(`health: UNAVAILABLE (${e instanceof Error ? e.message : e})`);
  }

  let tel = null;
  try {
    const body = await fetchJson(
      `/api/instrument-daily-opinions/telemetry?lookbackDays=${LOOKBACK}`,
    );
    tel = body?.data ?? body;
  } catch (e) {
    console.log(`telemetry: UNAVAILABLE (${e instanceof Error ? e.message : e})`);
  }

  if (tel) {
    const p1 = Number(tel.daysWithOpinions ?? 0);
    const prec = tel.buyPrecision5d;
    const recall = tel.buyRecall5d;
    const p3ok = prec != null && Number(prec) >= 0.7;
    const p4ok = recall != null && Number(recall) >= 0.55;
    console.log('');
    console.log('--- A0 telemetry (P1 / P3 / P4) ---');
    console.log(
      `P1 daysWithOpinions=${p1}  [${mark(p1 >= 60)}]  need≥60  gap=${Math.max(0, 60 - p1)}`,
    );
    console.log(
      `P3 buyPrecision5d=${prec} alarmaBuy=${tel.alarmaBuyCount} mature=${tel.matureBuySample}  [${mark(p3ok)}]  need≥0.70`,
    );
    console.log(
      `P4 buyRecall5d=${recall} caught=${tel.recallCaught}/${tel.recallMoveSample}  [${mark(p4ok)}]  need≥0.55`,
    );
  }

  if (skipDb) {
    console.log('');
    console.log('--- DB skipped (--no-db) ---');
    console.log('See docs/engineering/deuda-thaw-estricto-runbook-2026-08-25.md §2');
    return 0;
  }

  console.log('');
  console.log('--- Postgres (P2 / P5) ---');
  try {
    const confirmSeed = Number(
      await psql(
        `SELECT COUNT(*) FROM decision_sessions WHERE kind='confirm' AND account_id='${DEMO}'`,
      ),
    );
    const confirmAll = Number(
      await psql(`SELECT COUNT(*) FROM decision_sessions WHERE kind='confirm'`),
    );
    const journalSeed = Number(
      await psql(
        `SELECT COUNT(*) FROM decision_journal_entries WHERE account_id='${DEMO}'`,
      ),
    );
    const buysSeed = Number(
      await psql(
        `SELECT COUNT(*) FROM ledger_entries WHERE account_id='${DEMO}' AND type ILIKE '%buy%'`,
      ),
    );
    const tradeLike = Number(
      await psql(
        `SELECT COUNT(*) FROM ledger_entries WHERE account_id='${DEMO}' AND type NOT IN ('deposit','fee','withdraw')`,
      ),
    );
    const buysSplit = await psql(`
WITH buys AS (
  SELECT le.account_id, a.name, COUNT(*) AS n
  FROM ledger_entries le
  JOIN investment_accounts a ON a.id = le.account_id
  WHERE le.type ILIKE '%buy%'
  GROUP BY 1, 2
)
SELECT
  COALESCE(SUM(n) FILTER (WHERE name ~* '${TESTISH}'), 0)::text || '|' ||
  COALESCE(SUM(n) FILTER (WHERE name !~* '${TESTISH}'), 0)::text || '|' ||
  COALESCE(SUM(n), 0)::text
FROM buys`);
    const [buysTestish, buysNonTestish, buysAll] = (buysSplit || '0|0|0')
      .split('|')
      .map((x) => Number(x || 0));

    const maxDd = await psql(`
WITH cash AS (
  SELECT executed_at, balance_after::float AS bal
  FROM ledger_entries
  WHERE account_id='${DEMO}'
  ORDER BY executed_at, created_at
),
peaks AS (
  SELECT bal,
         MAX(bal) OVER (ORDER BY executed_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak
  FROM cash
)
SELECT COALESCE(MAX(CASE WHEN peak>0 THEN (peak-bal)/peak ELSE 0 END), 0)
FROM peaks`);
    const maxDdPct = (Number(maxDd) * 100).toFixed(2);

    const p2ok = confirmSeed >= 50;
    const p5ok = tradeLike > 0 && Number(maxDd) <= 0.1;
    const p5warn = tradeLike === 0;

    console.log(
      `P2 confirm_seed=${confirmSeed} confirm_all=${confirmAll} journal_seed=${journalSeed} buys_seed=${buysSeed}  [${mark(p2ok)}]  need≥50 confirm seed`,
    );
    console.log(
      `P2 noise buys_testish=${buysTestish} buys_non_testish=${buysNonTestish} buys_all=${buysAll}  (do not count testish toward 50)`,
    );
    console.log(
      `P5 trade_like=${tradeLike} cash_maxdd=${maxDdPct}%  [${mark(p5ok, p5warn)}]  need trades + ≤10% (+ Lab 1.2× when measured)`,
    );
    if (p5warn) {
      console.log('P5 note: 0 trades → cash DD is NOT a valid trading MaxDD');
    }
  } catch (e) {
    console.log(`db: UNAVAILABLE (${e instanceof Error ? e.message : e})`);
    console.log('hint: docker running? container bolsa-postgres? or pass --no-db');
  }

  console.log('');
  console.log('DoD: lift W2–W4 + Accept strict → runbook §4 (owner thaw word + ADR amend).');
  console.log('doc: docs/engineering/deuda-thaw-estricto-runbook-2026-08-25.md');
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
