/**
 * Regresiones del parser READ-ONLY de tiempos por intento de Playwright.
 *
 * Muerden de verdad: si `summarizeAttempts` dejara de distinguir el primer intento del
 * retry, o fabricara un `0`/delta cuando falta un intento, estos tests caen.
 *
 * Ejecutar: `node --test scripts/ci/playwright-attempt-timings.test.mjs`.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  collectSpecs,
  flattenSteps,
  formatTimings,
  isS5Journey,
  main,
  summarizeAttempts,
} from './playwright-attempt-timings.mjs';

/** Informe sintetico con la MISMA forma que el reporter JSON de Playwright. */
function reportWithS5() {
  return {
    config: {},
    suites: [
      {
        title: 'gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts',
        file: 'gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts',
        specs: [],
        suites: [
          {
            title: 'GP-V288-S5 — puente AUTO → estrategia → DÍA-D (API real)',
            file: 'gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts',
            specs: [
              {
                title: 'GP-V288-S5-04: guardar registra el enlace durable verificación ↔ cicloId (P2)',
                ok: true,
                tests: [
                  {
                    projectName: 'chromium',
                    results: [
                      {
                        retry: 0,
                        status: 'timedOut',
                        duration: 61_234,
                        steps: [
                          { title: 'S5-04 · abrir la operación AUTO', duration: 5_120, steps: [] },
                          {
                            title: 'S5-04 · esperar la evidencia de la sesión LAB',
                            duration: 55_100,
                            steps: [
                              { title: 'expect.toBeVisible', duration: 54_800, steps: [] },
                            ],
                          },
                        ],
                      },
                      {
                        retry: 1,
                        status: 'passed',
                        duration: 5_500,
                        steps: [
                          { title: 'S5-04 · esperar la evidencia de la sesión LAB', duration: 1_200, steps: [] },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                title: 'GP-V288-S5-01: /auto/operar monta y declara su estado',
                ok: true,
                tests: [
                  {
                    projectName: 'chromium',
                    results: [{ retry: 0, status: 'passed', duration: 900, steps: [] }],
                  },
                ],
              },
            ],
            suites: [],
          },
        ],
      },
    ],
  };
}

test('collectSpecs aplana suites anidadas heredando el fichero', () => {
  const rows = collectSpecs(reportWithS5());
  assert.equal(rows.length, 2);
  assert.equal(rows[0].file, 'gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts');
  assert.match(rows[0].spec.title, /S5-04/);
});

test('summarizeAttempts separa primer intento y retry sin fabricar el delta', () => {
  const [s5] = summarizeAttempts(reportWithS5());
  assert.equal(s5.retries, 1);
  assert.equal(s5.firstMs, 61_234);
  assert.equal(s5.retryMs, 5_500);
  assert.equal(s5.deltaMs, 55_734); // primero - retry, positivo = el retry fue mas rapido
  assert.equal(s5.ok, true);
  assert.equal(s5.attempts[0].status, 'timedOut');
  assert.equal(s5.attempts[1].status, 'passed');
});

test('summarizeAttempts sin retry declara el delta como hueco (null), nunca 0', () => {
  const summary = summarizeAttempts(reportWithS5());
  const plain = summary.find((row) => /S5-01/.test(row.title));
  assert.equal(plain.firstMs, 900);
  assert.equal(plain.retryMs, null);
  assert.equal(plain.deltaMs, null);
  assert.equal(plain.retries, 0);
});

test('summarizeAttempts ordena los pasos mas lentos y aplana los anidados', () => {
  const [s5] = summarizeAttempts(reportWithS5());
  const first = s5.attempts[0];
  // El paso PADRE nombrado (la fase que consume el tiempo) no se pierde frente a sus hijos.
  assert.equal(first.slowestSteps[0].title, 'S5-04 · esperar la evidencia de la sesión LAB');
  assert.equal(first.slowestSteps[0].durationMs, 55_100);
  assert.equal(first.slowestSteps[1].title, 'expect.toBeVisible');
  assert.equal(first.slowestSteps[1].durationMs, 54_800);
});

test('flattenSteps ignora pasos sin duracion medida', () => {
  const steps = flattenSteps([{ title: 'sin medida', steps: [] }, { title: 'ok', duration: 5, steps: [] }]);
  assert.deepEqual(steps, [{ title: 'ok', durationMs: 5 }]);
});

test('isS5Journey identifica el journey integrado S5-04', () => {
  assert.equal(isS5Journey({ title: 'GP-V288-S5-04: ...' }), true);
  assert.equal(isS5Journey({ title: 'GP-V288-S5-01: ...' }), false);
});

test('formatTimings declara el delta y el caso sin retry', () => {
  const text = formatTimings(summarizeAttempts(reportWithS5()));
  assert.match(text, /delta primero-retry 55\.73s/);
  assert.match(text, /sin retry \(delta hueco\)/);
  assert.match(text, /timedOut/);
});

test('un informe sin suites no inventa tests', () => {
  assert.deepEqual(summarizeAttempts({}), []);
  assert.deepEqual(summarizeAttempts({ suites: [] }), []);
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
  const missing = 'scripts/ci/__no_existe__-report.json';
  let code;
  const lines = captureLog(() => {
    code = main(['node', 'playwright-attempt-timings.mjs', missing]);
  });
  assert.equal(code, 0);
  assert.equal(lines.length, 1);
  assert.match(lines[0], /^# sin informe interpretable/);
  assert.match(lines[0], /__no_existe__-report\.json/);
});

test('main sin argumento es un uso incorrecto (exit 1)', () => {
  let code;
  captureLog(() => {
    code = main(['node', 'playwright-attempt-timings.mjs']);
  });
  assert.equal(code, 1);
});

