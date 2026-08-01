import { runPnpm } from './pnpm.mjs';
import { ROOT } from './logger.mjs';

function runDbScript(args, label) {
  const result = runPnpm(args, { cwd: ROOT });
  if (result.status !== 0) {
    throw new Error(`${label} falló (código ${result.status ?? 1})`);
  }
}

export function runDbGenerate() {
  runDbScript(['--filter', '@bolsa/database', 'db:generate'], 'Prisma generate');
}

export function runDbMigrateDeploy() {
  runDbScript(['--filter', '@bolsa/database', 'db:migrate:deploy'], 'Prisma migrate deploy');
}

export function runDbPush() {
  runDbScript(
    ['--filter', '@bolsa/database', 'exec', 'dotenv', '-e', '../../.env', '--', 'prisma', 'db', 'push', '--accept-data-loss'],
    'Prisma db push',
  );
}

export function runDbSeed() {
  runDbScript(['--filter', '@bolsa/database', 'db:seed'], 'Seed IBEX');
}
