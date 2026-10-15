#!/usr/bin/env node
/**
 * Parser READ-ONLY del informe de RED por intento del journey integrado S5
 * (`attachS5NetworkTimings` escribe `<S5_TIMINGS_OUT>.attempt<N>.json`).
 *
 * Por que existe (`S5-04`, post-`v2.88.135-beta`): el primer intento supera los 60 s
 * esperando la evidencia LAB y el retry pasa. `playwright-attempt-timings.mjs` declara
 * QUE `test.step` consume el tiempo; este modulo declara QUE COMPONENTE de red lo hace
 * (modulos de Vite en frio vs waterfall de API), agrupando por fase.
 *
 *   - NO cambia `timeout`, `retries` ni aserciones.
 *   - NO oculta el fallo: agrupa lo MEDIDO; un fichero ausente es un hueco declarado.
 *   - NO depende de red ni de PostgreSQL: lee los JSON y resume.
 *
 * Se ejercita con `node --test scripts/ci/s5-network-timings.test.mjs`.
 *
 * Uso:
 *   node scripts/ci/s5-network-timings.mjs /tmp/s5-network-timings.json
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

/** Numero finito o `null` (nunca un `0` de relleno: UNKNOWN != 0, y `null` es un hueco). */
function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Clasifica una peticion en una FASE legible. Las rutas `/api/*` pasan por el proxy de Vite
 * (mismo origen), asi que se distinguen por pathname; los modulos servidos por Vite dev
 * (`/src/*`, `/node_modules/*`, `/@vite*`, `/@fs*`, `/@id*`) son la sospecha del arranque en frio.
 */
export function classifyPhase(record) {
  const pathname = String(record?.pathname ?? '');
  const method = String(record?.method ?? '').toUpperCase();
  if (pathname.startsWith('/api/')) {
    if (pathname === '/api/backtests/run' && method === 'POST') return 'api:run';
    if (pathname.startsWith('/api/backtests/') && !pathname.endsWith('/run')) return 'api:detail';
    if (pathname.includes('/ohlcv')) return 'api:ohlcv';
    if (pathname.includes('/strategy-top')) return 'api:strategy-top';
    if (pathname.includes('/dia-d-verifications')) return 'api:dia-d-verifications';
    if (pathname.includes('/operational-monitor')) return 'api:monitor';
    return 'api:other';
  }
  if (pathname.startsWith('/src/')) return 'module:src';
  if (
    pathname.startsWith('/node_modules/') ||
    pathname.startsWith('/@vite') ||
    pathname.startsWith('/@fs') ||
    pathname.startsWith('/@id') ||
    pathname.includes('/.vite/')
  ) {
    return 'module:dep';
  }
  return 'other';
}

/**
 * Agrupa por fase: `count`, cuantas se midieron, la SUMA de duraciones (proxy del volumen
 * de trabajo) y el MAXIMO (la peticion mas lenta). Ordena por suma descendente.
 */
export function summarizeNetwork(records) {
  const byPhase = new Map();
  for (const record of Array.isArray(records) ? records : []) {
    const phase = classifyPhase(record);
    const entry =
      byPhase.get(phase) ?? { phase, count: 0, measured: 0, totalMs: 0, maxMs: 0, failed: 0 };
    entry.count += 1;
    if (record?.failed) entry.failed += 1;
    const duration = numberOrNull(record?.durationMs);
    if (duration !== null) {
      entry.measured += 1;
      entry.totalMs += duration;
      entry.maxMs = Math.max(entry.maxMs, duration);
    }
    byPhase.set(phase, entry);
  }
  return [...byPhase.values()].sort((a, b) => b.totalMs - a.totalMs || b.count - a.count);
}

/** Compara dos resumenes (primer intento vs retry) por fase y ordena por delta descendente. */
export function compareAttempts(firstSummary, retrySummary) {
  const phases = new Set([
    ...firstSummary.map((entry) => entry.phase),
    ...retrySummary.map((entry) => entry.phase),
  ]);
  const firstMap = new Map(firstSummary.map((entry) => [entry.phase, entry]));
  const retryMap = new Map(retrySummary.map((entry) => [entry.phase, entry]));
  const zero = { count: 0, totalMs: 0, maxMs: 0, measured: 0, failed: 0 };
  return [...phases]
    .map((phase) => {
      const first = firstMap.get(phase) ?? zero;
      const retry = retryMap.get(phase) ?? zero;
      return {
        phase,
        firstTotalMs: first.totalMs,
        retryTotalMs: retry.totalMs,
        deltaMs: first.totalMs - retry.totalMs,
        firstCount: first.count,
        retryCount: retry.count,
      };
    })
    .sort((a, b) => b.deltaMs - a.deltaMs);
}

