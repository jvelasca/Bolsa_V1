#!/usr/bin/env node
/**
 * Pin de la ventana PAPER — comprobacion y RE-ANCLAJE del arbol congelado.
 *
 * La ventana forward mide el material de un UNICO arbol de codigo: `run-day`
 * compara `git rev-parse "HEAD:apps" "HEAD:packages"` con los hashes pinneados
 * en `WINDOW_CONFIG` (`scripts/lib/window-forward.mjs`) y, si no coinciden,
 * aborta fail-closed con `TREE_MOVED` (ver runbook §G.1).
 *
 * Este helper NO existe en el flujo del runner: es una herramienta de OPERACION
 * para (a) comprobar el freeze antes de medir y (b) re-anclar el pin cuando el
 * arbol ha avanzado por un commit legitimo (p. ej. el re-anclaje POST-TAG).
 *
 * Uso (desde la raiz del repo):
 *   node scripts/window-pin.mjs --check
 *   node scripts/window-pin.mjs --write [--note "motivo"]
 *   node scripts/window-pin.mjs --write --dry-run
 *
 * `--check` sale 0 si `freeze OK` y 1 si `TREE_MOVED` (imprime los hashes a fijar).
 * `--write` actualiza SOLO `commit`/`appsHash`/`packagesHash` y anade un bloque de
 * comentario `RE-ANCLAJE` con la fecha y el motivo. NO toca la identidad
 * (cuenta/versiones/watchSize), que es la del protocolo.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const _HERE = dirname(fileURLToPath(import.meta.url));
export const PIN_FILE = join(_HERE, 'lib', 'window-forward.mjs');

const PIN_ANCHOR = 'export const WINDOW_CONFIG = Object.freeze({';

/**
 * Extrae los tres campos del pin de la config (puro, testeable sin git).
 * @param {string} text contenido de `window-forward.mjs`
 * @returns {{commit: string|null, appsHash: string|null, packagesHash: string|null}}
 */
export function parsePinFields(text) {
  const pick = (field) => {
    const match = text.match(new RegExp(`${field}:\\s*'([^']+)'`));
    return match ? match[1] : null;
  };
  return {
    commit: pick('commit'),
    appsHash: pick('appsHash'),
    packagesHash: pick('packagesHash'),
  };
}

/**
 * Compara el pin declarado con los hashes reales del arbol (puro).
 *
 * El freeze REAL son los dos tree hashes; `commit` es solo la ETIQUETA del commit
 * (el arbol del sello), por lo que un `commit` distinto no rompe el freeze. Se
 * devuelve aparte como informativo.
 * @param {{commit: string|null, appsHash: string|null, packagesHash: string|null}} pin
 * @param {{commit: string, appsHash: string, packagesHash: string}} actual
 */
export function freezeStatus(pin, actual) {
  const mismatches = [];
  if (pin.appsHash !== actual.appsHash) mismatches.push('appsHash');
  if (pin.packagesHash !== actual.packagesHash) mismatches.push('packagesHash');
  return {
    ok: mismatches.length === 0,
    mismatches,
    commitLabelStale: Boolean(pin.commit && actual.commit && pin.commit !== actual.commit),
  };
}

/**
 * Aplica el pin nuevo sobre el texto de la config (puro): reescribe los tres
 * campos y antepone un bloque `RE-ANCLAJE`. Idempotente: si los valores ya
 * coinciden, devuelve el texto sin cambios.
 */
