#!/usr/bin/env node
/**
 * Repara el intérprete de la venv cuando Windows Smart App Control /
 * AppLocker bloquea el trampolín que `uv` genera en `.venv\Scripts\python.exe`
 * (síntoma: `spawn UNKNOWN` al arrancar la API Python).
 *
 * Uso:
 *   node scripts/fix-venv-python.mjs          # repara si está bloqueado
 *   node scripts/fix-venv-python.mjs --check   # solo diagnostica (exit 1 si bloqueado)
 */
import { existsSync } from 'node:fs';
import { ensureLogDirs, logError, logInfo, logWarn } from './lib/logger.mjs';
import { probePython, projectVenvPython, repairVenvPython } from './lib/python.mjs';

ensureLogDirs();

const checkOnly = process.argv.includes('--check');
const venvPython = projectVenvPython();

logInfo('venv', `Intérprete de la venv: ${venvPython}`);

if (!existsSync(venvPython)) {
  logWarn('venv', 'No existe la venv del proyecto (.venv). Nada que reparar.');
  process.exit(0);
}

const before = probePython(venvPython);
if (before.ok) {
  logInfo('venv', `OK — ${before.detail} (nada que hacer)`);
  process.exit(0);
}

logWarn('venv', `No ejecutable / bloqueado (${before.code}). Suele ser Smart App Control.`);
if (checkOnly) {
  process.exit(1);
}

const ok = repairVenvPython(venvPython, { log: (msg) => logInfo('venv', msg) });
const after = probePython(venvPython);

if (ok && after.ok) {
  logInfo('venv', `Reparado — ${after.detail}`);
  process.exit(0);
}

logError('venv', 'No se pudo reparar automáticamente.');
logError(
  'venv',
  'Alternativas: (1) desactiva Smart App Control (Configuración → Seguridad de Windows → Control de aplicaciones y navegador); (2) recrea la venv con `python -m venv --copies .venv`.',
);
process.exit(1);
