import { ensureProjectDatabase, printDockerInstallHelp, checkPort } from './lib/docker.mjs';
import { runDbMigrateDeploy, runDbSeed } from './lib/db.mjs';
import { logError, logInfo, writeAgentLog } from './lib/logger.mjs';

const pingOnly = process.argv.includes('--ping');
const withMigrate = process.argv.includes('--migrate');

async function ensurePing() {
  const postgresUp = await checkPort('127.0.0.1', 5432);
  if (postgresUp) {
    return { ok: true, message: 'PostgreSQL responde en localhost:5432' };
  }
  return {
    ok: false,
    step: 'postgres',
    error: 'POSTGRES_DOWN',
    message:
      'PostgreSQL no responde en localhost:5432. Abre Docker Desktop y ejecuta: node scripts/db-ensure.mjs',
  };
}

const result = pingOnly ? await ensurePing() : await ensureProjectDatabase();

writeAgentLog('db-ensure', {
  status: result.ok ? 'ready' : 'failed',
  step: result.step ?? 'complete',
  dockerStarted: result.dockerStarted ?? false,
  postgresStarted: result.postgresStarted ?? false,
  message: result.message,
  error: result.error,
});

if (!result.ok) {
  logError('db-ensure', result.message ?? 'Fallo al preparar Docker/PostgreSQL', result);
  if (!pingOnly) printDockerInstallHelp();
  process.exit(1);
}

if (result.dockerStarted) {
  logInfo('db-ensure', 'Docker Desktop se abrió automáticamente');
}
if (result.postgresStarted) {
  logInfo('db-ensure', 'Contenedor bolsa-postgres iniciado');
}

if (!pingOnly) {
  try {
    logInfo('db-ensure', 'Aplicando migraciones Prisma...');
    runDbMigrateDeploy();
    logInfo('db-ensure', 'Cargando catálogo IBEX...');
    runDbSeed();
  } catch (error) {
    logError('db-ensure', error instanceof Error ? error.message : 'Error en BD');
    process.exit(1);
  }
  logInfo('db-ensure', 'Docker, PostgreSQL y catálogo IBEX listos');
} else if (withMigrate) {
  try {
    logInfo('db-ensure', 'Aplicando migraciones Prisma...');
    runDbMigrateDeploy();
  } catch (error) {
    logError('db-ensure', error instanceof Error ? error.message : 'Error en BD');
    process.exit(1);
  }
  logInfo('db-ensure', 'PostgreSQL listo (ping + migrate)');
} else {
  logInfo('db-ensure', 'PostgreSQL OK (ping)');
}
