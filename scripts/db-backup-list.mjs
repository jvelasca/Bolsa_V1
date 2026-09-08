import { listBackups, resolveKeep } from './lib/backup.mjs';
import { logInfo } from './lib/logger.mjs';

/**
 * pnpm db:backup:list — lista los backups locales en `db-backups/` ordenados
 * por fecha (más reciente primero) con horas legibles, y la retención vigente.
 */

const keep = resolveKeep();
const backups = listBackups();

logInfo('db-backup:list', `Retención (DB_BACKUP_KEEP): ${keep}`);
logInfo('db-backup:list', `Backups en db-backups/: ${backups.length}`);

if (backups.length === 0) {
  logInfo('db-backup:list', 'No hay backups todavía. Prueba: pnpm db:dump');
  process.exit(0);
}

backups.forEach((b, i) => {
  const tag = i === 0 ? ' (más reciente)' : '';
  logInfo(
    'db-backup:list',
    `${String(i + 1).padStart(2)}. ${b.name} — ${b.mtime.toISOString()} — ${((b.bytes / 1024) / 1024).toFixed(1)} MB${tag}`,
  );
});

const over = Math.max(0, backups.length - keep);
logInfo('db-backup:list', over > 0 ? `Sobran ${over} (se podarán en el próximo db:dump).` : 'Retención dentro del límite.');
