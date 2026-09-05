#!/usr/bin/env node
/**
 * V2.10 — Wrapper: carga `.env` (scripts/lib/load-env.mjs) y ejecuta
 * scripts/ops_seed_cabin_smoke.py con el mismo entorno que el API.
 *
 * Uso (repo root):
 *   node scripts/ops_seed_cabin_smoke.mjs birth-structural
 *   node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply --account-id <id>
 *   node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --apply --account-id <id>
 */
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadEnvFile } from './lib/load-env.mjs';
import { ROOT } from './lib/logger.mjs';

loadEnvFile();

const script = join(ROOT, 'scripts', 'ops_seed_cabin_smoke.py');
const args = process.argv.slice(2);
const py = process.env.PYTHON || 'python';
const result = spawnSync(py, [script, ...args], {
  stdio: 'inherit',
  env: process.env,
  cwd: ROOT,
});
process.exit(result.status === null ? 1 : result.status);
