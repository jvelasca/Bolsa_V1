import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  pgDumpToFile,
  sha256Hex,
  verifyChecksumSidecar,
} from "./lib/backup.mjs";
import {
  clientEnv,
  ensureProjectDatabase,
  findDockerExe,
  psqlBase,
  useTcpTransport,
} from "./lib/docker.mjs";
import { logError, logInfo, writeAgentLog } from "./lib/logger.mjs";

/**
 * pnpm db:dr:test — batería automática de Disaster Recovery (V2.15 C2).
 *
 * Verifica end-to-end que el pipeline de backup/restore es seguro y trazable:
 *  1. vuelca `bolsa_v1` (con sidecar `.sha256` y manifest) a un directorio temporal,
 *  2. comprueba que el checksum del sidecar coincide con el fichero volcado,
 *  3. restaura ese volcado en una BD scratch (`bolsa_v1_dr_test`) invocando el CLI
 *     real `db:restore ... --target-db` (Alembic debe dirigirse a la scratch),
 *  4. verifica que la scratch queda en el mismo head y con esquema SQL consultable,
 *  5. revisa la INTEGRIDAD DE DATOS financiera (C2-02): la scratch debe reproducir
 *     fielmente el snapshot canónico financiero de la principal — por entidad,
 *     `COUNT(*)` y un digest md5 del contenido ordenado (ver FINANCIAL_ENTITIES),
 *  6. verifica que `bolsa_v1` (principal) NO cambia de head durante la operación,
 *  7. limpia la scratch en `finally` y reporta un agregado ok/failed.
 *
 * Local por defecto (contenedor `bolsa-postgres`) y CI por red (BOLSA_DR_TCP).
 * NO ejecutar contra producción.
 * Uso: pnpm db:dr:test   (override del nombre scratch con DR_TARGET_DB)
 *   con transporte RED por TCP (CI): PGHOST/PGPORT/PGUSER/PGPASSWORD o DB_* + BOLSA_DR_TCP=1
 */

const CONTAINER = "bolsa-postgres";
const PG_USER = "bolsa";
const MAIN_DB = "bolsa_v1";

/**
 * Inventario canónico de entidades financieras/operativas cuyo restore debe ser
 * fiel a nivel de DATOS (no solo estructural). FUENTE ÚNICA: el ORM en
 * `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`,
 * línea de `__tablename__` en el comentario ⬅. Coincide con el mapa Fase B de la
 * auditoría C2-02 (`docs/engineering/auditoria-v2-15-1-c2-2026-09-08.md`).
 * Tablas de mercado masivo (ohlcv_bars, data logs…) quedan FUERA: una sola de
 * ellas desbordaría el `string_agg` del digest (riesgo 7b); su cobertura corre a
 * cargo del cheque estructural existente (nº de tablas public) + head.
 */
const FINANCIAL_ENTITIES = [
  { entity: "accounts", table: "investment_accounts" }, // tables.py:1588
  { entity: "ledger", table: "ledger_entries" }, // tables.py:1664
  { entity: "investment_portfolios", table: "investment_portfolios" }, // tables.py:1640
  { entity: "portfolios", table: "portfolios" }, // tables.py:152
  { entity: "transactions", table: "transactions" }, // tables.py:180
  { entity: "positions", table: "positions" }, // tables.py:166
  { entity: "position_states", table: "position_states" }, // tables.py:1107
  { entity: "pending_orders", table: "pending_orders" }, // tables.py:1079
  { entity: "submit_intents", table: "submit_intents" }, // tables.py:1195
  { entity: "live_orders", table: "live_orders" }, // tables.py:1241
  { entity: "execution_events", table: "execution_events" }, // tables.py:1343
  { entity: "operational_incidents", table: "operational_incidents" }, // tables.py:1374
  { entity: "lifecycle_events", table: "lifecycle_events" }, // tables.py:1429
  { entity: "lifecycle_aggregates", table: "lifecycle_aggregates" }, // tables.py:1499
  { entity: "lifecycle_outbox", table: "lifecycle_outbox" }, // tables.py:1514
  { entity: "custody_obligations", table: "custody_obligations" }, // tables.py:1891
  { entity: "decision_journal_entries", table: "decision_journal_entries" }, // tables.py:634
  { entity: "decision_sessions", table: "decision_sessions" }, // tables.py:617
];

function summary(checks) {
  return checks.every((c) => c.ok) ? { status: "ok" } : { status: "failed" };
}

