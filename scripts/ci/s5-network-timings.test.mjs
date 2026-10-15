/**
 * Regresiones del parser READ-ONLY de la RED por intento del journey S5.
 *
 * Muerden de verdad: si `classifyPhase` dejara de separar modulos de Vite de la API, o
 * `compareAttempts` fabricara un delta cuando falta el retry, o un informe ausente se
 * tratara como rojo, estos tests caen.
 *
 * Ejecutar: `node --test scripts/ci/s5-network-timings.test.mjs`.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

import {
  classifyPhase,
  collectAttemptFiles,
  compareAttempts,
  formatTimings,
  main,
  parseAttemptFile,
  summarizeNetwork,
} from './s5-network-timings.mjs';

/** Registro de red sintetico con la MISMA forma que emite `attachS5NetworkTimings`. */
function record(overrides) {
  return {
    index: 0,
    method: 'GET',
    pathname: '/api/health',
    resourceType: 'fetch',
    status: 200,
    durationMs: 10,
    offsetMs: 5,
    failed: false,
    failure: null,
    ...overrides,
  };
}

test('classifyPhase separa API, modulos de Vite y otros', () => {
  assert.equal(classifyPhase(record({ method: 'POST', pathname: '/api/backtests/run' })), 'api:run');
  assert.equal(classifyPhase(record({ pathname: '/api/backtests/abc-123' })), 'api:detail');
  assert.equal(classifyPhase(record({ pathname: '/api/instruments/x/ohlcv' })), 'api:ohlcv');
  assert.equal(classifyPhase(record({ pathname: '/api/instruments/x/strategy-top' })), 'api:strategy-top');
  assert.equal(classifyPhase(record({ pathname: '/api/auto/dia-d-verifications' })), 'api:dia-d-verifications');
  assert.equal(classifyPhase(record({ pathname: '/api/auto/operational-monitor' })), 'api:monitor');
  assert.equal(classifyPhase(record({ pathname: '/api/otra' })), 'api:other');
  assert.equal(classifyPhase(record({ pathname: '/src/features/backtests/dia-d-verify-host.tsx' })), 'module:src');
  assert.equal(classifyPhase(record({ pathname: '/node_modules/.vite/deps/react.js' })), 'module:dep');
  assert.equal(classifyPhase(record({ pathname: '/@vite/client' })), 'module:dep');
  assert.equal(classifyPhase(record({ pathname: '/favicon.ico', resourceType: 'image' })), 'other');
});

test('summarizeNetwork agrupa por fase, suma y saca el maximo sin rellenar huecos', () => {
  const summary = summarizeNetwork([
    record({ method: 'POST', pathname: '/api/backtests/run', durationMs: 500 }),
    record({ method: 'POST', pathname: '/api/backtests/run', durationMs: 300 }),
    record({ pathname: '/src/a.ts', durationMs: 40 }),
    record({ pathname: '/src/b.ts', durationMs: null }),
  ]);
  const run = summary.find((entry) => entry.phase === 'api:run');
  assert.equal(run.count, 2);
  assert.equal(run.measured, 2);
  assert.equal(run.totalMs, 800);
  assert.equal(run.maxMs, 500);
  const mod = summary.find((entry) => entry.phase === 'module:src');
  assert.equal(mod.count, 2);
  assert.equal(mod.measured, 1); // null => hueco, no 0
  assert.equal(mod.totalMs, 40);
  // Orden por suma descendente: la API pesa mas que un modulo.
  assert.equal(summary[0].phase, 'api:run');
});

test('compareAttempts da delta positivo cuando el primer intento es mas lento', () => {
  const first = summarizeNetwork([
    record({ pathname: '/src/a.ts', durationMs: 900 }),
    record({ method: 'POST', pathname: '/api/backtests/run', durationMs: 100 }),
  ]);
  const retry = summarizeNetwork([
    record({ pathname: '/src/a.ts', durationMs: 50 }),
    record({ method: 'POST', pathname: '/api/backtests/run', durationMs: 90 }),
  ]);
  const delta = compareAttempts(first, retry);
  assert.equal(delta[0].phase, 'module:src');
  assert.equal(delta[0].deltaMs, 850);
  assert.equal(delta[0].firstCount, 1);
  assert.equal(delta[0].retryCount, 1);
});

test('compareAttempts con una fase ausente usa hueco (0), no inventa', () => {
  const first = summarizeNetwork([record({ pathname: '/src/a.ts', durationMs: 500 })]);
  const retry = summarizeNetwork([]);
  const delta = compareAttempts(first, retry);
  assert.equal(delta[0].phase, 'module:src');
  assert.equal(delta[0].retryTotalMs, 0);
  assert.equal(delta[0].retryCount, 0);
});

test('parseAttemptFile tolera payload parcial y normaliza el intento', () => {
  assert.deepEqual(parseAttemptFile(null), null);
  assert.deepEqual(parseAttemptFile({ attempt: 1, records: [record({})] }).attempt, 1);
  assert.equal(parseAttemptFile({ record: [] }).records.length, 0);
});

test('formatTimings declara el delta y el hueco cuando no hay informes', () => {
  const text = formatTimings([
    {
      attempt: 0,
      file: '/tmp/x.attempt0.json',
      summary: summarizeNetwork([record({ pathname: '/src/a.ts', durationMs: 900 })]),
    },
    {
      attempt: 1,
      file: '/tmp/x.attempt1.json',
      summary: summarizeNetwork([record({ pathname: '/src/a.ts', durationMs: 50 })]),
    },
  ]);
  assert.match(text, /Delta primer intento - retry/);
  assert.match(text, /module:src/);
  assert.match(formatTimings([]), /sin informes de red: hueco declarado/);
});

test('collectAttemptFiles encuentra la base y los ficheros por intento', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 's5-net-'));
  try {
    const base = path.join(dir, 's5-network-timings.json');
    writeFileSync(base, '{}');
    writeFileSync(`${base}.attempt0.json`, '{}');
    writeFileSync(`${base}.attempt1.json`, '{}');
    writeFileSync(path.join(dir, 'otro.json'), '{}');
    const files = collectAttemptFiles(base).map((f) => path.basename(f)).sort();
    assert.deepEqual(files, [
      's5-network-timings.json',
      's5-network-timings.json.attempt0.json',
      's5-network-timings.json.attempt1.json',
    ]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

/** Captura `console.log`/`console.error` durante `fn` y devuelve las lineas emitidas por `log`. */
function captureLog(fn) {
  const lines = [];
  const originalLog = console.log;
  const originalError = console.error;
  console.log = (...args) => lines.push(args.join(' '));
  console.error = () => {};
  try {
    fn();
  } finally {
    console.log = originalLog;
    console.error = originalError;
  }
  return lines;
}

test('main con un informe AUSENTE declara el hueco y sale 0 (no rompe el job)', () => {
  const missing = 'scripts/ci/__no_existe__-net.json';
  let code;
  const lines = captureLog(() => {
    code = main(['node', 's5-network-timings.mjs', missing]);
  });
  assert.equal(code, 0);
  assert.match(lines.join('\n'), /sin informes de red: hueco declarado/);
});

test('main sin argumento es un uso incorrecto (exit 1)', () => {
  let code;
  captureLog(() => {
    code = main(['node', 's5-network-timings.mjs']);
  });
  assert.equal(code, 1);
});
