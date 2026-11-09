#!/usr/bin/env node
/**
 * Snapshot READ-ONLY de los cierres diarios del watch ESTUDIO (2026-11-09).
 *
 * **Por que existe.** A las 17:40 (BarsSync) la barra diaria europea puede quedar
 * **provisional**: la subasta de cierre termina a las 17:35 y algunos proveedores
 * consolidan despues. Si el cierre que usa la ventana difiere del que deja la
 * sincronizacion del dia siguiente, ese sesgo entra en todas las decisiones.
 *
 * **Que hace.** Copia a un JSON los cierres que hay en `ohlcv_bars` en el momento de
 * la captura, con la muestra por mercado (4 BME, 3 XETRA, 3 FR por defecto). No
 * escribe en la base de datos.
 *
 * Uso (raiz del repo):
 *   node scripts/snapshot-daily-closes.mjs --day 2026-11-09
 *   node scripts/snapshot-daily-closes.mjs --day 2026-11-09 --out operability_runs/quality/closes-20261109.json
 *   node scripts/snapshot-daily-closes.mjs --day 2026-11-09 --symbols SAN,ITX,SAP,SIE,AI,OR
 *
 * Codigos de salida: 0 captura escrita · 1 error de lectura/uso · 2 no hay cierres del dia.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';

import { ROOT } from './lib/logger.mjs';
import {
  SNAPSHOT_SCHEMA,
  DEFAULT_SAMPLE,
  readClosesFromDb,
  pickSample,
} from './lib/daily-closes.mjs';

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

function parseArgs(argv) {
  const flags = { day: null, out: null, symbols: [] };
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
    else if (name === '--out') flags.out = value();
    else if (name === '--symbols') {
      flags.symbols = value()
        .split(',')
        .map((symbol) => symbol.trim())
        .filter(Boolean);
    } else throw new Error(`argumento no reconocido: ${arg}`);
  }
  return flags;
}

function main() {
  let flags;
  try {
    flags = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.log(`[daily-closes] ${error.message}`);
    console.log('  uso: node scripts/snapshot-daily-closes.mjs --day YYYY-MM-DD [--out <path>] [--symbols A,B]');
    return 1;
  }
  if (!flags.day || !ISO_DAY_RE.test(flags.day)) {
    console.log('[daily-closes] --day es obligatorio y debe ser YYYY-MM-DD (p. ej. 2026-11-09)');
    return 1;
  }
  const read = readClosesFromDb({ day: flags.day, symbols: flags.symbols });
  if (read.error) {
    console.log(`[daily-closes] no se pudo leer PostgreSQL: ${read.error}`);
    return 1;
  }
  const selection =
    flags.symbols.length > 0
      ? { rows: read.rows, shortfall: {} }
      : pickSample(read.rows, DEFAULT_SAMPLE);
  if (selection.rows.length === 0) {
    console.log(`[daily-closes] no hay cierres de ${flags.day} en ohlcv_bars: nada que capturar`);
    return 2;
  }
  const payload = {
    schema: SNAPSHOT_SCHEMA,
    day: flags.day,
    capturedAt: new Date().toISOString(),
    listId: 'estudio',
    sample: flags.symbols.length > 0 ? 'explicit' : DEFAULT_SAMPLE,
    shortfall: selection.shortfall,
    skipped: read.skipped,
    rows: selection.rows,
  };
  const out = flags.out
    ? isAbsolute(flags.out)
      ? flags.out
      : join(ROOT, flags.out)
    : join(ROOT, 'operability_runs', 'quality', `closes-${flags.day.replace(/-/g, '')}.json`);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');

  console.log(`[daily-closes] snapshot ${flags.day} · ${selection.rows.length} valores · ${out}`);
  for (const row of selection.rows) {
    console.log(
      `  ${String(row.symbol).padEnd(8)}${String(row.market).padEnd(4)}` +
        `close ${row.close}  (${row.yahooSymbol || 'sin yahoo_symbol'})`,
    );
  }
  if (read.skipped > 0) {
    console.log(`  aviso: ${read.skipped} fila(s) descartada(s) por precio ilegible o close <= 0`);
  }
  if (Object.keys(selection.shortfall).length > 0) {
    console.log(`  aviso: muestra incompleta ${JSON.stringify(selection.shortfall)}`);
  }
  return 0;
}

process.exit(main());
