#!/usr/bin/env node
/**
 * Supervisor barato del stack de desarrollo para la ventana PAPER (2026-11-09).
 *
 * **Por que existe.** La causa operativa de los `fetch failed` de `BarsSync` es que
 * el API no estuviera arriba a la hora de la tarea (2026-11-08: el log de desarrollo
 * se corta a las 17:24 y el siguiente arranque es a las 18:22). La tarea programada
 * exige `/api/health/ready`; este script lo comprueba y, si no esta listo, **arranca
 * `pnpm dev` en segundo plano** y espera hasta `--wait-seconds`.
 *
 * **Que NO hace.** No mata procesos. Si el **puerto del API** (8000) esta ocupado por
 * algo que no responde `ready`, se declara y se sale `1`: matar el stack de otro no es
 * tarea del supervisor. Si solo estan ocupados la web (5173) o el puente XTB (3002),
 * **avisa y arranca igual**, porque `pnpm dev` libera esos tres puertos antes de
 * bindearlos (`ensureStackPortsFree`); bloquear ahi impedia recuperar el caso medido
 * del 2026-11-09 (API caido con el puente XTB huerfano vivo). No escribe en PostgreSQL
 * ni toca el arbol congelado.
 *
 * Uso (raiz del repo):
 *   node scripts/window-stack-ready.mjs                    # comprueba y arranca si hace falta
 *   node scripts/window-stack-ready.mjs --no-start          # solo comprueba
 *   node scripts/window-stack-ready.mjs --wait-seconds 300
 *   node scripts/window-stack-ready.mjs --dry-run
 *
 * Codigos de salida: 0 stack listo · 1 no listo tras la espera · 2 uso incorrecto.
 */
import { closeSync, mkdirSync, openSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join } from 'node:path';

import { ROOT, logError, logInfo, logWarn, writeAgentLog } from './lib/logger.mjs';
import { getListenerPids } from './lib/ports.mjs';
import { decidePortConflict, describePortConflict, stackPorts } from './lib/stack-ports.mjs';

const SCOPE = 'stack-ready';
const DEFAULT_WAIT_SECONDS = 300;
const DEFAULT_INTERVAL_SECONDS = 5;
const READY_TIMEOUT_MS = 5_000;

function parseArgs(argv) {
  const flags = {
    waitSeconds: DEFAULT_WAIT_SECONDS,
    intervalSeconds: DEFAULT_INTERVAL_SECONDS,
    start: true,
    dryRun: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const [name, inline] = arg.includes('=')
      ? [arg.slice(0, arg.indexOf('=')), arg.slice(arg.indexOf('=') + 1)]
      : [arg, null];
    const value = (flagName) => {
      if (inline !== null) return inline;
      const next = argv[i + 1];
      if (next === undefined) throw new Error(`falta el valor de ${flagName}`);
      i += 1;
      return next;
    };
    if (name === '--wait-seconds') flags.waitSeconds = Number(value(name));
    else if (name === '--interval-seconds') flags.intervalSeconds = Number(value(name));
    else if (name === '--no-start') flags.start = false;
    else if (name === '--dry-run') flags.dryRun = true;
    else throw new Error(`argumento no reconocido: ${arg}`);
  }
  return flags;
}

function readyUrl() {
  const port = process.env.API_PYTHON_PORT || process.env.API_PORT || '8000';
  return process.env.WINDOW_API_READY_URL || `http://127.0.0.1:${port}/api/health/ready`;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Una sonda: `{ok, status}`; un error de red cuenta como no listo, nunca como listo. */
async function probe(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), READY_TIMEOUT_MS);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return { ok: response.ok, status: response.status, error: null };
  } catch (error) {
    return {
      ok: false,
      status: null,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timer);
  }
}

function spawnDev(logPath) {
  mkdirSync(join(ROOT, 'logs', 'agent'), { recursive: true });
  const fd = openSync(logPath, 'a');
  const child = spawn('pnpm', ['dev'], {
    cwd: ROOT,
    shell: true,
    detached: true,
    stdio: ['ignore', fd, fd],
    windowsHide: true,
    env: process.env,
  });
  child.unref();
  closeSync(fd);
  return child.pid ?? null;
}

