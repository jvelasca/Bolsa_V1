import { listBackups, readManifest, resolveKeep, resolveMirrorDir } from './lib/backup.mjs';
import { logInfo } from './lib/logger.mjs';

/**
 * pnpm db:backup:list — lista los backups locales en `db-backups/` ordenados
 * por fecha (más reciente primero) con horas legibles, retención y métricas de
 * RPO (antigüedad del snapshot más reciente) + estado de la copia espejo 3-2-1.
 */

// RPO: antigüedad del snapshot más reciente (edad del mtime en ms → humano).
function ageHuman(ms) {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}min`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

const keep = resolveKeep();
const mirrorDir = resolveMirrorDir();
const backups = listBackups();
const manifest = readManifest();
const newest = backups.length ? backups[0] : null;
// Detección de espejo del artefacto más reciente en el manifest.
const newestMf = newest
  ? manifest.find((e) => e.file === newest.name)
  : null;

logInfo('db-backup:list', `Retención (DB_BACKUP_KEEP): ${keep}`);
logInfo('db-backup:list', `Backups en db-backups/: ${backups.length}`);
logInfo(
  'db-backup:list',
  `Espejo 3-2-1 off-site: ${mirrorDir ? 'CONFIGURADO → ' + mirrorDir + '/db-backups' : 'no (solo copia local db-backups). Fija DB_BACKUP_MIRROR_DIR para la 2ª copia en otro árbol/medio.'}`,
);

if (backups.length === 0) {
  logInfo('db-backup:list', 'No hay backups todavía. Prueba: pnpm db:dump');
  process.exit(0);
}

if (newest) {
  const rpo = ageHuman(Date.now() - newest.mtimeMs);
  logInfo('db-backup:list', `RPO (antigüedad del snapshot más reciente): ${rpo}`);
  logInfo(
    'db-backup:list',
    `Último backup ${newestMf?.mirror?.path ? 'con copia espejo ✔' : 'SIN copia espejo (mirror aún no espejó este artefacto)'} (newest: ${newest.name})`,
  );
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

