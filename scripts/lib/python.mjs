import { spawnSync } from 'node:child_process';

/**
 * Ejecutable Python para arrancar uvicorn.
 * Override con PYTHON=/ruta/python en .env si hace falta.
 */
export function resolvePython() {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }

  for (const candidate of ['python', 'python3', 'py']) {
    const check = spawnSync(candidate, ['--version'], { encoding: 'utf8', shell: false });
    if (check.status === 0) {
      return candidate;
    }
  }

  return 'python';
}
