#!/usr/bin/env node
/**
 * Reproducción del ARRANQUE EN FRÍO de `S5-04` (evidencia LAB) — READ-ONLY.
 *
 * Encadena la medición local del primer intento del journey integrado `gp-v288-s5`:
 *
 *   1. Exige que NO haya stack previo (si hay algo en :5173/:8000, aborta: no se mide en caliente).
 *   2. Vacía `apps/web/node_modules/.vite` para forzar a Vite a transformar los módulos pesados
 *      del DÍA-D/gráficos DENTRO del tramo (el sospechoso del arranque en frío).
 *   3. Arranca el stack fresco (`pnpm dev`: API + Vite + puente) y espera a que respondan
 *      `/api/health` (:8000) **y** Vite (:5173). Ojo: el `webServer` de Playwright solo espera a
 *      Vite, así que hay que gatear la API aquí o el journey se salta por precondición.
 *   4. Ejecuta `playwright test gp-v288-s5 --retries=1`. Playwright REUSA el stack ya levantado.
 *   5. Renderiza los DOS parsers y muestra las fases del servidor (`[backtest-timing]`, con
 *      `BOLSA_BACKTEST_TIMING=1`). Tumba el stack al terminar.
 *
 * NO cambia `timeout`, `retries` ni aserciones. Repítelo N veces para tener varias muestras del
 * primer intento (cada invocación vuelve a arrancar en frío).
 *
 * Uso:
 *   pnpm ci:s5:cold
 *   node scripts/ci/s5-cold-repro.mjs
 *
 * `S5_COLD_GREP` (opcional) filtra por título, p.ej. `S5_COLD_GREP=S5-04 pnpm ci:s5:cold` mide el
 * journey aislado sobre un Vite recién vaciado (el caso MÁS frío: ningún test previo precalienta
 * módulos). Sigue sin tocar `timeout`/`retries`.
 *
 * Requisitos (declarados, no fingidos): PostgreSQL arriba y migrado, dependencias instaladas
 * (`pnpm install`, `uv sync`) y `.venv` disponible para el seed del ciclo AUTO.
 */
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const webDir = path.join(repoRoot, 'apps', 'web');
const viteCache = path.join(webDir, 'node_modules', '.vite');
const outDir = path.join(tmpdir(), 's5-cold');
const reportPath = path.join(outDir, 's5-integrated-report.json');
const timingsBase = path.join(outDir, 's5-network-timings.json');
const apiHealthUrl = 'http://127.0.0.1:8000/api/health';
const webUrl = 'http://127.0.0.1:5173';
const READY_TIMEOUT_MS = 180_000;

/** `spawnSync` con shell solo en Windows (resuelve `pnpm`/`.cmd`). */
function run(command, args, extra = {}) {
  return spawnSync(command, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
    ...extra,
  });
}

/** `true` si el servicio responde (se usa como sonda de disponibilidad). */
async function isUp(url) {
  try {
    const res = await fetch(url, { redirect: 'manual' });
    return res.status > 0 && res.status < 500;
  } catch {
    return false;
  }
}

/** Espera a que `url` responda; `false` si agota el tiempo. */
async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isUp(url)) return true;
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }
  return false;
}

/** Arranca `pnpm dev` en su propio grupo de procesos (para poder tumbarlo entero). */
function startStack() {
  return spawn('pnpm', ['dev'], {
    cwd: repoRoot,
    stdio: ['ignore', 'inherit', 'inherit'],
    shell: process.platform === 'win32',
    detached: process.platform !== 'win32',
    // La API hereda esta env (la arranca `pnpm dev`): así emite `[backtest-timing]`.
    env: { ...process.env, BOLSA_BACKTEST_TIMING: '1' },
  });
}

/** Tumba el árbol del stack arrancado por este script (nunca un stack ajeno). */
function stopStack(child) {
  if (!child || child.exitCode !== null) return;
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
  } else {
    try {
      process.kill(-child.pid, 'SIGTERM');
    } catch {
      // El grupo ya no existía: nada que tumbar.
    }
  }
}

async function main() {
  // 1) Honestidad del arranque en frío: nada debe estar escuchando ya.
  if ((await isUp(webUrl)) || (await isUp(apiHealthUrl))) {
    console.error(
      '[s5-cold] hay un stack previo en :5173/:8000. Detén tu `pnpm dev` y reintenta: ' +
        'medir sobre un stack caliente no es un arranque en frío.',
    );
    return 1;
  }

  // 2) Arranque en frío de Vite.
  rmSync(viteCache, { recursive: true, force: true });
  mkdirSync(outDir, { recursive: true });
  console.log(`[s5-cold] caché de Vite vaciada: ${path.relative(repoRoot, viteCache)}`);

  // 3) Stack fresco + gate de API y Vite.
  const stack = startStack();
  try {
    const [webReady, apiReady] = await Promise.all([
      waitFor(webUrl, READY_TIMEOUT_MS),
      waitFor(apiHealthUrl, READY_TIMEOUT_MS),
    ]);
    if (!webReady || !apiReady) {
      console.error(
        `[s5-cold] stack no disponible (vite=${webReady}, api=${apiReady}). ` +
          'Revisa que PostgreSQL esté arriba/migrado y el log de `pnpm dev`.',
      );
      return 1;
    }
    console.log('[s5-cold] stack fresco listo (api :8000 + vite :5173)');

    // 4) Journey integrado con el MISMO `retries` que CI.
    const env = {
      ...process.env,
      E2E_RUN: '1',
      E2E_INTEGRATION: '1',
      E2E_ALLOW_DEV_DB: '1',
      PLAYWRIGHT_JSON_OUTPUT_NAME: reportPath,
      S5_TIMINGS_OUT: timingsBase,
      BOLSA_BACKTEST_TIMING: '1',
    };
    const grep = process.env.S5_COLD_GREP;
    const playwrightArgs = [
      'exec',
      'playwright',
      'test',
      'gp-v288-s5',
      '--reporter=list',
      '--reporter=json',
      '--retries=1',
    ];
    if (grep) {
      playwrightArgs.push('--grep', grep);
      console.log(`[s5-cold] filtro de título activo: --grep ${grep}`);
    }
    const playwright = run('pnpm', playwrightArgs, { cwd: webDir, env });

    // 5) Render de los DOS parsers (aunque el journey quede en rojo, hay informe).
    console.log('\n[s5-cold] === tiempos por intento (test.step) ===');
    run('node', [path.join('scripts', 'ci', 'playwright-attempt-timings.mjs'), reportPath]);
    console.log('\n[s5-cold] === red por intento (fases) ===');
    run('node', [path.join('scripts', 'ci', 's5-network-timings.mjs'), timingsBase]);
    console.log(`\n[s5-cold] informes en ${outDir}`);
    return playwright.status ?? 1;
  } finally {
    stopStack(stack);
  }
}

process.exitCode = await main();
