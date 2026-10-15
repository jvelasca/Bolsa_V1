#!/usr/bin/env node
/**
 * Parser READ-ONLY del informe JSON de Playwright: por test, el tiempo de CADA
 * intento (primer intento vs retry) y los pasos mas lentos.
 *
 * Por que existe (S5-04, `v2.88.135-beta`): el primer intento del journey
 * integrado `GP-V288-S5-04` supera los 60 s y el retry pasa. Eso es una
 * incidencia de CI (lentitud del primer arranque), NO un defecto del producto, y
 * se ARREGLA midiendo antes de optimizar. Este modulo SOLO mide:
 *
 *   - NO cambia `timeout`, `retries` ni la asercion del test.
 *   - NO oculta el fallo: el primer intento sigue siendo el que manda.
 *   - NO depende de red ni de PostgreSQL: lee un JSON y resume.
 *
 * Se ejercita con `node --test scripts/ci/playwright-attempt-timings.test.mjs`.
 *
 * Uso:
 *   node scripts/ci/playwright-attempt-timings.mjs /tmp/s5-integrated-report.json
 */

import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

/** Numero finito o `null` (nunca un `0` de relleno: UNKNOWN != 0). */
function numberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Aplana los `specs` anidados en `suites` (recursivo), heredando el fichero. */
export function collectSpecs(report) {
  const out = [];
  const walk = (suite, inheritedFile) => {
    if (!suite || typeof suite !== 'object') return;
    const file = typeof suite.file === 'string' && suite.file ? suite.file : inheritedFile;
    for (const spec of Array.isArray(suite.specs) ? suite.specs : []) {
      out.push({ spec, file, suiteTitle: String(suite.title ?? '') });
    }
    for (const child of Array.isArray(suite.suites) ? suite.suites : []) {
      walk(child, file);
    }
  };
  for (const suite of Array.isArray(report?.suites) ? report.suites : []) {
    walk(suite, '');
  }
  return out;
}

/**
 * Aplana los `steps` (posiblemente anidados) conservando CADA paso con duracion medida.
 * Se incluyen los pasos PADRE (su duracion es el tiempo de pared de la fase, p. ej. un
 * `test.step` nombrado) ademas de sus hijos, para que el paso que consume el tiempo no se
 * pierda al ordenar por duracion.
 */
export function flattenSteps(steps, out = []) {
  for (const step of Array.isArray(steps) ? steps : []) {
    if (!step || typeof step !== 'object') continue;
    const title = String(step.title ?? '');
    const duration = numberOrNull(step.duration);
    if (duration !== null && title !== '') {
      out.push({ title, durationMs: duration });
    }
    flattenSteps(step.steps, out);
  }
  return out;
}

/**
 * Resume por test los intentos observados y sus pasos mas lentos.
 * `attempts` va en ORDEN (indice 0 = primer intento; `retry` es su indice de reintento).
 * `firstMs`/`retryMs`/`deltaMs` son `null` cuando el intento no existe (hueco, no `0`).
 * @param {unknown} report
 * @param {{ slowestSteps?: number }} [options]
 */
export function summarizeAttempts(report, { slowestSteps = 3 } = {}) {
  const summary = [];
  for (const { spec, file, suiteTitle } of collectSpecs(report)) {
    const test = (Array.isArray(spec?.tests) ? spec.tests : [])[0] ?? {};
    const results = Array.isArray(test.results) ? test.results : [];
    const attempts = results.map((result, index) => {
      const steps = flattenSteps(result?.steps)
        .sort((a, b) => b.durationMs - a.durationMs)
        .slice(0, slowestSteps);
      return {
        order: index,
        retry: numberOrNull(result?.retry) ?? index,
        status: String(result?.status ?? 'unknown'),
        durationMs: numberOrNull(result?.duration),
        slowestSteps: steps,
      };
    });
    const first = attempts.find((a) => a.retry === 0) ?? attempts[0] ?? null;
    const retry = attempts.find((a) => a.retry > 0) ?? null;
    const firstMs = first?.durationMs ?? null;
    const retryMs = retry?.durationMs ?? null;
    summary.push({
      title: String(spec?.title ?? ''),
      file,
      suiteTitle,
      projectName: String(test.projectName ?? ''),
      ok: Boolean(spec?.ok),
      attempts,
      retries: attempts.filter((a) => a.retry > 0).length,
      firstMs,
      retryMs,
      // Delta medido solo con AMBOS intentos: cuanto mas lento fue el primer intento que el
      // retry (positivo = el retry fue mas rapido). Sin retry el delta es un hueco (null).
      deltaMs: firstMs !== null && retryMs !== null ? firstMs - retryMs : null,
    });
  }
  return summary;
}

/** ¿El test es el journey integrado `S5-04` (el unico con la lentitud conocida)? */
export function isS5Journey(row) {
  return /S5-04/.test(String(row?.title ?? ''));
}

const fmtMs = (value) => (value === null ? 'hueco' : `${(value / 1000).toFixed(2)}s`);

/** Render legible y estable (para el log del job). */
export function formatTimings(summary) {
  const lines = [
    '# AUTO S5 · tiempos por intento (READ-ONLY; no cambia timeouts ni retries)',
    '',
    '| test | intento | retry | estado | duracion | pasos mas lentos |',
    '| --- | --- | --- | --- | --- | --- |',
  ];
  for (const row of summary) {
    if (row.attempts.length === 0) {
      lines.push(`| ${row.title} | (sin intentos) |  |  |  |  |`);
      continue;
    }
    for (const attempt of row.attempts) {
      const steps = attempt.slowestSteps
        .map((s) => `${s.title} ${fmtMs(s.durationMs)}`)
        .join(' · ');
      lines.push(
        `| ${row.title} | ${attempt.order + 1} | ${attempt.retry} | ${attempt.status} | ` +
          `${fmtMs(attempt.durationMs)} | ${steps} |`,
      );
    }
  }
  lines.push('');
  for (const row of summary) {
    lines.push(
      `- ${row.title}: primer intento ${fmtMs(row.firstMs)}` +
        (row.retryMs === null
          ? ' · sin retry (delta hueco)'
          : ` · retry ${fmtMs(row.retryMs)} · delta primero-retry ${fmtMs(row.deltaMs)}`),
    );
  }
  return lines.join('\n');
}

export function main(argv) {
  const path = argv[2];
  if (!path) {
    console.error('# uso: node scripts/ci/playwright-attempt-timings.mjs <informe.json>');
    return 1;
  }
  let report;
  try {
    report = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    // Un informe ausente/ilegible es un HUECO declarado, no un rojo: la medicion es
    // instrumentacion, el gate del journey vive en el propio job de Playwright.
    console.log(`# sin informe interpretable (${path}): ${error instanceof Error ? error.message : error}`);
    return 0;
  }
  const summary = summarizeAttempts(report);
  if (summary.length === 0) {
    console.log(`# informe sin tests (${path})`);
    return 0;
  }
  console.log(formatTimings(summary));
  const slow = summary.filter((row) => isS5Journey(row) && row.firstMs !== null && row.retryMs !== null);
  for (const row of slow) {
    console.log(
      `# S5-04 delta primero-retry ${fmtMs(row.deltaMs)} (primero ${fmtMs(row.firstMs)} · retry ${fmtMs(row.retryMs)})`,
    );
  }
  return 0;
}

// Solo ejecuta el CLI cuando se invoca como programa (no al importarlo en tests).
const invokedPath = process.argv[1];
if (invokedPath && import.meta.url === pathToFileURL(invokedPath).href) {
  process.exitCode = main(process.argv);
}
