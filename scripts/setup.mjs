import { copyFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ensureProjectDatabase, printDockerInstallHelp } from './lib/docker.mjs';
import { runDbGenerate, runDbPush, runDbSeed } from './lib/db.mjs';
import { ensureLogDirs, logInfo, logError, ROOT, writeAgentLog } from './lib/logger.mjs';
import { runPnpm } from './lib/pnpm.mjs';

function runPnpmStep(args, label) {
  logInfo('setup', `Ejecutando: pnpm ${args.join(' ')}`);
  const result = runPnpm(args);
  if (result.status !== 0) {
    logError('setup', `${label} falló`, { exitCode: result.status });
    process.exit(result.status ?? 1);
  }
}

ensureLogDirs();

if (!existsSync(join(ROOT, '.env'))) {
  copyFileSync(join(ROOT, '.env.example'), join(ROOT, '.env'));
  logInfo('setup', 'Creado .env desde .env.example');
}

const webEnv = join(ROOT, 'apps/web/.env');
if (!existsSync(webEnv)) {
  copyFileSync(join(ROOT, 'apps/web/.env.example'), webEnv);
  logInfo('setup', 'Creado apps/web/.env');
}

runPnpmStep(['install'], 'pnpm install');

logInfo('setup', 'Comprobando Docker y PostgreSQL...');
const db = await ensureProjectDatabase();
if (!db.ok) {
  printDockerInstallHelp();
  process.exit(1);
}

try {
  runDbGenerate();
  runDbPush();
  runDbSeed();
} catch (error) {
  logError('setup', error instanceof Error ? error.message : 'Error en BD');
  process.exit(1);
}

runPnpmStep(['test'], 'tests');

writeAgentLog('setup', { status: 'ok', message: 'Setup completado' });
logInfo('setup', 'Setup completado. Ejecuta: node scripts/run-dev.mjs');
