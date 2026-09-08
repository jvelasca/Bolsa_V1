import { spawnSync } from 'node:child_process';
import {
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { join } from 'node:path';
import { findDockerExe } from './docker.mjs';
import { logError, logInfo, ROOT } from './logger.mjs';
import { loadEnvFile } from './load-env.mjs';

/**
 * Copias de seguridad locales de la BD `bolsa_v1` (PREVENCIÓN V2.15).
 *
 * La BD de dev vive en un contenedor Docker (`bolsa-postgres`); su volumen es
 * persistente pero NO se versiona ni se copia sola. El incidente del 2026-09-08
 * (BBDD quedó seed-only sin listas/membresía y sin pg_dump) dejó claro que los
 * estados runtime no versionados son irrecuperables sin copia. Por eso volcamos
 * POR FUERA del contenedor a `db-backups/` (carpeta local, dentro de
 * `.gitignore`), listable y podable por retención.
 *
 * Esta carpeta es SOLO entorno local `bolsa_v1`. Nunca ejecutar automáticamente
 * contra una BD productiva compartida.
 */

export const BACKUP_DIR = join(ROOT, 'db-backups');

const CONTAINER_DEFAULT = 'bolsa-postgres';
const PG_USER_DEFAULT = 'bolsa';
const PG_DB_DEFAULT = 'bolsa_v1';

/** Sello local `YYYYMMDD-HHMMSS` (huso de la máquina, no UTC). */
export function buildFileStamp(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

export function backupDir() {
  return BACKUP_DIR;
}

/** Asegura que existe la carpeta local de backups (fuera del contenedor). */
export function ensureBackupHostDir(dir = BACKUP_DIR) {
  mkdirSync(dir, { recursive: true });
  return dir;
}

/** ¿Existe un binario `gzip` utilizable? (portable; en Windows suele faltar). */
function hasGzip() {
  const probe = spawnSync('gzip', ['--version'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return probe.status === 0;
}

/**
 * Ejecuta `docker exec` de un volcado de PostgreSQL a fichero local.
 *
 * @param {object} opts
 * @param {string} [opts.docker] binario docker (auto if omitido)
 * @param {string} [opts.db] base de datos a volcar (bolsa_v1)
 * @param {boolean} [opts.gzip] comprimir si hay `gzip` disponible
 * @param {string} [opts.dir] carpeta destino (BACKUP_DIR)
 * @returns {{file:string, bytes:number, gzipped:boolean}}
 */
export function pgDumpToFile(opts = {}) {
  const docker = opts.docker ?? findDockerExe();
  const db = opts.db ?? PG_DB_DEFAULT;
  const wantGzip = opts.gzip !== false;
  const dir = ensureBackupHostDir(opts.dir ?? BACKUP_DIR);
  if (!docker) {
    throw new Error('Docker CLI no disponible — no se puede volcar la BD');
  }

  const gzip = wantGzip && hasGzip();
  const stamp = buildFileStamp();
  const fileName = `bolsa_v1-${stamp}.sql${gzip ? '.gz' : ''}`;
  const outPath = join(dir, fileName);

  logInfo('backup', `Vaciando ${db} → ${outPath}`);

  // Capturamos stdout cruda a buffer y la escribimos aparte (evita que la consola
  // de Windows (PowerShell) reinterprete bytes / añada CRLF al volcado).
  const result = spawnSync(
    docker,
    ['exec', CONTAINER_DEFAULT, 'pg_dump', '-U', PG_USER_DEFAULT, '-d', db],
    {
      encoding: 'buffer',
      maxBuffer: 1024 * 1024 * 512, // hasta ~512 MB de volcado razonable
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  const stderr = (result.stderr ?? Buffer.alloc(0)).toString('utf8');
  if (result.status !== 0) {
    throw new Error(
      `pg_dump falló (código ${result.status ?? result.error?.code ?? 1}): ${stderr.trim() || 'sin detalle'}`,
    );
  }

  let payload = Buffer.isBuffer(result.stdout) ? result.stdout : Buffer.from(result.stdout ?? '');
  if (gzip) {
    const gz = spawnSync('gzip', ['-c'], {
      input: payload,
      encoding: 'buffer',
      maxBuffer: 1024 * 1024 * 512,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    if (gz.status !== 0) {
      throw new Error(`gzip falló: ${(gz.stderr ?? '').toString('utf8').trim()}`);
    }
    payload = Buffer.isBuffer(gz.stdout) ? gz.stdout : Buffer.from(gz.stdout ?? '');
  }
  writeFileSync(outPath, payload);
  return { file: outPath, bytes: payload.length, gzipped: gzip };
}

/** Lista los backups de la carpeta (solo ficheros `*.sql*`), por mtime desc. */
export function listBackups({ dir = BACKUP_DIR } = {}) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  return entries
    .filter((e) => e.isFile() && e.name.toLowerCase().startsWith('bolsa_v1-') && /\.sql/.test(e.name.toLowerCase()))
    .map((e) => {
      const full = join(dir, e.name);
      const st = statSync(full);
      return { name: e.name, full, bytes: st.size, mtimeMs: st.mtimeMs, mtime: st.mtime };
    })
    .sort((a, b) => b.mtimeMs - a.mtimeMs);
}

/**
 * Podado por retención de backups (modelado en `pruneStampedLogs` de logger.mjs).
 * Conserva los `keep` más recientes y borra los más viejos. Devuelve el nº borrado.
 */
export function retentionPrune(keep, { dir = BACKUP_DIR } = {}) {
  const keepN = Number.isFinite(keep) && keep > 0 ? Math.floor(keep) : 0;
  const entries = listBackups({ dir });
  if (keepN <= 0 || entries.length <= keepN) return 0;
  const toRemove = entries.slice(keepN);
  let removed = 0;
  for (const entry of toRemove) {
    try {
      rmSync(entry.full, { force: true });
      removed += 1;
    } catch {
      logError('backup', `No se pudo podar ${entry.name} (en uso?)`);
    }
  }
  return removed;
}

/**
 * Resolución del `keep` desde env `.env`/shell (DB_BACKUP_KEEP) con default.
 * @param {number} fallback
 * @returns {number}
 */
export function resolveKeep(opts = {}) {
  loadEnvFile();
  const envVal = opts.envKeep ?? process.env.DB_BACKUP_KEEP;
  const parsed = Number.parseInt(String(envVal ?? ''), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : (opts.defaultKeep ?? 14);
}

/** Comprueba que el fichero existe (error claro si no). */
export function requireBackupFile(file) {
  const st = statSync(file);
  if (!st.isFile() || st.size === 0) {
    throw new Error(`El fichero ${file} no es un backup válido (vacío/inexistente)`);
  }
  return file;
}

/**
 * Devuelve el contenido del backup a restaurar a través de psql por STDIN.
 * Devuelve bytes/string; si el fichero está `.gz` NO lo descomprime aquí,
 * la decisión de pipe se deja en el llamante (db-restore lo maneja).
 * @param {string} file
 */
export function readBackupBytes(file) {
  requireBackupFile(file);
  return readFileSync(file);
}
