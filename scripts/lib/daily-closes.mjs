/**
 * Calidad del cierre diario (2026-11-09) — helpers PUROS + lectura read-only.
 *
 * **Que mide.** A las 17:40 la barra diaria europea puede quedar **provisional**: la
 * subasta de cierre termina a las 17:35 y algunos proveedores consolidan mas tarde.
 * Si el cierre que se usa para medir (17:40) difiere del que deja la sincronizacion
 * del dia siguiente, el sesgo entra en **todas** las decisiones del forward.
 *
 * **Que hace este modulo.** Captura el cierre del dia en un JSON
 * (`snapshot-daily-closes.mjs`) y, al dia siguiente, compara el cierre persistido con
 * el actual en bps (`compare-daily-closes.mjs`). Read-only sobre PostgreSQL.
 */
import { spawnSync } from 'node:child_process';

import { psqlBase } from './docker.mjs';

/** Esquema del snapshot (un cambio de forma exige subir la version). */
export const SNAPSHOT_SCHEMA = 'bolsa-daily-closes-v1';
/** Lista canonica del watch de la ventana PAPER. */
export const ESTUDIO_LIST_ID = 'estudio';
/** Umbral por defecto: 10 bps sobre el cierre. */
export const DEFAULT_THRESHOLD_BPS = 10;
/** Reparto por defecto de la muestra (4 BME, 3 XETRA, 3 FR = 10 valores). */
export const DEFAULT_SAMPLE = Object.freeze({ ES: 4, DE: 3, FR: 3 });

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const SAFE_ID_RE = /^[a-zA-Z0-9_-]+$/;

/**
 * Mercado de un instrumento por el sufijo de su simbolo de Yahoo. `exchange` no
 * sirve: 129 de 197 instrumentos estan en `UNKNOWN`.
 *
 * @param {string} yahooSymbol
 * @returns {'ES' | 'DE' | 'FR' | 'OTHER'}
 */
export function marketBucket(yahooSymbol) {
  const symbol = String(yahooSymbol ?? '').trim().toUpperCase();
  if (symbol.endsWith('.MC')) return 'ES';
  if (symbol.endsWith('.DE')) return 'DE';
  if (symbol.endsWith('.PA')) return 'FR';
  return 'OTHER';
}

/**
 * SQL de cierres del dia para la lista indicada. Solo barras `close > 0`.
 *
 * @param {{day: string, listId?: string, symbols?: string[]}} parts
 * @returns {string}
 */
export function closesSql({ day, listId = ESTUDIO_LIST_ID, symbols = [] }) {
  const iso = String(day ?? '').trim();
  if (!ISO_DAY_RE.test(iso)) {
    throw new Error('closesSql: `day` debe ser YYYY-MM-DD');
  }
  const id = String(listId ?? '').trim();
  if (!SAFE_ID_RE.test(id)) {
    throw new Error('closesSql: `listId` invalido');
  }
  const wanted = (symbols ?? []).map((symbol) => String(symbol).trim()).filter(Boolean);
  if (wanted.some((symbol) => !SAFE_ID_RE.test(symbol))) {
    throw new Error('closesSql: simbolo invalido');
  }
  const filter =
    wanted.length > 0
      ? ` AND i.symbol = ANY(ARRAY[${wanted.map((symbol) => `'${symbol}'`).join(', ')}])`
      : '';
  return [
    'SELECT i.symbol, i.yahoo_symbol, i.exchange,',
    '       b.open, b.high, b.low, b.close, b.volume, b.created_at, b.source',
    'FROM instrument_list_items li',
    'JOIN instruments i ON i.id = li.instrument_id',
    'JOIN ohlcv_bars b',
    '  ON b.instrument_id = li.instrument_id',
    " AND b.timeframe = '1d'",
    ` AND b.timestamp >= '${iso}'::date`,
    ` AND b.timestamp < ('${iso}'::date + interval '1 day')`,
    `WHERE li.list_id = '${id}'`,
    '  AND b.close > 0' + filter,
    'ORDER BY i.symbol;',
  ].join('\n');
}

/**
 * Parsea la salida `psql -t -A -F "|"` de `closesSql`. Ignora filas mal formadas
 * (no inventa precios): una fila ilegible se descarta y se cuenta.
 *
 * @param {string} text
 * @returns {{rows: Array<Record<string, unknown>>, skipped: number}}
 */
