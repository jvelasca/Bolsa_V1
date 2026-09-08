import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  pgDumpToFile,
  sha256Hex,
  verifyChecksumSidecar,
} from './lib/backup.mjs';
import { ensureProjectDatabase, findDockerExe } from './lib/docker.mjs';
import { logError, logInfo, writeAgentLog } from './lib/logger.mjs';

/**
 * pnpm db:dr:test — batería automática de Disaster Recovery (V2.15 C2).
 *
 * Verifica end-to-end que el pipeline de backup/restore es seguro y trazable:
 *  1. vuelca `bolsa_v1` (con sidecar `.sha256` y manifest) a un directorio temporal,
 *  2. comprueba que el checksum del sidecar coincide con el fichero volcado,
 *  3. restaura ese volcado en una BD scratch (`bolsa_v1_dr_test`) invocando el CLI
 *     real `db:restore ... --target-db` (Alembic debe dirigirse a la scratch),
 *  4. verifica que la scratch queda en el mismo head y con esquema SQL consultable,
 *  5. verifica que `bolsa_v1` (principal) NO cambia de head durante la operación,
 *  6. limpia la scratch en `finally` y reporta un agregado ok/failed.
 *
 * Solo entorno local (contenedor `bolsa-postgres`). NO ejecutar contra producción.
 * Uso: pnpm db:dr:test   (override del nombre scratch con DR_TARGET_DB)
 */

const CONTAINER = 'bolsa-postgres';
const PG_USER = 'bolsa';
const MAIN_DB = 'bolsa_v1';

function summary(checks) {
  return checks.every((c) => c.ok) ? { status: 'ok' } : { status: 'failed' };
}

function psqlQuery(db, sql) {
  const docker = findDockerExe();
  if (!docker) return { ok: false, out: '', err: 'no docker' };
  const r = spawnSync(
    docker,
    [
      'exec',
      CONTAINER,
      'psql',
      '-U',
      PG_USER,
      '-d',
      db,
      '-Atc',
      sql,
      '-v',
      'ON_ERROR_STOP=1',
    ],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
  );
  return {
    ok: r.status === 0,
    out: (r.stdout ?? '').toString().trim(),
    err: (r.stderr ?? '').toString().trim(),
  };
}

function readRevision(db) {
  const q = psqlQuery(db, 'SELECT version_num FROM alembic_version LIMIT 1;');
  return q.ok && q.out ? q.out : null;
}

function countPublicTables(db) {
  const q = psqlQuery(
    db,
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';",
  );
  return q.ok ? Number.parseInt(q.out || '0', 10) : 0;
}

function maintenance(query) {
  const docker = findDockerExe();
  const q = spawnSync(
    docker,
    ['exec', CONTAINER, 'psql', '-U', PG_USER, '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', query],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
  );
  return { ok: q.status === 0, stderr: (q.stderr ?? '').toString().trim() };
}

