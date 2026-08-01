import { checkPort, ensureProjectDatabase, printDockerInstallHelp } from './lib/docker.mjs';
import { runDbMigrateDeploy, runDbSeed } from './lib/db.mjs';
import { logError, logInfo, writeAgentLog } from './lib/logger.mjs';

const portOpen = await checkPort('127.0.0.1', 5432);

if (portOpen) {
  writeAgentLog('db-check', { status: 'ready', postgresPort5432: 'open' });
  logInfo('db-check', 'PostgreSQL responde en localhost:5432');
  process.exit(0);
}

logError('db-check', 'PostgreSQL NO esta activo — preparando Docker...');

const result = await ensureProjectDatabase();

writeAgentLog('db-check', {
  status: result.ok ? 'ready' : 'failed',
  postgresPort5432: result.ok ? 'open' : 'closed',
  dockerStarted: result.dockerStarted ?? false,
  postgresStarted: result.postgresStarted ?? false,
});

if (!result.ok) {
  printDockerInstallHelp();
  process.exit(1);
}

logInfo('db-check', 'PostgreSQL listo. Aplicando migraciones y seed...');

try {
  runDbMigrateDeploy();
  runDbSeed();
} catch (error) {
  logError('db-check', error instanceof Error ? error.message : 'Error en BD');
  process.exit(1);
}

logInfo('db-check', 'Base de datos inicializada correctamente');
