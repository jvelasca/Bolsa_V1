/**
 * Regresiones del conflicto de puertos del supervisor `window-stack-ready.mjs`.
 *
 * Lo que se protege (medido el 2026-11-09):
 *   - la web es 5173, NO 3002 (3002 es el puente XTB mock);
 *   - un puente XTB huerfano NO bloquea el arranque del stack;
 *   - un API ocupado SI bloquea (no se arranca un segundo uvicorn).
 *
 * Ejecutar: `node --test scripts/lib/stack-ports.test.mjs`.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { decidePortConflict, describePortConflict, stackPorts } from './stack-ports.mjs';

test('stackPorts: defaults reales del stack (web 5173, puente 3002)', () => {
  assert.deepEqual(stackPorts({}), { api: 8000, web: 5173, bridge: 3002 });
});

test('stackPorts: respeta el entorno y API_PORT como respaldo', () => {
  assert.deepEqual(
    stackPorts({ API_PYTHON_PORT: '9000', WEB_PORT: '6000', XTB_BRIDGE_PORT: '4000' }),
    { api: 9000, web: 6000, bridge: 4000 },
  );
  assert.equal(stackPorts({ API_PORT: '9100' }).api, 9100);
  // API_PYTHON_PORT gana a API_PORT, como en run-dev.mjs.
  assert.equal(stackPorts({ API_PYTHON_PORT: '9000', API_PORT: '9100' }).api, 9000);
});

test('decidePortConflict: API ocupado bloquea', () => {
  const decision = decidePortConflict({ api: [111] });
  assert.equal(decision.block, true);
  assert.deepEqual(decision.api, [111]);
  assert.deepEqual(decision.stale, []);
});

test('decidePortConflict: puente XTB huerfano NO bloquea (el bug de 3002)', () => {
  const decision = decidePortConflict({ api: [], web: [], bridge: [18988] });
  assert.equal(decision.block, false);
  assert.deepEqual(decision.stale, [18988]);
  assert.deepEqual(decision.byRole.bridge, [18988]);
});

test('decidePortConflict: web ocupada NO bloquea y se declara como stale', () => {
  const decision = decidePortConflict({ web: [22900] });
  assert.equal(decision.block, false);
  assert.deepEqual(decision.byRole.web, [22900]);
  assert.deepEqual(decision.stale, [22900]);
});

test('decidePortConflict: sin listeners no hay conflicto', () => {
  const decision = decidePortConflict({});
  assert.equal(decision.block, false);
  assert.deepEqual(decision.stale, []);
});

test('describePortConflict: nombra cada puerto con su rol', () => {
  const ports = { api: 8000, web: 5173, bridge: 3002 };
  const decision = decidePortConflict({ api: [1], web: [2], bridge: [3] });
  const text = describePortConflict(ports, decision);
  assert.match(text, /API :8000 \(PID 1\)/);
  assert.match(text, /web :5173 \(PID 2\)/);
  assert.match(text, /puente XTB :3002 \(PID 3\)/);
});