async function main() {
  let flags;
  try {
    flags = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.log(`[${SCOPE}] ${error.message}`);
    console.log(
      '  uso: node scripts/window-stack-ready.mjs [--no-start] [--wait-seconds 300] [--interval-seconds 5] [--dry-run]',
    );
    return 2;
  }
  if (!Number.isFinite(flags.waitSeconds) || flags.waitSeconds < 0) {
    console.log(`[${SCOPE}] --wait-seconds debe ser un numero >= 0`);
    return 2;
  }
  if (!Number.isFinite(flags.intervalSeconds) || flags.intervalSeconds <= 0) {
    console.log(`[${SCOPE}] --interval-seconds debe ser un numero > 0`);
    return 2;
  }

  const url = readyUrl();
  const first = await probe(url);
  if (first.ok) {
    logInfo(SCOPE, `stack listo (${url}, HTTP ${first.status}); no se arranca nada`);
    writeAgentLog('stack-ready', { status: 'ready', url, started: false });
    return 0;
  }
  logWarn(
    SCOPE,
    `stack NO listo (${url}): ${first.error ?? `HTTP ${first.status}`}` +
      (flags.start ? '' : ' · --no-start: no se arranca'),
  );

  if (flags.dryRun) {
    console.log(`[${SCOPE}] --dry-run · arrancaria: pnpm dev (cwd ${ROOT}) y esperaria ${flags.waitSeconds} s`);
    return first.ok ? 0 : 1;
  }
  if (!flags.start) {
    writeAgentLog('stack-ready', { status: 'not-ready', url, started: false });
    return 1;
  }

  // Puertos REALES del stack: API 8000, web 5173 (no 3002, que es el puente XTB) y
  // puente 3002. Solo el API bloquea (ver `scripts/lib/stack-ports.mjs`): web y puente
  // los libera `run-dev.mjs` en `ensureStackPortsFree()`, y bloquear ahí impediría
  // recuperar el caso medido (API caído con el puente XTB huérfano vivo).
  const ports = stackPorts();
  const decision = decidePortConflict({
    api: getListenerPids(ports.api),
    web: getListenerPids(ports.web),
    bridge: getListenerPids(ports.bridge),
  });
  if (decision.block) {
    logError(
      SCOPE,
      `puerto del API ocupado — ${describePortConflict(ports, decision)} — pero ${url} no responde: ` +
        'NO se arranca un segundo stack; revisar el proceso vivo',
    );
    writeAgentLog('stack-ready', {
      status: 'port-busy',
      url,
      pids: decision.api,
      ports,
      started: false,
    });
    return 1;
  }
  if (decision.stale.length > 0) {
    logWarn(
      SCOPE,
      `puertos web/puente ocupados — ${describePortConflict(ports, decision)} —: se arranca igual ` +
        '(`pnpm dev` libera 5173/3002 antes de bindear)',
    );
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logPath = join(ROOT, 'logs', 'agent', `stack-ready-${stamp}.log`);
  const pid = spawnDev(logPath);
  logInfo(SCOPE, `arrancando \`pnpm dev\` en segundo plano (PID ${pid ?? 'n/d'}, log ${logPath})`);

  const deadline = Date.now() + flags.waitSeconds * 1000;
  for (;;) {
    await sleep(flags.intervalSeconds * 1000);
    const result = await probe(url);
    if (result.ok) {
      logInfo(SCOPE, `stack listo tras el arranque (${url}, HTTP ${result.status})`);
      writeAgentLog('stack-ready', { status: 'ready', url, started: true, pid, logPath });
      return 0;
    }
    if (Date.now() >= deadline) {
      logError(
        SCOPE,
        `stack sigue sin responder ${url} tras ${flags.waitSeconds} s` +
          ` (${result.error ?? `HTTP ${result.status}`}); ver ${logPath}`,
      );
      writeAgentLog('stack-ready', {
        status: 'timeout',
        url,
        started: true,
        pid,
        logPath,
      });
      return 1;
    }
  }
}

main().then((code) => process.exit(code));
