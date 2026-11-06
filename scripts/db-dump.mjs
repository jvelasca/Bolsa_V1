import {
  ensureProjectDatabase,
  findDockerExe,
  isPostgresReady,
} from "./lib/docker.mjs";
import {
  pgDumpToFile,
  resolveMirrorDir,
  retentionPrune,
  resolveKeep,
} from "./lib/backup.mjs";
import { logError, logInfo, writeAgentLog } from "./lib/logger.mjs";

/**
 * pnpm db:dump — genera un volcado local de `bolsa_v1` en `db-backups/`
 * y poda por retención (DB_BACKUP_KEEP, default 14).
 * Uso:
 *   node scripts/db-dump.mjs            # bolsa_v1 → db-backups/bolsa_v1-<stamp>.sql[.gz]
 *   node scripts/db-dump.mjs --keep 30
 *   node scripts/db-dump.mjs --no-gzip
 *   node scripts/db-dump.mjs --dir <ruta>   # directorio destino (p. ej. DB_BACKUP_DIR)
 */

const cliKeep = process.argv.indexOf("--keep");
const keepFromCli =
  cliKeep >= 0
    ? Number.parseInt(process.argv[cliKeep + 1] ?? "", 10)
    : undefined;
const wantGzip = !process.argv.includes("--no-gzip");
// ``--dir``: la copia bajo demanda desde la API (POST /api/database/backup) escribe en
// el MISMO directorio que lee ``BackupInventoryAdapter`` (``DB_BACKUP_DIR``). Sin flag,
// se conserva el default histórico ``db-backups/`` en la raíz del repo.
const cliDir = process.argv.indexOf("--dir");
const dirFromCli =
  cliDir >= 0 ? (process.argv[cliDir + 1] ?? "").trim() || undefined : undefined;

async function main() {
  const docker = findDockerExe();

  // Asegura Docker + contenedor PostgreSQL si no está listo (reutiliza db-ensure).
  if (docker && !isPostgresReady(docker)) {
    logInfo("db-dump", "PostgreSQL no listo — arrancando Docker/Postgres...");
    const ensure = await ensureProjectDatabase();
    if (!ensure.ok) {
      logError("db-dump", ensure.message ?? "No se pudo asegurar la BD");
      writeAgentLog("db-dump", {
        status: "failed",
        step: "ensure",
        error: ensure.error,
      });
      process.exit(1);
    }
  }

  const keep = resolveKeep({
    envKeep: keepFromCli !== undefined ? String(keepFromCli) : undefined,
  });
  const mirrorDir = resolveMirrorDir(); // env DB_BACKUP_MIRROR_DIR (2º árbol) o null

  try {
    const t0 = Date.now();
    const { file, bytes, gzipped, mirrorPath } = pgDumpToFile({
      gzip: wantGzip,
      mirrorDir, // espejo 3-2-1: solo si se configura un DIR off-site
      ...(dirFromCli ? { dir: dirFromCli } : {}),
    });
    const dumpMs = Date.now() - t0;
    logInfo(
      "db-dump",
      `Backup creado: ${file} (${bytes} bytes${gzipped ? ", gzip" : ""}) · retención ${keep} · dump ${dumpMs} ms`,
    );
    if (mirrorPath) {
      logInfo(
        "db-dump",
        `Copia espejo 3-2-1 presente en: ${mirrorPath}`,
      );
    } else {
      logInfo(
        "db-dump",
        "Sin espejo off-site (DB_BACKUP_MIRROR_DIR vacío) → 1 sola copia en db-backups.",
      );
    }
    const pruned = retentionPrune(
      keep,
      dirFromCli ? { dir: dirFromCli } : {},
    );
    if (pruned > 0) {
      logInfo(
        "db-dump",
        `Podados ${pruned} backup(s) más antiguo(s) (keep=${keep})`,
      );
    }
    // RPO: antigüedad del snapshot más reciente (desde su creation_alembic head).
    // En este run el backup recién producido es el más reciente → RPO objetivo ~0
    // salvo el retardo de ejecución ya incluido en dumpMs.
    writeAgentLog("db-dump", {
      status: "ok",
      file,
      bytes,
      gzipped,
      mirrorPath: mirrorPath ?? null,
      mirrorEnabled: Boolean(mirrorDir),
      rpoMs: dumpMs, // tiempo desde el inicio del dump hasta snapshot consistente
      keep,
      pruned,
    });
  } catch (error) {
    logError(
      "db-dump",
      error instanceof Error ? error.message : "Error en el dump",
    );
    writeAgentLog("db-dump", {
      status: "failed",
      step: "dump",
      error: String(error),
    });
    process.exit(1);
  }
}

await main();
