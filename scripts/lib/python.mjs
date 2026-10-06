import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
/** Raíz del repositorio (…/Bolsa_V1). */
export const REPO_ROOT = join(HERE, '..', '..');

/**
 * Interpreta patrones de `python --version`:
 *  - status 0 → ejecutable lanzable.
 *  - `error.code === 'UNKNOWN'` (errno -4094) en Windows → Smart App Control
 *    (o AppLocker) bloqueó la carga del binario; típico con el trampolín que
 *    `uv` genera en `.venv\Scripts\python.exe`.
 */
export function probePython(exe) {
  const check = spawnSync(exe, ['--version'], { encoding: 'utf8', shell: false });
  if (check.error) {
    return { ok: false, code: check.error.code || check.error.message, detail: null };
  }
  const detail = (check.stdout || check.stderr || '').trim();
  return { ok: check.status === 0, code: check.status === 0 ? null : `exit ${check.status}`, detail };
}

/**
 * Extrae el intérprete base (`home = …`) de un `pyvenv.cfg`.
 * Función pura para poder testear sin tocar el disco.
 */
export function readPyvenvHome(cfgText) {
  if (typeof cfgText !== 'string') return null;
  const match = cfgText.match(/^\s*home\s*=\s*(.+?)\s*$/m);
  return match ? match[1].trim() : null;
}

function venvScriptsDir() {
  return process.platform === 'win32' ? 'Scripts' : 'bin';
}

function venvPythonName() {
  return process.platform === 'win32' ? 'python.exe' : 'python';
}

/**
 * Ruta del intérprete de la venv del proyecto (o de `VIRTUAL_ENV` si está
 * activada). No garantiza que exista ni que sea ejecutable.
 */
export function projectVenvPython() {
  const exe = join(venvScriptsDir(), venvPythonName());
  if (process.env.VIRTUAL_ENV) {
    const fromEnv = join(process.env.VIRTUAL_ENV, exe);
    if (existsSync(fromEnv)) return fromEnv;
  }
  return join(REPO_ROOT, '.venv', exe);
}

function venvCandidates() {
  const exe = join(venvScriptsDir(), venvPythonName());
  const list = [];
  if (process.env.VIRTUAL_ENV) list.push(join(process.env.VIRTUAL_ENV, exe));
  list.push(join(REPO_ROOT, '.venv', exe));
  list.push(join(REPO_ROOT, 'apps', 'api-python', '.venv', exe));
  return list;
}

function resolveBasePython(venvPython) {
  const cfgPath = join(dirname(dirname(venvPython)), 'pyvenv.cfg');
  if (existsSync(cfgPath)) {
    const home = readPyvenvHome(readFileSync(cfgPath, 'utf8'));
    if (home) {
      const candidate = join(home, venvPythonName());
      if (existsSync(candidate)) return candidate;
    }
  }
  for (const candidate of ['python', 'python3', 'py']) {
    if (probePython(candidate).ok) return candidate;
  }
  return null;
}

/**
 * Sustituye el intérprete de la venv (bloqueado) por una **copia real** del
 * intérprete base, creada con `python -m venv --copies`.
 *
 * ¿Por qué funciona? Smart App Control bloquea el *trampolín* sin firmar que
 * `uv` genera en `.venv\Scripts\python.exe`, pero permite el binario firmado
 * del intérprete base. Una copia real hereda esa firma. `pyvenv.cfg` y
 * `site-packages` no se tocan, así que el entorno de la venv se conserva.
 */
export function repairVenvPython(venvPython, { log = () => {} } = {}) {
  if (process.platform !== 'win32') return false;
  const basePython = resolveBasePython(venvPython);
  if (!basePython) {
    log(`No se pudo localizar el intérprete base para reparar ${venvPython}`);
    return false;
  }

  const venvDir = dirname(dirname(venvPython));
  const tmp = mkdtempSync(join(tmpdir(), 'bolsa-venv-fix-'));
  try {
    log(`Generando imagen real del intérprete (${basePython})…`);
    const created = spawnSync(basePython, ['-m', 'venv', '--copies', tmp], {
      encoding: 'utf8',
      shell: false,
    });
    if (created.error || created.status !== 0) {
      log(`No se pudo crear la venv temporal (${created.error?.code ?? created.status})`);
      return false;
    }

    let replaced = false;
    for (const name of ['python.exe', 'pythonw.exe']) {
      const src = join(tmp, 'Scripts', name);
      const dst = join(venvDir, 'Scripts', name);
      if (!existsSync(src) || !existsSync(dst)) continue;
      // Backup inicial del trampolín bloqueado, por si hace falta revertir.
      const backup = `${dst}.sacbak`;
      if (!existsSync(backup)) copyFileSync(dst, backup);
      copyFileSync(src, dst);
      replaced = true;
    }
    if (!replaced) {
      log('La imagen temporal no contenía intérpretes; nada que sustituir');
      return false;
    }
    return probePython(venvPython).ok;
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

/**
 * Devuelve el intérprete de la venv si es lanzable, reparándolo antes si Smart
 * App Control lo bloqueó. `null` si no hay venv o no se pudo dejar operativa.
 */
export function ensureVenvPython({ log = () => {} } = {}) {
  for (const candidate of venvCandidates()) {
    if (!existsSync(candidate)) continue;
    const probe = probePython(candidate);
    if (probe.ok) return candidate;
    if (process.platform === 'win32' && probe.code === 'UNKNOWN') {
      log(`Intérprete de la venv bloqueado por App Control (${candidate}); reparando…`);
      if (repairVenvPython(candidate, { log }) && probePython(candidate).ok) {
        log(`Venv reparada con una copia real del intérprete base: ${candidate}`);
        return candidate;
      }
      log('No se pudo reparar la venv automáticamente');
    }
  }
  return null;
}

/**
 * Ejecutable Python para arrancar uvicorn (o cualquier tooling Python local).
 * Prioridad: `PYTHON` → venv del proyecto (reparada si hace falta) → PATH.
 * Override con PYTHON=/ruta/python en .env si hace falta.
 */
export function resolvePython({ log = () => {} } = {}) {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }

  const venv = ensureVenvPython({ log });
  if (venv) return venv;

  for (const candidate of ['python', 'python3', 'py']) {
    if (probePython(candidate).ok) {
      return candidate;
    }
  }

  return 'python';
}
