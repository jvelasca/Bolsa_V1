#!/usr/bin/env node
/**
 * Worker de poll scan/optimize para backends no-ARQ (R12-SCHED / R-8C.2).
 * Con SCAN_QUEUE_BACKEND=arq este proceso hace no-op; usa `pnpm dev:arq-worker`.
 */
import { spawn } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolvePython } from './lib/python.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const apiDir = join(root, 'apps', 'api-python');
const python = resolvePython();

console.log('[dev-queue-poll-worker] Iniciando queue poll (scan + optimize)…');

const child = spawn(
  python,
  ['-m', 'bolsa_api.workers.queue_poll_worker'],
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
