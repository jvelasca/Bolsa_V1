import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { basename, join } from 'node:path';
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

/** Sello local `YYYYMMDD-HHMMSS-mmm` (huso de la máquina, no UTC). */
export function buildFileStamp(date = new Date()) {
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}` +
    `-${pad(date.getMilliseconds(), 3)}`
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

/** Sha256 en hex de un buffer (sidecar checksum / manifest). */
export function sha256Hex(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

/** Revisión Alembic actual (best-effort) leyendo `alembic_version` en la BD. */
function readDbSchema(docker, db) {
  try {
    const q = spawnSync(
      docker,
      [
        'exec',
        CONTAINER_DEFAULT,
        'psql',
        '-U',
        PG_USER_DEFAULT,
        '-d',
        db,
        '-Atc',
        'SELECT version_num FROM alembic_version LIMIT 1;',
      ],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
    );
    if (q.status !== 0) return null;
    const rev = (q.stdout ?? '').toString().trim();
    return rev || null;
  } catch {
    return null;
  }
}

/** Ruta del sidecar de checksum `<backupFile>.sha256`. */
export function backupSidecarPath(backupFile) {
  return `${backupFile}.sha256`;
}

/** Devuelve el expect checksum del sidecar, o null si no hay sidecar. */
export function readSidecarSha256(backupFile) {
  try {
    const raw = readFileSync(backupSidecarPath(backupFile), 'utf8').trim();
    const first = raw.split(/\s+/)[0] ?? '';
    return /^[0-9a-f]{64}$/i.test(first) ? first.toLowerCase() : null;
  } catch {
    return null;
  }
}

/**
 * Comprueba que el sidecar de checksum coincide con el fichero (si el sidecar
 * existe). Devuelve ``{ ok, code }``:
 *   - ok=true  → coinciden (o no existe sidecar: legacy, no bloquea).
 *   - ok=false, code='MISMATCH' → el fichero no coincide con su checksum.
 */
export function verifyChecksumSidecar(backupFile) {
  const expected = readSidecarSha256(backupFile);
  if (!expected) return { ok: true, code: 'NO_SIDECAR' };
  const actual = sha256Hex(readFileSync(backupFile));
  return actual === expected ? { ok: true, code: 'OK' } : { ok: false, code: 'MISMATCH' };
}

/** Ruta del manifest de backups (historial de artefactos + checksum). */
function manifestPath(dir) {
  return join(dir, 'backups-manifest.json');
}

/** Lee el manifest JSON (array de entradas) o [] si no existe/corrupto. */
function readManifest(dir) {
  try {
    const parsed = JSON.parse(readFileSync(manifestPath(dir), 'utf8'));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/**
 * Reconstruye el manifest a partir de los ficheros `.sql[.gz]` presentes, para que
 * nunca queden entradas huérfanas tras un ``retentionPrune`` (V2.15-09/-11).
 */
export function reconcileManifest({ dir = BACKUP_DIR } = {}) {
  ensureBackupHostDir(dir);
  const existing = new Map((readManifest(dir) || []).map((e) => [e.file, e]));
  const seen = new Set();
  const next = listBackups({ dir }).map((b) => {
    const name = b.name;
    seen.add(name);
    const known = existing.get(name) || {};
    let sha = known.sha256 ?? null;
    if (!sha) {
      try {
        sha = sha256Hex(readFileSync(b.full));
      } catch {
        sha = null;
      }
    }
    return {
      file: name,
      sha256: sha,
      bytes: b.bytes,
      created_at: known.created_at ?? b.mtime.toISOString(),
      schema: known.schema ?? null,
    };
  });
  const merged = readManifest(dir).filter((e) => seen.has(e.file)).concat(next);
  const dedup = [...new Map(merged.map((e) => [e.file, e])).values()].sort((a, b) =>
    a.file < b.file ? -1 : 1
  );
  writeFileSync(manifestPath(dir), `${JSON.stringify(dedup, null, 2)}\n`, 'utf8');
  return dedup;
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
 * Tras el volcado escribe el backup con ``O_EXCL`` (nunca sobrescribe), un sidecar
 * ``<file>.sha256`` y actualiza `backups-manifest.json` con checksum/bytes/fecha y
 * el esquema Alembic actual (V2.15-09/-10/-11).
 *
 * @param {object} opts
 * @param {string} [opts.docker] binario docker (auto if omitido)
 * @param {string} [opts.db] base de datos a volcar (bolsa_v1)
 * @param {boolean} [opts.gzip] comprimir si hay `gzip` disponible
 * @param {string} [opts.dir] carpeta destino (BACKUP_DIR)
 * @returns {{file:string, bytes:number, gzipped:boolean, sha256:string, schema:string|null}}
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

  const sha = sha256Hex(payload);
  try {
    writeFileSync(outPath, payload, { flag: 'wx' });
  } catch (error) {
    // 'wx' → O_EXCL: nunca sobrescribir un backup ya existente (V2.15-10).
    throw new Error(
      `No se pudo crear ${fileName}: ya existe (O_EXCL). Reintenta. (${error?.code ?? error?.message ?? error})`,
    );
  }

  // Sidecar checksum `<file>.sha256` (V2.15-11).
  writeFileSync(`${outPath}.sha256`, `${sha}  ${fileName}\n`, 'utf8');

  // Manifest con checksum/bytes/fecha/esquema actual best-effort (V2.15-09).
  const schema = readDbSchema(docker, db);
  const manifest = readManifest(dir);
  manifest.push({
    file: fileName,
    sha256: sha,
    bytes: payload.length,
    created_at: new Date().toISOString(),
    schema,
  });
  writeFileSync(manifestPath(dir), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

  return { file: outPath, bytes: payload.length, gzipped: gzip, sha256: sha, schema };
}

/** Lista los backups de la carpeta (solo artefactos `.sql`/`.sql.gz`), por mtime desc. */
export function listBackups({ dir = BACKUP_DIR } = {}) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const isBackup = (name) => /^bolsa_v1-.+\.sql(\.gz)?$/i.test(name);
  return entries
    .filter((e) => e.isFile() && isBackup(e.name))
    .map((e) => {
      const full = join(dir, e.name);
      const st = statSync(full);
      return { name: e.name, full, bytes: st.size, mtimeMs: st.mtimeMs, mtime: st.mtime };
    })
    .sort((a, b) => b.mtimeMs - a.mtimeMs);
}

/**
 * Podado por retención de backups (modelado en `pruneStampedLogs` de logger.mjs).
 * Conserva los `keep` más recientes y borra los más viejos (y su sidecar `.sha256`).
 * Devuelve el nº de backups borrados. Regenera el manifest en `finally`.
 */
export function retentionPrune(keep, { dir = BACKUP_DIR } = {}) {
  const keepN = Number.isFinite(keep) && keep > 0 ? Math.floor(keep) : 0;
  const entries = listBackups({ dir });
  if (keepN <= 0 || entries.length <= keepN) {
    reconcileManifest({ dir });
    return 0;
  }
  const toRemove = entries.slice(keepN);
  let removed = 0;
  for (const entry of toRemove) {
    try {
      rmSync(entry.full, { force: true });
      try {
        rmSync(`${entry.full}.sha256`, { force: true });
      } catch {
        /* sidecar opcional */
      }
      removed += 1;
    } catch {
      logError('backup', `No se pudo podar ${entry.name} (en uso?)`);
    }
  }
  try {
    reconcileManifest({ dir });
  } catch {
    /* manifest es best-effort: no debe tumbar la retención */
  }
  return removed;
}

/**
 * Resolución del `keep` desde env `.env`/shell (DB_BACKUP_KEEP) con default.
 * Mínimo seguro `>= 1`: `DB_BACKUP_KEEP=0` (typo frecuente) queda desactivada y
 * se sustituye por el mínimo/default para que una retención nunca deje 0 backups
 * (hallazgo V2.15-13 del auditor externo).
 * @param {number} fallback
 * @returns {number}
 */
export function resolveKeep(opts = {}) {
  const minKeep = opts.minKeep ?? 1;
  loadEnvFile();
  const envVal = opts.envKeep ?? process.env.DB_BACKUP_KEEP;
  const raw = (envVal ?? '').toString().trim();
  const parsed = Number.parseInt(raw, 10);
  if (!raw || !Number.isFinite(parsed)) {
    return opts.defaultKeep ?? 14;
  }
  if (parsed < minKeep) {
    logError('backup', `DB_BACKUP_KEEP=${raw} < mínimo ${minKeep}; usando mínimo seguro`);
    return minKeep;
  }
  return parsed;
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