export function parseCloses(text) {
  const rows = [];
  let skipped = 0;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const [
      symbol,
      yahooSymbol,
      exchange,
      open,
      high,
      low,
      close,
      volume,
      createdAt,
      source,
    ] = trimmed.split('|');
    const closeValue = Number(close);
    if (!symbol || !Number.isFinite(closeValue) || closeValue <= 0) {
      skipped += 1;
      continue;
    }
    rows.push({
      symbol,
      yahooSymbol: yahooSymbol ?? '',
      exchange: exchange ?? '',
      market: marketBucket(yahooSymbol),
      open: Number(open),
      high: Number(high),
      low: Number(low),
      close: closeValue,
      volume: Number(volume),
      createdAt: createdAt ?? '',
      source: source ?? '',
    });
  }
  return { rows, skipped };
}

/**
 * Muestra determinista por mercado: ordena por simbolo dentro de cada mercado y
 * corta `perMarket`. Si un mercado no tiene suficientes, se declara en `shortfall`.
 *
 * @param {Array<Record<string, unknown>>} rows
 * @param {Record<string, number>} [perMarket]
 */
export function pickSample(rows, perMarket = DEFAULT_SAMPLE) {
  const picked = [];
  const shortfall = {};
  for (const [market, count] of Object.entries(perMarket)) {
    const bucket = rows
      .filter((row) => row.market === market)
      .sort((a, b) => String(a.symbol).localeCompare(String(b.symbol)));
    picked.push(...bucket.slice(0, count));
    if (bucket.length < count) shortfall[market] = count - bucket.length;
  }
  return { rows: picked, shortfall };
}

/**
 * Desvio relativo en puntos basicos entre dos cierres. **Puro.**
 * Devuelve `null` cuando no se puede comparar (falta un lado o `before <= 0`).
 *
 * @param {number} before
 * @param {number} after
 * @returns {number | null}
 */
export function deviationBps(before, after) {
  const a = Number(before);
  const b = Number(after);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0) return null;
  return ((b - a) / a) * 10_000;
}

/**
 * Compara el snapshot con las filas actuales. **Puro.**
 *
 * @param {{snapshot: {rows: Array<{symbol: string, close: number}>},
 *          current: Array<{symbol: string, close: number}>,
 *          thresholdBps?: number}} parts
 */
export function compareCloses({ snapshot, current, thresholdBps = DEFAULT_THRESHOLD_BPS }) {
  const threshold = Number(thresholdBps);
  const bySymbol = new Map((current ?? []).map((row) => [row.symbol, row]));
  const comparisons = [];
  for (const before of snapshot?.rows ?? []) {
    const after = bySymbol.get(before.symbol);
    if (!after) {
      comparisons.push({
        symbol: before.symbol,
        market: before.market ?? null,
        before: before.close,
        after: null,
        bps: null,
        status: 'FALTA',
      });
      continue;
    }
    const bps = deviationBps(before.close, after.close);
    comparisons.push({
      symbol: before.symbol,
      market: before.market ?? null,
      before: before.close,
      after: after.close,
      bps: bps === null ? null : Number(bps.toFixed(2)),
      status: bps === null ? 'NO_COMPARABLE' : Math.abs(bps) > threshold ? 'FUERA' : 'DENTRO',
    });
  }
  const flagged = comparisons.filter((row) => row.status !== 'DENTRO');
  const worst = comparisons
    .filter((row) => row.bps !== null)
    .sort((a, b) => Math.abs(b.bps) - Math.abs(a.bps))[0] ?? null;
  return {
    thresholdBps: threshold,
    compared: comparisons.length,
    within: comparisons.length - flagged.length,
    flagged: flagged.length,
    worst,
    comparisons,
    ok: flagged.length === 0,
  };
}

/**
 * Lee los cierres del dia desde PostgreSQL con el transporte comun.
 *
 * @param {{day: string, listId?: string, symbols?: string[], db?: string}} parts
 */
export function readClosesFromDb({ day, listId = ESTUDIO_LIST_ID, symbols = [], db = 'bolsa_v1' }) {
  const sql = closesSql({ day, listId, symbols });
  const base = psqlBase({ db });
  const result = spawnSync(base.bin, [...base.argv, '-t', '-A', '-F', '|', '-c', sql], {
    encoding: 'utf8',
    env: { ...process.env, ...base.env },
  });
  if (result.status !== 0) {
    const detail = String(result.stderr ?? result.stdout ?? '').trim();
    return {
      rows: [],
      skipped: 0,
      error: `psql exit ${result.status ?? 'null'}: ${detail || 'sin detalle'}`,
    };
  }
  return { ...parseCloses(result.stdout), error: null };
}