/** Normaliza el JSON de un intento (tolerante a un payload parcial). */
export function parseAttemptFile(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const records = Array.isArray(raw.records) ? raw.records : [];
  const attempt = numberOrNull(raw.attempt);
  return { attempt: attempt ?? 0, records };
}

/** Ficheros de intento disponibles para una base (`<base>.attempt<N>.json`) o la base directa. */
export function collectAttemptFiles(base) {
  const out = [];
  if (existsSync(base)) out.push(base);
  const dir = path.dirname(base);
  const name = path.basename(base);
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    if (entry.startsWith(`${name}.attempt`) && entry.endsWith('.json')) {
      out.push(path.join(dir, entry));
    }
  }
  return out;
}

const fmtMs = (value) => (value === null ? 'hueco' : `${(value / 1000).toFixed(2)}s`);

/** Render legible y estable (para el log del job). */
export function formatTimings(attempts) {
  const lines = [
    '# AUTO S5 · red por intento (READ-ONLY; no cambia timeouts ni retries)',
    '',
  ];
  if (attempts.length === 0) {
    lines.push('(sin informes de red: hueco declarado, no un rojo)');
    return lines.join('\n');
  }
  for (const { attempt, summary, file } of attempts) {
    lines.push(`## Intento ${attempt} (${file})`);
    if (summary.length === 0) {
      lines.push('');
      lines.push('(sin peticiones medibles)');
      lines.push('');
      continue;
    }
    lines.push('');
    lines.push('| fase | peticiones | medida | suma | max | fallidas |');
    lines.push('| --- | --- | --- | --- | --- | --- |');
    for (const entry of summary) {
      lines.push(
        `| ${entry.phase} | ${entry.count} | ${entry.measured} | ` +
          `${fmtMs(entry.totalMs)} | ${fmtMs(entry.maxMs)} | ${entry.failed} |`,
      );
    }
    lines.push('');
  }
  const first = attempts.find((row) => row.attempt === 0) ?? attempts[0];
  const retry = attempts.find((row) => row.attempt > 0);
  if (first && retry) {
    lines.push('## Delta primer intento - retry (por fase; positivo = mas lento en frio)');
    lines.push('');
    lines.push('| fase | primero (suma) | retry (suma) | delta | peticiones 1o vs retry |');
    lines.push('| --- | --- | --- | --- | --- |');
    for (const row of compareAttempts(first.summary, retry.summary)) {
      if (row.firstTotalMs === 0 && row.retryTotalMs === 0) continue;
      lines.push(
        `| ${row.phase} | ${fmtMs(row.firstTotalMs)} | ${fmtMs(row.retryTotalMs)} | ` +
          `${fmtMs(row.deltaMs)} | ${row.firstCount} vs ${row.retryCount} |`,
      );
    }
    lines.push('');
  }
  return lines.join('\n');
}

export function main(argv) {
  const base = argv[2] ?? process.env.S5_TIMINGS_OUT?.trim();
  if (!base) {
    console.error('# uso: node scripts/ci/s5-network-timings.mjs <base.json>');
    return 1;
  }
  const files = collectAttemptFiles(base);
  const attempts = [];
  for (const file of files) {
    let parsed;
    try {
      parsed = parseAttemptFile(JSON.parse(readFileSync(file, 'utf8')));
    } catch (error) {
      // Un informe ausente/ilegible es un HUECO declarado, no un rojo.
      console.log(
        `# sin informe de red interpretable (${file}): ` +
          `${error instanceof Error ? error.message : error}`,
      );
      continue;
    }
    if (!parsed) continue;
    attempts.push({ ...parsed, summary: summarizeNetwork(parsed.records), file });
  }
  attempts.sort((a, b) => a.attempt - b.attempt);
  console.log(formatTimings(attempts));
  for (const { attempt, summary } of attempts) {
    const slowest = summary[0];
    if (slowest) {
      console.log(
        `# intento ${attempt}: fase mas pesada por suma ${slowest.phase} ` +
          `${fmtMs(slowest.totalMs)} (${slowest.count} peticiones)`,
      );
    }
  }
  return 0;
}

// Solo ejecuta el CLI cuando se invoca como programa (no al importarlo en tests).
const invokedPath = process.argv[1];
if (invokedPath && import.meta.url === pathToFileURL(invokedPath).href) {
  process.exitCode = main(process.argv);
}
