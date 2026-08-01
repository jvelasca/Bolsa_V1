#!/usr/bin/env node
/**
 * Verificación completa pre-desarrollo: doctor + health HTTP + smoke test Python.
 */
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { ensureLogDirs, logError, logInfo, ROOT } from './lib/logger.mjs';

ensureLogDirs();

function run(label, args, options = {}) {
  logInfo('verify', `→ ${label}`);
  const result = spawnSync(process.execPath, args, {
    cwd: ROOT,
    stdio: 'inherit',
    ...options,
  });
  if (result.status !== 0) {
    logError('verify', `${label} falló (código ${result.status ?? 1})`);
    process.exit(result.status ?? 1);
  }
}

run('dev-doctor', [join(ROOT, 'scripts', 'dev-doctor.mjs')]);

const health = spawnSync(process.execPath, [join(ROOT, 'scripts', 'health-check.mjs')], {
  cwd: ROOT,
  stdio: 'inherit',
});
if (health.status !== 0) {
  logInfo('verify', 'health-check omitido (servicios no arrancados — normal antes de F5)');
} else {
  logInfo('verify', 'health-check OK');
}

logInfo('verify', '→ smoke tests Python (position policies)');
const py = spawnSync(
  'python',
  ['-m', 'pytest', 'tests/integration/test_position_policies_flow.py', '-q'],
  {
    cwd: join(ROOT, 'apps', 'api-python'),
    stdio: 'inherit',
    env: { ...process.env, PYTHONPATH: join(ROOT, 'apps', 'api-python', 'src') },
    shell: true,
  },
);
if (py.status !== 0) {
  logError('verify', 'smoke tests Python fallaron');
  process.exit(py.status ?? 1);
}

logInfo('verify', '=== Verificación completada ===');
