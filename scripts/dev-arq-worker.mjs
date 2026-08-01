#!/usr/bin/env node
/**
 * Worker Arq para scan jobs (RD-2 full).
 * Requiere Redis + SCAN_QUEUE_BACKEND=arq en la API.
 */
import { spawn } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolvePython } from './lib/python.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const apiDir = join(root, 'apps', 'api-python');
const python = resolvePython();

console.log('[dev-arq-worker] Iniciando worker Arq scan jobs…');

const child = spawn(
  python,
  ['-m', 'bolsa_api.workers.arq_worker'],
  {
    cwd: apiDir,
    stdio: 'inherit',
    shell: false,
    env: {
      ...process.env,
      PYTHONPATH: join(apiDir, 'src'),
    },
  },
);

child.on('exit', (code) => process.exit(code ?? 0));
