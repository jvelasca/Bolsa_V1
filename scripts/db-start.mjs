import { ensureProjectDatabase, printDockerInstallHelp } from './lib/docker.mjs';
import { logError, logInfo } from './lib/logger.mjs';

const result = await ensureProjectDatabase();

if (!result.ok) {
  logError('db-start', result.message ?? 'No se pudo preparar Docker/PostgreSQL');
  printDockerInstallHelp();
  process.exit(1);
}

if (result.dockerStarted) {
  logInfo('db-start', 'Docker Desktop se abrió automáticamente');
}

logInfo('db-start', 'PostgreSQL en marcha. Siguiente: pnpm db:push && pnpm db:seed');
