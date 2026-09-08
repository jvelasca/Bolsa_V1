import {
  ensureProjectDatabase,
  findDockerExe,
  isPostgresReady,
} from "./lib/docker.mjs";
import { pgDumpToFile, retentionPrune, resolveKeep } from "./lib/backup.mjs";
import { logError, logInfo, writeAgentLog } from "./lib/logger.mjs";

/**
 * pnpm db:dump — genera un volcado local de `bolsa_v1` en `db-backups/`
 * y poda por retención (DB_BACKUP_KEEP, default 14).
 * Uso:
 *   node scripts/db-dump.mjs            # bolsa_v1 → db-backups/bolsa_v1-<stamp>.sql[.gz]
 *   node scripts/db-dump.mjs --keep 30
 *   node scripts/db-dump.mjs --no-gzip
 */

const cliKeep = process.argv.indexOf("--keep");
const keepFromCli =
  cliKeep >= 0
    ? Number.parseInt(process.argv[cliKeep + 1] ?? "", 10)
    : undefined;
const wantGzip = !process.argv.includes("--no-gzip");

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

  try {
    const { file, bytes, gzipped } = pgDumpToFile({ gzip: wantGzip });
    logInfo(
      "db-dump",
      `Backup creado: ${file} (${bytes} bytes${gzipped ? ", gzip" : ""}) · retención ${keep}`,
    );
    const pruned = retentionPrune(keep);
    if (pruned > 0) {
      logInfo(
        "db-dump",
        `Podados ${pruned} backup(s) más antiguo(s) (keep=${keep})`,
      );
    }
    writeAgentLog("db-dump", {
      status: "ok",
      file,
      bytes,
      gzipped,
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
