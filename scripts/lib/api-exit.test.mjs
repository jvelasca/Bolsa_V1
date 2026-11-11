/**
 * Regresiones del criterio `api-exit:<code>` (caída de la API diagnosticable).
 *
 * Lo que se protege (medido el 2026-11-11 sobre 3f7cd5e9):
 *   - un exit no-cero se declara con su código;
 *   - un exit 0 NO queda mudo (antes `if (code && code !== 0)` lo ignoraba);
 *   - una muerte por señal (`code === null`) se declara con la señal;
 *   - el motivo identifica proceso (rol, pid, code, signal, uptime) y adjunta
 *     las últimas líneas del stderr, que es la causa real.
 *
 * Ejecutar: `node --test scripts/lib/api-exit.test.mjs` (o `pnpm dev:test`).
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { apiExitFacts, apiExitReason, describeApiExit, lastLines } from './api-exit.mjs';

test('apiExitReason: exit no-cero conserva el código', () => {
  assert.equal(apiExitReason({ code: 1 }), 'api-exit:1');
  assert.equal(apiExitReason({ code: 137, signal: null }), 'api-exit:137');
});

test('apiExitReason: exit 0 también se declara', () => {
  assert.equal(apiExitReason({ code: 0 }), 'api-exit:0');
});

test('apiExitReason: muerte por señal se declara con la señal', () => {
  assert.equal(apiExitReason({ code: null, signal: 'SIGKILL' }), 'api-exit:signal:SIGKILL');
  assert.equal(apiExitReason({ code: null, signal: 'SIGTERM' }), 'api-exit:signal:SIGTERM');
});

test('apiExitReason: sin código ni señal no inventa un motivo', () => {
  assert.equal(apiExitReason({}), 'api-exit:unknown');
  assert.equal(apiExitReason(), 'api-exit:unknown');
});

test('apiExitFacts: identifica rol, pid, código, señal y uptime', () => {
  const facts = apiExitFacts({
    code: 1,
    signal: null,
    pid: 48232,
    uptimeMs: 12345,
    lastLines: ['a', 'b'],
  });
  assert.deepEqual(facts, {
    role: 'api',
    pid: 48232,
    code: 1,
    signal: null,
    uptimeMs: 12345,
    lastLines: ['a', 'b'],
  });
});

test('apiExitFacts: sin pid ni uptime no inventa campos', () => {
  assert.deepEqual(apiExitFacts({ code: 0 }), { role: 'api', code: 0, signal: null });
});

test('describeApiExit: una línea con pid, motivo y última línea de stderr', () => {
  const facts = apiExitFacts({
    code: 1,
    signal: null,
    pid: 48232,
    uptimeMs: 1000,
    lastLines: ['Traceback (most recent call last):', 'psycopg.OperationalError: connection refused'],
  });
  const reason = apiExitReason(facts);
  const text = describeApiExit({ reason, facts });
  assert.match(text, /rol=api/);
  assert.match(text, /pid=48232/);
  assert.match(text, /code=1/);
  assert.match(text, /api-exit:1/);
  assert.match(text, /se detiene el stack/);
  assert.match(text, /último stderr: psycopg\.OperationalError: connection refused/);
});

test('describeApiExit: sin datos no rompe el formato', () => {
  const text = describeApiExit({ reason: 'api-exit:signal:SIGKILL', facts: apiExitFacts() });
  assert.match(text, /pid=-/);
  assert.match(text, /code=-/);
  assert.match(text, /signal=-/);
  assert.match(text, /api-exit:signal:SIGKILL/);
});

test('lastLines: respeta CRLF, recorta y descarta vacías', () => {
  const stderr = 'INFO arrancando\r\n\r\n  ERROR 1  \nERROR 2\n\n';
  assert.deepEqual(lastLines(stderr, 2), ['ERROR 1', 'ERROR 2']);
  assert.deepEqual(lastLines(''), []);
  assert.deepEqual(lastLines('una sola'), ['una sola']);
});
