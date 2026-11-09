#!/usr/bin/env node
/**
 * Comparacion READ-ONLY del cierre persistido en el snapshot con el cierre actual
 * (2026-11-09). Mide la deriva en **puntos basicos** y falla si supera el umbral.
 *
 * **Por que existe.** Si la barra de las 17:40 era provisional, la sincronizacion
 * del dia siguiente la reescribe (upsert por `instrumento/timeframe/timestamp`). El
 * desvio entre ambos cierres es el sesgo sistematico que arrastrarian todas las
 * decisiones del forward.
 *
 * Uso (raiz del repo, DESPUES del BarsSync del dia siguiente):
 *   node scripts/compare-daily-closes.mjs --day 2026-11-09
 *   node scripts/compare-daily-closes.mjs --day 2026-11-09 --threshold-bps 10 --json
 *
 * Codigos de salida:
 *   0  todos los valores dentro del umbral
 *   1  algun valor fuera del umbral, falta o no es comparable; o material ilegible
 *   2  uso incorrecto
 */
import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';

import { ROOT } from './lib/logger.mjs';
import {
  DEFAULT_THRESHOLD_BPS,
  SNAPSHOT_SCHEMA,
  compareCloses,
  readClosesFromDb,
} from './lib/daily-closes.mjs';

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

function parseArgs(argv) {
  const flags = { day: null, snapshot: null, thresholdBps: DEFAULT_THRESHOLD_BPS, json: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const [name, inline] = arg.includes('=')
      ? [arg.slice(0, arg.indexOf('=')), arg.slice(arg.indexOf('=') + 1)]
      : [arg, null];
    const value = () => {
      if (inline !== null) return inline;
      const next = argv[i + 1];
      if (next === undefined) throw new Error(`falta el valor de ${name}`);
      i += 1;
      return next;
    };
    if (name === '--day') flags.day = value();
    else if (name === '--snapshot') flags.snapshot = value();
    else if (name === '--threshold-bps') flags.thresholdBps = Number(value());
    else if (name === '--json') flags.json = true;
    else throw new Error(`argumento no reconocido: ${arg}`);
  }
  return flags;
}

function resolvePath(target) {
  return isAbsolute(target) ? target : join(ROOT, target);
}

function main() {
  let flags;
  try {
    flags = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.log(`[daily-closes] ${error.message}`);
    console.log(
      '  uso: node scripts/compare-daily-closes.mjs --day YYYY-MM-DD [--snapshot <path>] [--threshold-bps 10] [--json]',
    );
    return 2;
  }
  if (!flags.day || !ISO_DAY_RE.test(flags.day)) {
    console.log('[daily-closes] --day es obligatorio y debe ser YYYY-MM-DD (p. ej. 2026-11-09)');
    return 2;
  }
  if (!Number.isFinite(flags.thresholdBps) || flags.thresholdBps <= 0) {
    console.log('[daily-closes] --threshold-bps debe ser un numero positivo');
    return 2;
  }
  const snapshotPath = flags.snapshot
    ? resolvePath(flags.snapshot)
    : join(ROOT, 'operability_runs', 'quality', `closes-${flags.day.replace(/-/g, '')}.json`);
  if (!existsSync(snapshotPath)) {
    console.log(
      `[daily-closes] falta el snapshot ${snapshotPath}; ejecuta snapshot-daily-closes.mjs el dia de la captura`,
    );
    return 1;
  }
  let snapshot;
  try {
    snapshot = JSON.parse(readFileSync(snapshotPath, 'utf8'));
  } catch (error) {
    console.log(`[daily-closes] snapshot ilegible: ${error.message}`);
    return 1;
  }
  if (snapshot?.schema !== SNAPSHOT_SCHEMA) {
    console.log(
      `[daily-closes] esquema del snapshot no soportado (${snapshot?.schema ?? 'n/d'}); se esperaba ${SNAPSHOT_SCHEMA}`,
    );
    return 1;
  }
  if (snapshot.day !== flags.day) {
    console.log(
      `[daily-closes] el snapshot es del ${snapshot.day}, no del ${flags.day} (no se compara material ajeno)`,
    );
    return 1;
  }
  const symbols = (snapshot.rows ?? []).map((row) => row.symbol).filter(Boolean);
  const current = readClosesFromDb({ day: flags.day, symbols });
  if (current.error) {
    console.log(`[daily-closes] no se pudo leer PostgreSQL: ${current.error}`);
    return 1;
  }
  const result = compareCloses({
    snapshot,
    current: current.rows,
    thresholdBps: flags.thresholdBps,
  });

  if (flags.json) {
    console.log(JSON.stringify({ day: flags.day, snapshot: snapshotPath, ...result }, null, 2));
  } else {
    console.log(
      `[daily-closes] dia ${flags.day} · umbral ${result.thresholdBps} bps · ` +
        `${result.compared} comparados · dentro ${result.within} · fuera ${result.flagged}`,
    );
    if (result.worst) {
      console.log(
        `  peor: ${result.worst.symbol} (${result.worst.market ?? 'n/d'}) ` +
          `${result.worst.before} -> ${result.worst.after ?? 'n/d'} · ${result.worst.bps ?? 'n/d'} bps`,
      );
    }
    console.log('');
    console.log(`${'simbolo'.padEnd(9)}${'mercado'.padEnd(9)}${'antes'.padEnd(13)}${'ahora'.padEnd(13)}${'bps'.padEnd(10)}estado`);
    console.log('-'.repeat(72));
    for (const row of result.comparisons) {
      console.log(
        `${String(row.symbol).padEnd(9)}${String(row.market ?? 'n/d').padEnd(9)}` +
          `${String(row.before).padEnd(13)}${String(row.after ?? 'n/d').padEnd(13)}` +
          `${String(row.bps ?? 'n/d').padEnd(10)}${row.status}`,
      );
    }
    console.log('-'.repeat(72));
  }
  if (!result.ok) {
    console.log(
      '[daily-closes] DERIVA POR ENCIMA DEL UMBRAL: revisar si el cierre de la ventana fue provisional.',
    );
    return 1;
  }
  console.log('[daily-closes] cierres estables dentro del umbral.');
  return 0;
}

process.exit(main());
