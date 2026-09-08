import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { gunzipSync } from "node:zlib";
import {
  clientEnv,
  findDockerExe,
  psqlBase,
  useTcpTransport,
} from "./lib/docker.mjs";
import { readBackupBytes, verifyChecksumSidecar } from "./lib/backup.mjs";
import { runDbMigrateDeploy, redirectDatabaseUrlTo } from "./lib/db.mjs";
import { logError, logInfo, writeAgentLog } from "./lib/logger.mjs";

/**
 * pnpm db:restore — restaura un volcado local `db-backups/<file>` en la BD local.
 *
 * Destructivo: RECREA la BD destino desde cero antes de aplicar el dump, por lo
 * que exige `--yes` (salvo que se pase por STDIN no interactivo) y `--file`.
 *
 *   node scripts/db-restore.mjs --file db-backups/bolsa_v1-<stamp>.sql --yes
 *   node scripts/db-restore.mjs --file db-backups/bolsa_v1-<stamp>.sql.gz --yes --target-db bolsa_v1_restore_test
 *   node scripts/db-restore.mjs --file ... --yes --no-alembic     # no re-aplicar migraciones
 *
 * Garantías de seguridad (V2.15 C2):
 *   - `psql` corre con `-v ON_ERROR_STOP=1`: cualquier error SQL ⇒ restore FAILED.
 *   - La re-aplicación de migraciones Alembic se ejecuta SIEMPRE contra `--target-db`
 *     (re-escribiendo DATABASE_URL al destino), nunca contra la BD principal.
 *
 * SOLO entorno local `bolsa_v1` (o BD de prueba). Nunca una BD productiva.
 */

const CONTAINER = "bolsa-postgres";
const PG_USER = "bolsa";
const PG_DB_DEFAULT = "bolsa_v1";

function flagValue(flag) {
  const idx = process.argv.indexOf(flag);
  return idx >= 0 ? process.argv[idx + 1] : undefined;
}
const withFlag = (f) => process.argv.includes(f);

function readStdinConfirm(prompt) {
  return new Promise((resolve) => {
    const rl = createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(
        answer.trim().toLowerCase() === "y" ||
          answer.trim().toLowerCase() === "yes",
      );
    });
  });
}

function runPsqlViaStdin(db, payload) {
  const base = psqlBase({
    db,
    container: CONTAINER,
    user: PG_USER,
    interactive: true,
  });
  return spawnSync(base.bin, [...base.argv, "-v", "ON_ERROR_STOP=1"], {
    input: payload,
    encoding: "buffer",
    maxBuffer: 1024 * 1024 * 1024,
    stdio: ["pipe", "pipe", "pipe"],
    env: clientEnv(base),
  });
}

function maintenance(query) {
  const base = psqlBase({
    db: "postgres",
    container: CONTAINER,
    user: PG_USER,
  });
  const q = spawnSync(
    base.bin,
    [...base.argv, "-v", "ON_ERROR_STOP=1", "-c", query],
    {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      env: clientEnv(base),
    },
  );
  return { ok: q.status === 0, stderr: (q.stderr ?? "").toString().trim() };
}