export function applyPin(text, { commit, appsHash, packagesHash, note, day }) {
  const current = parsePinFields(text);
  if (
    current.commit === commit &&
    current.appsHash === appsHash &&
    current.packagesHash === packagesHash
  ) {
    return { text, changed: false };
  }
  let next = text
    .replace(/(commit:\s*')[^']+(')/, `$1${commit}$2`)
    .replace(/(appsHash:\s*')[^']+(')/, `$1${appsHash}$2`)
    .replace(/(packagesHash:\s*')[^']+(')/, `$1${packagesHash}$2`);
  const block = [
    '/**',
    ` * RE-ANCLAJE ${day} — pin del arbol re-anclado a \`${commit}\``,
    ` * (\`apps\` \`${appsHash}\` / \`packages\` \`${packagesHash}\`).`,
    note ? ` * Motivo: ${note}` : ' * Motivo: (no declarado).',
    ' * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,',
    ' * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse',
    ' * DESPUES de este re-anclaje (o quedarian `STALE`).',
    ' */',
    '',
  ].join('\n');
  next = next.replace(PIN_ANCHOR, `${block}${PIN_ANCHOR}`);
  return { text: next, changed: true };
}

function git(args) {
  const res = spawnSync('git', args, { encoding: 'utf8' });
  if (res.status !== 0) {
    const detail = (res.stderr || res.stdout || '').trim();
    throw new Error(`git ${args.join(' ')} fallo (${res.status}): ${detail}`);
  }
  return res.stdout.trim();
}

function readActual() {
  const lines = git(['rev-parse', 'HEAD:apps', 'HEAD:packages']).split(/\r?\n/);
  const commit = git(['rev-parse', '--short=8', 'HEAD']);
  return { appsHash: lines[0], packagesHash: lines[1], commit };
}

function parseArgs(argv) {
  const flags = { write: false, check: false, dryRun: false, note: null, day: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--write') flags.write = true;
    else if (arg === '--check') flags.check = true;
    else if (arg === '--dry-run') flags.dryRun = true;
    else if (arg === '--note') {
      flags.note = argv[i + 1] ?? null;
      i += 1;
    } else if (arg.startsWith('--note=')) flags.note = arg.slice('--note='.length);
    else if (arg === '--day') {
      flags.day = argv[i + 1] ?? null;
      i += 1;
    } else if (arg.startsWith('--day=')) flags.day = arg.slice('--day='.length);
  }
  return flags;
}

function today() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function main() {
  const flags = parseArgs(process.argv.slice(2));
  const text = readFileSync(PIN_FILE, 'utf8');
  const pin = parsePinFields(text);
  const actual = readActual();
  const status = freezeStatus(pin, actual);

  if (flags.write) {
    const day = flags.day || today();
    const { text: next, changed } = applyPin(text, {
      commit: actual.commit,
      appsHash: actual.appsHash,
      packagesHash: actual.packagesHash,
      note: flags.note,
      day,
    });
    if (!changed) {
      console.log(`[window-pin] freeze OK ya vigente (${actual.commit}) — nada que re-anclar`);
      return 0;
    }
    if (flags.dryRun) {
      console.log(`[window-pin] --dry-run: re-anclaria a ${actual.commit}`);
      console.log(`  appsHash     ${actual.appsHash}`);
      console.log(`  packagesHash ${actual.packagesHash}`);
      return 0;
    }
    writeFileSync(PIN_FILE, next, 'utf8');
    console.log(`[window-pin] pin re-anclado a ${actual.commit}`);
    console.log(`  appsHash     ${actual.appsHash}`);
    console.log(`  packagesHash ${actual.packagesHash}`);
    return 0;
  }

  // `--check` (o por defecto).
  if (status.ok) {
    console.log(`[window-pin] freeze OK (${actual.commit})`);
    console.log(`  appsHash     ${pin.appsHash}`);
    console.log(`  packagesHash ${pin.packagesHash}`);
    if (status.commitLabelStale) {
      console.log(
        `  nota: la etiqueta 'commit' del pin (${pin.commit}) != HEAD (${actual.commit}); ` +
          'el freeze real son los dos tree hashes (puede re-anclarse con --write)',
      );
    }
    return 0;
  }
  console.log(`[window-pin] TREE_MOVED — el pin NO coincide con el arbol de HEAD`);
  console.log(`  campo         pin                                  HEAD`);
  console.log(`  commit        ${String(pin.commit).padEnd(35)}  ${actual.commit}`);
  console.log(`  appsHash      ${String(pin.appsHash).padEnd(35)}  ${actual.appsHash}`);
  console.log(`  packagesHash  ${String(pin.packagesHash).padEnd(35)}  ${actual.packagesHash}`);
  console.log('  re-ancla con: node scripts/window-pin.mjs --write --note "<motivo>"');
  return 1;
}

if (process.argv[1] && process.argv[1].endsWith('window-pin.mjs')) {
  process.exit(main());
}
