import { runPnpm } from './lib/pnpm.mjs';
import { ensureLogDirs, logInfo, logError, ROOT, writeAgentLog } from './lib/logger.mjs';

ensureLogDirs();

logInfo('tests', 'Ejecutando suite de tests...');

const result = runPnpm(['test'], {
  cwd: ROOT,
  shell: true,
  encoding: 'utf8',
  env: { ...process.env, FORCE_COLOR: '0' },
});

const output = `${result.stdout ?? ''}${result.stderr ?? ''}`;
process.stdout.write(result.stdout ?? '');
process.stderr.write(result.stderr ?? '');

const stamp = new Date().toISOString().replace(/[:.]/g, '-');
import('node:fs').then(({ writeFileSync, mkdirSync }) => {
  mkdirSync(`${ROOT}/logs/tests`, { recursive: true });
  writeFileSync(`${ROOT}/logs/tests/run-${stamp}.log`, output, 'utf8');
  writeFileSync(`${ROOT}/logs/tests/latest.log`, output, 'utf8');
});

const summary = {
  status: result.status === 0 ? 'passed' : 'failed',
  exitCode: result.status,
  logFile: 'logs/tests/latest.log',
};

writeAgentLog('tests', summary);

if (result.status !== 0) {
  logError('tests', 'Tests fallidos', summary);
  process.exit(result.status ?? 1);
}

logInfo('tests', 'Todos los tests pasaron', summary);