async function main() {
  // Docker solo es obligatorio en transporte local. En modo red (BOLSA_DR_TCP)
  // los helpers usan psql de host conectado por TCP (CI release-tag / C2-13).
  const tcp = useTcpTransport();
  if (!tcp && !findDockerExe()) {
    logError("db-restore", "Docker CLI no disponible");
    process.exit(1);
  }

  const file = flagValue("--file");
  if (!file) {
    logError("db-restore", "Falta --file <path.sql|path.sql.gz>");
    logInfo(
      "db-restore",
      "Ej: pnpm db:restore --file db-backups/bolsa_v1-20260908-000000.sql --yes",
    );
    process.exit(1);
  }

  const target = flagValue("--target-db") ?? PG_DB_DEFAULT;
  const runAlembic = !withFlag("--no-alembic");
  const yes = withFlag("--yes");

  let raw = Buffer.alloc(0);
  let payload = Buffer.alloc(0);
  let sourceLabel = "";
  try {
    raw = readBackupBytes(file);
    const isGz = /\.gz$/i.test(file);
    payload = isGz ? gunzipSync(raw) : raw;
    sourceLabel = isGz ? "gzip" : "sql";
  } catch (error) {
    logError(
      "db-restore",
      error instanceof Error ? error.message : "No se pudo leer el backup",
    );
    process.exit(1);
  }

  // Checksum del sidecar (V2.15-11): si existe y no coincide, abortar (un backup
  // corrupto no debe restaurarse en silencio). Ausencia de sidecar = backup legacy.
  const check = verifyChecksumSidecar(file);
  if (check.code === "MISMATCH") {
    logError(
      "db-restore",
      `Checksum del sidecar NO coincide para ${file}; restauración abortada.`,
    );
    process.exit(1);
  }
  if (check.code === "NO_SIDECAR") {
    logInfo(
      "db-restore",
      "Backup sin sidecar .sha256 (legacy); no se pudo auto-verificar integridad.",
    );
  }

  if (!yes) {
    logInfo(
      "db-restore",
      `Se va a DESTRUIR y recrear la BD local "${target}" con ${file} (${sourceLabel}).`,
    );
    const ok = await readStdinConfirm("¿Continuar? [y/N] ");
    if (!ok) {
      logError("db-restore", "Cancelado por el usuario");
      process.exit(1);
    }
  }

  // 1) Recrear la BD destino desde cero (evita duplicados de CREATE TABLE).
  const drop = maintenance(`DROP DATABASE IF EXISTS "${target}" WITH (FORCE);`);
  if (!drop.ok) {
    logError("db-restore", `No se pudo soltar ${target}: ${drop.stderr}`);
    process.exit(1);
  }
  const create = maintenance(`CREATE DATABASE "${target}";`);
  if (!create.ok) {
    logError("db-restore", `No se pudo crear ${target}: ${create.stderr}`);
    process.exit(1);
  }
  logInfo("db-restore", `BD "${target}" recreada`);

  // 2) Aplicar el dump por stdin.
  const apply = runPsqlViaStdin(target, payload);
  const applyErr = (apply.stderr ?? Buffer.alloc(0)).toString("utf8").trim();
  if (apply.status !== 0) {
    logError(
      "db-restore",
      `psql falló al restaurar: ${applyErr || "sin detalle"}`,
    );
    writeAgentLog("db-restore", {
      status: "failed",
      file,
      target,
      step: "psql",
    });
    process.exit(1);
  }
  if (applyErr && !/^NOTICE:/m.test(applyErr)) {
    logInfo("db-restore", `psql avisos (no bloqueantes):\n${applyErr}`);
  }
  logInfo("db-restore", `${file} aplicado a "${target}" (${sourceLabel})`);

  // 3) Alinear Alembic a head (023) tras la restauración, si procede.
  //    Crucial: la migración debe ejecutarse contra `target`, NO contra la BD
  //    principal del .env (V2.15-01). Re-escribimos DATABASE_URL al destino.
  if (runAlembic) {
    try {
      const targetUrl = redirectDatabaseUrlTo(target);
      logInfo(
        "db-restore",
        `Alembic → BD "${target}" (destino restaurada, no la principal)`,
      );
      runDbMigrateDeploy({ databaseUrl: targetUrl });
      logInfo("db-restore", `Alembic aplicado a head (023) en "${target}"`);
    } catch (error) {
      logError(
        "db-restore",
        `Restauración OK pero Alembic falló contra "${target}": ${error.message}`,
      );
      writeAgentLog("db-restore", {
        status: "partial",
        file,
        target,
        alembic: "failed",
      });
      process.exit(1);
    }
  }

  logInfo(
    "db-restore",
    `Restauración completa: ${target} ← ${file} ⇢ head 023`,
  );
  writeAgentLog("db-restore", {
    status: "ok",
    file,
    target,
    alembic: runAlembic,
  });
}

await main();
