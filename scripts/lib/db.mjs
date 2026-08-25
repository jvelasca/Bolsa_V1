import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { runPnpm } from './pnpm.mjs';
import { ROOT } from './logger.mjs';
import { loadEnvFile } from './load-env.mjs';
import { resolvePython } from './python.mjs';

function runDbScript(args, label) {
  const result = runPnpm(args, { cwd: ROOT });
  if (result.status !== 0) {
    throw new Error(`${label} falló (código ${result.status ?? 1})`);
  }
}

export function runDbGenerate() {
  runDbScript(['--filter', '@bolsa/database', 'db:generate'], 'Prisma generate');
}

/**
 * Same mechanism as FastAPI lifespan: Alembic upgrade head via
 * `bolsa_infrastructure.database.migrations.ensure_migrated`.
 */
export function runAlembicUpgrade() {
  loadEnvFile();
  const py = resolvePython();
  const infraSrc = join(ROOT, 'packages', 'py', 'infrastructure', 'src');
  const sep = process.platform === 'win32' ? ';' : ':';
  const pythonPath = [infraSrc, process.env.PYTHONPATH].filter(Boolean).join(sep);
  const result = spawnSync(
    py,
    [
      '-c',
      'from bolsa_infrastructure.database.migrations import ensure_migrated; ensure_migrated()',
    ],
    {
      cwd: ROOT,
      stdio: 'inherit',
      encoding: 'utf8',
      windowsHide: true,
      env: { ...process.env, PYTHONPATH: pythonPath },
    },
  );
  if (result.status !== 0) {
    throw new Error(`Alembic upgrade falló (código ${result.status ?? 1})`);
  }
}

export function runDbMigrateDeploy() {
  runAlembicUpgrade();
}

export function runDbPush() {
  runAlembicUpgrade();
}

export function runDbSeed() {
  runDbScript(['--filter', '@bolsa/database', 'db:seed'], 'Seed IBEX');
}
