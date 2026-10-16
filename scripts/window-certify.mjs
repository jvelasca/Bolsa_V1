/**
 * `window:certify` — certificador de la ventana PAPER (ADR-046) con la IDENTIDAD del pin.
 *
 * Por qué existe
 * --------------
 * El certificador `v2_98_paper_window_certification.py` exige `--account-id` y una
 * `--strategy-version` por cada estrategia del par A/B. La identidad de la ventana
 * (cuenta + versiones) vive en `WINDOW_CONFIG` (`scripts/lib/window-forward.mjs`), así
 * que este wrapper la LEE de ahí en vez de repetirla a mano: una sola orden
 * reproducible y sin riesgo de certificar una cuenta/versión equivocada.
 *
 * Qué NO hace
 * -----------
 * Es **read-only** y **NO sustituye la ventana real**: sólo LEE el material durable que
 * ya existe y declara el hueco honestamente (`INCONCLUSIVE`). No abre el motor, no
 * escribe en PostgreSQL ni en el journal, no cambia umbrales ni el gobernador.
 *
 * Freeze-neutral: este fichero vive en `scripts/`, que NO participa del freeze
 * (`HEAD:apps`/`HEAD:packages`). Añadirlo no mueve el árbol del pin.
 *
 * Códigos de salida (los mismos de `v2_98`): `0` aunque el veredicto sea
 * `INCONCLUSIVE` (declarar el hueco no es un fallo); `2` si el material no se pudo
 * leer; `1` si el lanzamiento es incorrecto.
 *
 * Uso:
 *   pnpm run window:certify
 *   node scripts/window-certify.mjs --out operability_runs/paper-window-certification/cert.json
 *   node scripts/window-certify.mjs -- --days 30      # args extra para v2_98 tras `--`
 */
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { ROOT, logError, logInfo } from './lib/logger.mjs';
import { WINDOW_CONFIG } from './lib/window-forward.mjs';

const SCOPE = 'window';
const SCRIPT_CERTIFY = 'apps/api-python/scripts/v2_98_paper_window_certification.py';
const DEFAULT_OUT = 'operability_runs/paper-window-certification/window-certificate.json';

/**
 * Resuelve cómo lanzar Python con la MISMA precedencia que el runner forward:
 *   1. `WINDOW_PY` (override explícito del intérprete).
 *   2. `uv run --no-sync python` (convención del repo), si `uv` puede lanzarlo.
 *   3. `python` directo (algunos entornos bloquean el spawn interno de `uv`).
 */
function runProcess(bin, args, options = {}) {
  const { cwd = ROOT, env = process.env } = options;
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(bin, args, { cwd, env, shell: false, windowsHide: true });
    } catch (error) {
      resolve({ code: null, out: '', err: '', spawnError: error });
      return;
    }
    let out = '';
    let err = '';
    child.stdout.on('data', (chunk) => {
      out += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      err += chunk.toString();
    });
    child.on('error', (error) => resolve({ code: null, out, err, spawnError: error }));
    child.on('close', (code) => resolve({ code, out, err }));
  });
}

/** Separa los args propios de los que se reenvían a `v2_98` tras `--`. */
function splitArgs(argv) {
  const passthrough = [];
  const own = [];
  let seenSeparator = false;
  for (const arg of argv) {
    if (!seenSeparator && arg === '--') {
      seenSeparator = true;
      continue;
    }
    (seenSeparator ? passthrough : own).push(arg);
  }
  return { own, passthrough };
}

function parseOwn(argv) {
  const parsed = { out: DEFAULT_OUT, json: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--out') {
      parsed.out = argv[i + 1];
      i += 1;
    } else if (arg.startsWith('--out=')) {
      parsed.out = arg.slice('--out='.length);
    } else if (arg === '--json') {
      parsed.json = true;
    } else {
      throw new Error(`argumento no reconocido: ${arg}`);
    }
  }
  return parsed;
}

async function resolveLauncher() {
  if (process.env.WINDOW_PY) {
    return { bin: process.env.WINDOW_PY, prefix: [], label: process.env.WINDOW_PY };
  }
  const uv = process.env.WINDOW_UV || 'uv';
  const probe = await runProcess(uv, ['run', '--no-sync', 'python', '-c', 'print(0)']);
  if (probe.code === 0) {
    return { bin: uv, prefix: ['run', '--no-sync', 'python'], label: `${uv} run --no-sync python` };
  }
  const detail = (probe.err || '').trim().split(/\r?\n/).pop() || 'fallo';
  logError(SCOPE, `uv no puede lanzar python (${detail}); se usa 'python' directo (override con WINDOW_PY)`);
  return { bin: 'python', prefix: [], label: 'python' };
}

async function main() {
  const { own, passthrough } = splitArgs(process.argv.slice(2));
  let options;
  try {
    options = parseOwn(own);
  } catch (error) {
    logError(SCOPE, String(error.message));
    process.exitCode = 1;
    return;
  }

  const launcher = await resolveLauncher();
  const args = [
    ...launcher.prefix,
    join(ROOT, SCRIPT_CERTIFY),
    '--account-id',
    WINDOW_CONFIG.account,
    '--strategy-version',
    WINDOW_CONFIG.versionA,
    '--strategy-version',
    WINDOW_CONFIG.versionB,
    '--out',
    options.out,
    ...(options.json ? ['--json'] : []),
    ...passthrough,
  ];

  logInfo(
    SCOPE,
    `certificacion de la ventana PAPER (ADR-046) · cuenta ${WINDOW_CONFIG.account} · ` +
      `${WINDOW_CONFIG.versionA}/${WINDOW_CONFIG.versionB} · launcher ${launcher.label}`,
  );

  const result = await runProcess(launcher.bin, args);
  if (result.spawnError) {
    logError(SCOPE, `no se pudo lanzar ${launcher.label}: ${result.spawnError.message}`);
    process.exitCode = 1;
    return;
  }
  if (result.out) process.stdout.write(result.out);
  if (result.err) process.stderr.write(result.err);
  process.exitCode = typeof result.code === 'number' ? result.code : 1;
}

main();