async function main() {
  let docker = findDockerExe();
  const checks = [];
  const targetDB = process.env.DR_TARGET_DB ?? 'bolsa_v1_dr_test';
  let tmpDir = null;
  let dumpFile = null;

  try {
    if (!docker) throw new Error('Docker CLI no disponible');
    // Asegurar Docker + PostgreSQL del proyecto (auto-arranque como db:dump).
    if (!(await ensureProjectDatabase()).ok) {
      logError('db-dr-verify', 'No se pudo asegurar Docker/PostgreSQL');
    }
    docker = findDockerExe();
    logInfo('db-dr-verify', `Batería DR sobre contenedor, scratch="${targetDB}"`);

    // Snapshot del estado de la BD principal ANTES.
    const mainHeadBefore = readRevision(MAIN_DB);
    if (!mainHeadBefore) throw new Error('No se pudo leer el head de bolsa_v1 (¿migrado?)');
    logInfo('db-dr-verify', `head principal (antes): ${mainHeadBefore}`);

    // (1) Volcado temporal + sidecar/manifest.
    tmpDir = mkdtempSync(join(tmpdir(), 'bolsa-dr-'));
    const dumped = pgDumpToFile({ dir: tmpDir, gzip: false, db: MAIN_DB });
    dumpFile = dumped.file;
    const freshSha = sha256Hex(readFileSync(dumpFile));
    checks.push(
      freshSha === dumped.sha256
        ? { ok: true, name: 'dump-hash-calculado-coincide', detail: dumped.sha256 }
        : { ok: false, name: 'dump-integrity', detail: 'sha interno no coincide' },
    );

    // (2) Checksum del sidecar verificado.
    const side = verifyChecksumSidecar(dumpFile);
    checks.push(
      side.ok
        ? { ok: true, name: 'sidecar-checksum', detail: side.code }
        : { ok: false, name: 'sidecar-checksum', detail: side.code },
    );

    // (3a) Garantizar scratch limpia antes del restore.
    const dropMaintenance = maintenance(`DROP DATABASE IF EXISTS "${targetDB}" WITH (FORCE);`);
    if (!dropMaintenance.ok) {
      throw new Error(`No se pudo limpiar scratch ${targetDB}: ${dropMaintenance.stderr}`);
    }

    // (3b) Invocamos el CLI real con --target-db → el restore + Alembic va a la scratch.
    logInfo('db-dr-verify', `Restaurando volcado en "${targetDB}" (Alembic dirigido a scratch)...`);
    const restore = spawnSync(
      process.execPath,
      ['scripts/db-restore.mjs', '--file', dumpFile, '--target-db', targetDB, '--yes'],
      { encoding: 'utf8', stdio: ['inherit'] },
    );
    checks.push(
      restore.status === 0
        ? { ok: true, name: 'db-restore-cli-exit0' }
        : { ok: false, name: 'db-restore-cli-exit', detail: `exit=${restore.status}` },
    );

    // (4) La scratch quedó al head y con esquema consultable.
    const scratchRev = readRevision(targetDB);
    checks.push(
      scratchRev === mainHeadBefore
        ? { ok: true, name: 'scratch-al-alineado-head', detail: scratchRev }
        : { ok: false, name: 'scratch-head', detail: `${scratchRev} vs esperado ${mainHeadBefore}` },
    );
    const scratchTables = countPublicTables(targetDB);
    checks.push(
      scratchTables > 0
        ? { ok: true, name: 'scratch-esquema-consultable', detail: `${scratchTables} tablas public` }
        : { ok: false, name: 'scratch-esquema', detail: '0 tablas public (restore vacío?)' },
    );

    // (5) La BD principal NO cambió de head.
    const mainHeadAfter = readRevision(MAIN_DB);
    checks.push(
      mainHeadAfter === mainHeadBefore
        ? { ok: true, name: 'principal-intacta', detail: mainHeadAfter }
        : { ok: false, name: 'principal-cambiada', detail: `${mainHeadAfter} vs ${mainHeadBefore}` },
    );

    const verdict = summary(checks);
    for (const c of checks) {
      logInfo('db-dr-verify', `${c.ok ? 'PASS' : 'FAIL'} · ${c.name} · ${c.detail ?? ''}`);
    }
    logInfo('db-dr-verify', `Resultado agregado: ${verdict.status} (scratch="${targetDB}")`);
    writeAgentLog('db-dr-verify', { status: verdict.status, targetDB, checks });
    if (verdict.status === 'failed') {
      process.exitCode = 1;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logError('db-dr-verify', message);
    writeAgentLog('db-dr-verify', { status: 'failed', error: message });
    process.exitCode = 1;
  } finally {
    // (6) Limpieza de la scratch y del dump temporal, independientemente del resultado.
    if (targetDB !== MAIN_DB) {
      const rm = maintenance(`DROP DATABASE IF EXISTS "${targetDB}" WITH (FORCE);`);
      if (!rm.ok) {
        logError('db-dr-verify', `No se pudo limpiar scratch ${targetDB}: ${rm.stderr}`);
      } else {
        logInfo('db-dr-verify', `Scratch "${targetDB}" eliminada`);
      }
    }
    if (tmpDir) {
      try {
        rmSync(tmpDir, { recursive: true, force: true });
      } catch {
        /* best-effort */
      }
    }
  }
}

await main();
