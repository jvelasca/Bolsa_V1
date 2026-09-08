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
 *
 * @param {object} options
 * @param {string} [options.databaseUrl] Dirige Alembic a una BD distinta de la
 *   global: reescribe `DATABASE_URL` del subproceso Python para que
 *   `ensure_migrated` migre esa BD y NO la principal del `.env`/entorno
 *   (usado por `db:restore --target-db`, hallazgo V2.15-01 del auditor externo).
 */
export function runAlembicUpgrade(options = {}) {
  loadEnvFile();
  const py = resolvePython();
  const infraSrc = join(ROOT, 'packages', 'py', 'infrastructure', 'src');
  const sep = process.platform === 'win32' ? ';' : ':';
  const pythonPath = [infraSrc, process.env.PYTHONPATH].filter(Boolean).join(sep);
  const env = { ...process.env, PYTHONPATH: pythonPath };
  if (options.databaseUrl) {
    // Sobrescribir siempre (aunque el padre ya tuviera DATABASE_URL): el objetivo
    // es dirigir la migración explícitamente a la BD restaurada (V2.15-01).
    env.DATABASE_URL = options.databaseUrl;
  }
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
      env,
    },
  );
  if (result.status !== 0) {
    throw new Error(`Alembic upgrade falló (código ${result.status ?? 1})`);
  }
}

/**
 * Reemplaza la base de datos del ``DATABASE_URL`` efectivo por ``dbName``,
 * preservando host/puerto/usuario/password/esquema (sin inspeccionar credenciales).
 *
 * Localmente ``DATABASE_URL`` suele ser
 * ``postgresql+psycopg://bolsa:***@localhost:5432/bolsa_v1?schema=public``;
 * sustituimos únicamente el último segmento de la ruta antes de ``?``.
 */
export function redirectDatabaseUrlTo(dbName, options = {}) {
  loadEnvFile();
  const current = options.databaseUrl ?? process.env.DATABASE_URL;
  if (!current) {
    throw new Error('DATABASE_URL no configurado; no puedo recalcular el destino de la BD');
  }
  if (!/^[a-zA-Z0-9_.-]+$/.test(dbName)) {
    throw new Error(`Nombre de BD inválido: ${dbName}`);
  }
  const qIndex = current.indexOf('?');
  const base = qIndex === -1 ? current : current.slice(0, qIndex);
  const query = qIndex === -1 ? '' : current.slice(qIndex);
  const slash = base.lastIndexOf('/');
  const head = slash === -1 ? base : base.slice(0, slash + 1);
  return `${head}${dbName}${query}`;
}

export function runDbMigrateDeploy(options = {}) {
  runAlembicUpgrade(options.databaseUrl ? { databaseUrl: options.databaseUrl } : {});
}

export function runDbPush(options = {}) {
  runAlembicUpgrade(options.databaseUrl ? { databaseUrl: options.databaseUrl } : {});
}

export function runDbSeed() {
  runDbScript(['--filter', '@bolsa/database', 'db:seed'], 'Seed IBEX');
}
