/**
 * Puerta de completitud de barras diarias del watch ESTUDIO (2026-11-09).
 *
 * **Problema que cierra.** El `run-day` de las 18:30 mide con la barra del dia ya
 * persistida (`AUTO_ENGINE_SIM_REAL_PRICE=1`). Si `BarsSync` (17:40) falla y el
 * worker de auto-sync no alcanza a drenar, el dia se registra **MEDIDO con cero
 * senales**: no es lo mismo que un dia sin oportunidades. Ese dia envenena el gate
 * (`>=4 dias / >=2 episodios / >=32 ciclos`) y nadie lo detecta despues.
 *
 * **Contrato.** Antes del preflight se cuenta, en PostgreSQL, cuantas barras del dia
 * existen para los miembros de la lista ESTUDIO. Si la cobertura no llega al umbral,
 * el runner espera (hasta un maximo) y, si no llega, **aborta sin marcar el dia como
 * terminal**: no escribe fila en el ledger y la proxima ejecucion lo reintenta.
 *
 * Fail-closed declarado: si la lista ESTUDIO no tiene el tamano esperado (80), la
 * puerta **falla** en vez de medir un universo que no es el canonico.
 *
 * `scripts/` no participa del freeze (`HEAD:apps` / `HEAD:packages`).
 */
import { spawnSync } from 'node:child_process';

import { psqlBase } from './docker.mjs';

/** Lista canonica del watch de la ventana PAPER. */
export const ESTUDIO_LIST_ID = 'estudio';
/** Tamano esperado de la lista ESTUDIO (cambiar exige decision explicita). */
export const ESTUDIO_EXPECTED_MEMBERS = 80;
/** Cobertura minima para medir: 95 % de 80 = 76 barras. */
export const DEFAULT_MIN_COVERAGE = 0.95;
/** Espera maxima de la puerta: 30 min. */
export const DEFAULT_WAIT_SECONDS = 1800;
/** Sondeo entre reintentos de la puerta: 60 s. */
export const DEFAULT_POLL_SECONDS = 60;

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const SAFE_ID_RE = /^[a-zA-Z0-9_-]+$/;

/**
 * SQL de cobertura: por cada miembro de la lista, ¿hay barra diaria del dia con
 * `close > 0`? Una barra ausente NO se cuenta; una barra con `close = 0` tampoco
 * (el defecto `mark = 0.0` documentado en la auditoria).
 *
 * @param {{day: string, listId?: string}} parts
 * @returns {string}
 */
export function coverageSql({ day, listId = ESTUDIO_LIST_ID }) {
  const iso = String(day ?? '').trim();
  if (!ISO_DAY_RE.test(iso)) {
    throw new Error('coverageSql: `day` debe ser YYYY-MM-DD');
  }
  const id = String(listId ?? '').trim();
  if (!SAFE_ID_RE.test(id)) {
    throw new Error('coverageSql: `listId` invalido');
  }
  return [
    'SELECT count(*) AS total,',
    "       count(*) FILTER (WHERE b.close > 0) AS covered",
    'FROM instrument_list_items li',
    'JOIN instruments i ON i.id = li.instrument_id',
    'LEFT JOIN ohlcv_bars b',
    '  ON b.instrument_id = li.instrument_id',
    " AND b.timeframe = '1d'",
    ` AND b.timestamp >= '${iso}'::date`,
    ` AND b.timestamp < ('${iso}'::date + interval '1 day')`,
    `WHERE li.list_id = '${id}';`,
  ].join('\n');
}

/**
 * Parsea la salida `psql -t -A -F "|"` de `coverageSql`. Devuelve `null` si no hay
 * una fila `total|covered` valida (nunca inventa cero).
 *
 * @param {string} text
 * @returns {{total: number, covered: number} | null}
 */
export function parseCoverage(text) {
  const lines = String(text ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const last = lines.at(-1);
  if (!last) return null;
  const [totalRaw, coveredRaw] = last.split('|');
  const total = Number(totalRaw);
  const covered = Number(coveredRaw);
  if (!Number.isFinite(total) || !Number.isFinite(covered)) return null;
  if (total < 0 || covered < 0 || covered > total) return null;
  return { total: Math.trunc(total), covered: Math.trunc(covered) };
}

/**
 * Decide si la cobertura alcanza para medir. **Puro.**
 *
 * @param {{total: number, covered: number, minCoverage?: number,
 *          expectedMembers?: number}} parts
 * @returns {{ok: boolean, ratio: number, missing: number, requiredCovered: number,
 *            reason: string | null}}
 */
export function coverageDecision({
  total,
  covered,
  minCoverage = DEFAULT_MIN_COVERAGE,
  expectedMembers = ESTUDIO_EXPECTED_MEMBERS,
}) {
  const rows = Number(total);
  const filled = Number(covered);
  const expected = Number(expectedMembers);
  const min = Number(minCoverage);
  if (!Number.isFinite(rows) || !Number.isFinite(filled) || rows <= 0) {
    return {
      ok: false,
      ratio: 0,
      missing: 0,
      requiredCovered: 0,
      reason: 'SIN_MIEMBROS',
    };
  }
  if (Number.isFinite(expected) && expected > 0 && rows !== expected) {
    // Fail-closed: medir otra lista (o una lista truncada) no es la ventana.
    return {
      ok: false,
      ratio: filled / rows,
      missing: Math.max(0, rows - filled),
      requiredCovered: Math.ceil(rows * min - 1e-9),
      reason: 'ESTUDIO_SIZE_MISMATCH',
    };
  }
  const requiredCovered = Math.max(1, Math.ceil(rows * min - 1e-9));
  const ok = filled >= requiredCovered;
  return {
    ok,
    ratio: filled / rows,
    missing: Math.max(0, rows - filled),
    requiredCovered,
    reason: ok ? null : 'BARS_INCOMPLETE',
  };
}

/**
 * Lee la cobertura de PostgreSQL con el mismo transporte que el resto de scripts
 * (`docker exec bolsa-postgres` por defecto; `BOLSA_DR_TCP=1` para CI).
 *
 * @param {{day: string, listId?: string, db?: string}} parts
 * @returns {{total: number, covered: number, sql: string, error: string | null}}
 */
export function readCoverageFromDb({ day, listId = ESTUDIO_LIST_ID, db = 'bolsa_v1' }) {
  const sql = coverageSql({ day, listId });
  const base = psqlBase({ db });
  const result = spawnSync(
    base.bin,
    [...base.argv, '-t', '-A', '-F', '|', '-c', sql],
    { encoding: 'utf8', env: { ...process.env, ...base.env } },
  );
  if (result.status !== 0) {
    const detail = String(result.stderr ?? result.stdout ?? '').trim();
    return {
      total: 0,
      covered: 0,
      sql,
      error: `psql exit ${result.status ?? 'null'}: ${detail || 'sin detalle'}`,
    };
  }
  const parsed = parseCoverage(result.stdout);
  if (!parsed) {
    return {
      total: 0,
      covered: 0,
      sql,
      error: 'cobertura ilegible (se esperaba "total|covered")',
    };
  }
  return { ...parsed, sql, error: null };
}