function psqlQuery(db, sql) {
  const base = psqlBase({ db, container: CONTAINER, user: PG_USER });
  if (!useTcpTransport() && !findDockerExe())
    return { ok: false, out: "", err: "no docker" };
  const r = spawnSync(
    base.bin,
    [...base.argv, "-Atc", sql, "-v", "ON_ERROR_STOP=1"],
    {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      env: clientEnv(base),
    },
  );
  return {
    ok: r.status === 0,
    out: (r.stdout ?? "").toString().trim(),
    err: (r.stderr ?? "").toString().trim(),
  };
}

function readRevision(db) {
  const q = psqlQuery(db, "SELECT version_num FROM alembic_version LIMIT 1;");
  return q.ok && q.out ? q.out : null;
}

function countPublicTables(db) {
  const q = psqlQuery(
    db,
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';",
  );
  return q.ok ? Number.parseInt(q.out || "0", 10) : 0;
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

/**
 * Digest canónico determinista de UNA tabla financiera. Devuelve { ok, count, digest }.
 * SQL (una sola pasada):
 *   - `count(*)`: filas de la tabla.
 *   - `md5(string_agg(fila::text, '\n' ORDER BY fila::text))`: proyecta cada fila
 *     a su texto canónico (jsonb sale en su forma canónica, los timestamptz en la
 *     TZ de sesión — CONSTANTE entre las lecturas BEFORE/AFTER de este mismo run,
 *     que es el único requisito de estabilidad) y las agrupa ordenadas. El digest es
 *     independiente del ORDEN físico de filas, detecciona filas perdidas/añadidas y
 *     alteraciones de contenido (no es un SUM: no hay cancelación simétrica).
 *
 * Sobre el hash (md5 en vez de SHA-256): `sha256(...)`/`encode(...,'hex')` viven en
 * la extensión opcional `pgcrypto`, que PostgreSQL 16 NO instala por defecto en el
 * restore a scratch → usarla rompería la batería sin pre-requisito. `md5(text)` es
 * BUILT-IN en core y basta para un guard de INTEGRIDAD DE RESTORE no-adversarial
 * (filas perdidas/alteradas): el riesgo de colisión sobre todo el contenido canónico
 * de tablas financieras reales es despreciable y no estamos frente a un adversary
 * (las afirmaciones de falsificación se cubren con el sidecar SHA-256 del dump en
 * Node — `sha256Hex`/`verifyChecksumSidecar`).
 *
 * Límites justificados:
 *   - `string_agg` materializa todo el contenido en memoria del servidor: solo es
 *     seguro porque FINANCIAL_ENTITIES excluye tablas de mercado masivo (las tablas
 *     financieras son de volumen contenido). Si una entidad futura creciera sin
 *     límite habría que pasar a hashear por bloques.
 *   - `fila::text` incluye TODAS las columnas (sin enumeración manual → robusto a
 *     migraciones que añadan columnas); el PK único hace que dos filas distintas
 *     nunca rindan el mismo texto.
 * Readonly: no usa FOR UPDATE; el `count` y el `string_agg` del mismo query se leen
 * bajo la misma snapshot de lectura → coherentes entre dos SELECT encadenados.
 */
function readTableFingerprint(db, entry) {
  const q = psqlQuery(
    db,
    `SELECT (SELECT count(*) FROM "${entry.table}"), COALESCE(md5(w.q), '') FROM ` +
      `(SELECT string_agg(r.rowtxt, E'\\n' ORDER BY r.rowtxt) AS q FROM ` +
      `(SELECT t::text AS rowtxt FROM "${entry.table}" t) r) w;`,
  );
  if (!q.ok) {
    return { ok: false, entity: entry.entity, table: entry.table, err: q.err };
  }
  // Formato -At: una línea "N<TAB>digest"; si no cae en el patrón, digest = ''.
  const m = /^(\d+)[	 ]+(.*)$/.exec(q.out);
  return {
    ok: true,
    entity: entry.entity,
    table: entry.table,
    count: m ? Number.parseInt(m[1], 10) : 0,
    digest: m ? m[2] : "",
  };
}

/**
 * Snapshot financiero canónico de una BD: row-count + digest por entidad, en el
 * ORDEN fijo de FINANCIAL_ENTITIES (determinista). Devuelve { ok, counts, rows }.
 * Si una tabla falla de lectura (p. ej. no existe en la scratch) → ok=false y el
 * cheque de comparación lo marcará como FAIL explícito (riesgo 7a).
 */
function financialSnapshot(db) {
  const rows = [];
  for (const entry of FINANCIAL_ENTITIES) {
    const f = readTableFingerprint(db, entry);
    if (!f.ok)
      return {
        ok: false,
        rows,
        error: `${entry.entity} (${entry.table}): ${f.err}`,
      };
    rows.push({ entity: entry.entity, count: f.count, digest: f.digest });
  }
  return { ok: true, rows };
}

async function main() {
  let docker = findDockerExe();
  const checks = [];
  const targetDB = process.env.DR_TARGET_DB ?? "bolsa_v1_dr_test";
  let tmpDir = null;
  let dumpFile = null;

  try {
    const tcp = useTcpTransport();
    if (tcp) {
      // Modo CI/red: PostgreSQL alcanzable por TCP con psql/pg_dump de host
      // (BOLSA_DR_TCP=1) — nunca tocar Docker ni el contenedor del proyecto.
      logInfo(
        "db-dr-verify",
        `Batería DR por red (BOLSA_DR_TCP), scratch="${targetDB}"`,
      );
    } else {
      if (!docker) throw new Error("Docker CLI no disponible");
      // Asegurar Docker + PostgreSQL del proyecto (auto-arranque como db:dump).
      if (!(await ensureProjectDatabase()).ok) {
        logError("db-dr-verify", "No se pudo asegurar Docker/PostgreSQL");
      }
      docker = findDockerExe();
      logInfo(
        "db-dr-verify",
        `Batería DR sobre contenedor, scratch="${targetDB}"`,
      );
    }

    // Snapshot del estado de la BD principal ANTES.
    const mainHeadBefore = readRevision(MAIN_DB);
    if (!mainHeadBefore)
      throw new Error("No se pudo leer el head de bolsa_v1 (¿migrado?)");
    logInfo("db-dr-verify", `head principal (antes): ${mainHeadBefore}`);

    // (1) Volcado temporal + sidecar/manifest.
    tmpDir = mkdtempSync(join(tmpdir(), "bolsa-dr-"));
    const dumped = pgDumpToFile({ dir: tmpDir, gzip: false, db: MAIN_DB });
    dumpFile = dumped.file;
    const freshSha = sha256Hex(readFileSync(dumpFile));
    checks.push(
      freshSha === dumped.sha256
        ? {
            ok: true,
            name: "dump-hash-calculado-coincide",
            detail: dumped.sha256,
          }
        : {
            ok: false,
            name: "dump-integrity",
            detail: "sha interno no coincide",
          },
    );

    // (2) Checksum del sidecar verificado.
    const side = verifyChecksumSidecar(dumpFile);
    checks.push(
      side.ok
        ? { ok: true, name: "sidecar-checksum", detail: side.code }
        : { ok: false, name: "sidecar-checksum", detail: side.code },
    );

    // (2b) Snapshot financiero canónico ANTES, sobre la BD PRINCIPAL (nunca de la
    // scratch). Se reutiliza tal cual para comparar tras el restore (C2-02).
    let beforeSnap;
    try {
      beforeSnap = financialSnapshot(MAIN_DB);
      if (!beforeSnap.ok) throw new Error(beforeSnap.error);
      const counts = beforeSnap.rows
        .map((r) => `${r.entity}=${r.count}`)
        .join(" ");
      logInfo("db-dr-verify", `snapshot financiero (antes): ${counts}`);
    } catch (err) {
      throw new Error(
        `No se pudo computar snapshot financiero de la principal: ${err.message}`,
      );
    }

    // (3a) Garantizar scratch limpia antes del restore.
    const dropMaintenance = maintenance(
      `DROP DATABASE IF EXISTS "${targetDB}" WITH (FORCE);`,
    );
    if (!dropMaintenance.ok) {
      throw new Error(
        `No se pudo limpiar scratch ${targetDB}: ${dropMaintenance.stderr}`,
      );
    }

    // (3b) Invocamos el CLI real con --target-db → el restore + Alembic va a la scratch.
    logInfo(
      "db-dr-verify",
      `Restaurando volcado en "${targetDB}" (Alembic dirigido a scratch)...`,
    );
    const restore = spawnSync(
      process.execPath,
      [
        "scripts/db-restore.mjs",
        "--file",
        dumpFile,
        "--target-db",
        targetDB,
        "--yes",
      ],
      { encoding: "utf8", stdio: ["inherit"] },
    );
    checks.push(
      restore.status === 0
        ? { ok: true, name: "db-restore-cli-exit0" }
        : {
            ok: false,
            name: "db-restore-cli-exit",
            detail: `exit=${restore.status}`,
          },
    );

    // (4) La scratch quedó al head y con esquema consultable.
    const scratchRev = readRevision(targetDB);
    checks.push(
      scratchRev === mainHeadBefore
        ? { ok: true, name: "scratch-al-alineado-head", detail: scratchRev }
        : {
            ok: false,
            name: "scratch-head",
            detail: `${scratchRev} vs esperado ${mainHeadBefore}`,
          },
    );
    const scratchTables = countPublicTables(targetDB);
    checks.push(
      scratchTables > 0
        ? {
            ok: true,
            name: "scratch-esquema-consultable",
            detail: `${scratchTables} tablas public`,
          }
        : {
            ok: false,
            name: "scratch-esquema",
            detail: "0 tablas public (restore vacío?)",
          },
    );

    // (4b) Snapshot financiero canónico DESPUÉS sobre la scratch y comparación contra
    // el snapshot ANTES de la principal (por entidad + digest). Varios FAILs son
    // intencionales (legibilidad): uno global que rompe de inmediato si la scratch
    // no es capaz siquiera de negarse a ser consultada (tabla inexistente, 7a).
    let afterSnap;
    try {
      afterSnap = financialSnapshot(targetDB);
    } catch (err) {
      afterSnap = { ok: false, error: String(err.message ?? err) };
    }
    checks.push(
      afterSnap.ok
        ? { ok: true, name: "dr-snapshot-financiero-leido" }
        : {
            ok: false,
            name: "dr-snapshot-financiero-leido",
            detail: `no se pudo leer snapshot de ${targetDB}: ${afterSnap.error ?? ""}`,
          },
    );
    if (afterSnap.ok) {
      const diffs = [];
      for (const a of afterSnap.rows) {
        const b = beforeSnap.rows.find((r) => r.entity === a.entity);
        if (!b) {
          diffs.push(`entidad ${a.entity} no estaba en el snapshot ANTES`);
          continue;
        }
        if (a.count !== b.count) {
          diffs.push(
            `${a.entity}: COUNT ${b.count} vs ${a.count} (tras restore en scratch)`,
          );
        } else if (a.digest !== b.digest) {
          diffs.push(
            `${a.entity}: contenido alterado (${a.count} filas en ambas, digest distinto)`,
          );
        }
      }
      checks.push(
        diffs.length === 0
          ? {
              ok: true,
              name: "dr-datos-financieros-integridad",
              detail: "COUNT y digest md5 idénticos en scratch",
            }
          : {
              ok: false,
              name: "dr-datos-financieros-integridad",
              detail: diffs.join("; "),
            },
      );
    } else {
      checks.push({
        ok: false,
        name: "dr-datos-financieros-integridad",
        detail: afterSnap.error ?? "snapshot AFTER no disponible",
      });
    }

    // (5) La BD principal NO cambió de head.
    const mainHeadAfter = readRevision(MAIN_DB);
    checks.push(
      mainHeadAfter === mainHeadBefore
        ? { ok: true, name: "principal-intacta", detail: mainHeadAfter }
        : {
            ok: false,
            name: "principal-cambiada",
            detail: `${mainHeadAfter} vs ${mainHeadBefore}`,
          },
    );

    const verdict = summary(checks);
    for (const c of checks) {
      logInfo(
        "db-dr-verify",
        `${c.ok ? "PASS" : "FAIL"} · ${c.name} · ${c.detail ?? ""}`,
      );
    }
    logInfo(
      "db-dr-verify",
      `Resultado agregado: ${verdict.status} (scratch="${targetDB}")`,
    );
    writeAgentLog("db-dr-verify", { status: verdict.status, targetDB, checks });
    if (verdict.status === "failed") {
      process.exitCode = 1;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logError("db-dr-verify", message);
    writeAgentLog("db-dr-verify", { status: "failed", error: message });
    process.exitCode = 1;
  } finally {
    // (6) Limpieza de la scratch y del dump temporal, independientemente del resultado.
    if (targetDB !== MAIN_DB) {
      const rm = maintenance(
        `DROP DATABASE IF EXISTS "${targetDB}" WITH (FORCE);`,
      );
      if (!rm.ok) {
        logError(
          "db-dr-verify",
          `No se pudo limpiar scratch ${targetDB}: ${rm.stderr}`,
        );
      } else {
        logInfo("db-dr-verify", `Scratch "${targetDB}" eliminada`);
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
