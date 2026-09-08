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
 * V2.15.5: con el digest POR BLOQUES (memoria acotada) las tablas masivas de
 * mercado ya NO quedan excluidas por desborde del digest; se auditan aparte en
 * `MARKET_ENTITIES` (ohlcv_bars = fuente de verdad del mercado).
 */
const FINANCIAL_ENTITIES = [
  { scope: "financial", entity: "accounts", table: "investment_accounts" }, // tables.py:1588
  { scope: "financial", entity: "ledger", table: "ledger_entries" }, // tables.py:1664
  { scope: "financial", entity: "investment_portfolios", table: "investment_portfolios" }, // tables.py:1640
  { scope: "financial", entity: "portfolios", table: "portfolios" }, // tables.py:152
  { scope: "financial", entity: "transactions", table: "transactions" }, // tables.py:180
  { scope: "financial", entity: "positions", table: "positions" }, // tables.py:166
  { scope: "financial", entity: "position_states", table: "position_states" }, // tables.py:1107
  { scope: "financial", entity: "pending_orders", table: "pending_orders" }, // tables.py:1079
  { scope: "financial", entity: "submit_intents", table: "submit_intents" }, // tables.py:1195
  { scope: "financial", entity: "live_orders", table: "live_orders" }, // tables.py:1241
  { scope: "financial", entity: "execution_events", table: "execution_events" }, // tables.py:1343
  { scope: "financial", entity: "operational_incidents", table: "operational_incidents" }, // tables.py:1374
  { scope: "financial", entity: "lifecycle_events", table: "lifecycle_events" }, // tables.py:1429
  { scope: "financial", entity: "lifecycle_aggregates", table: "lifecycle_aggregates" }, // tables.py:1499
  { scope: "financial", entity: "lifecycle_outbox", table: "lifecycle_outbox" }, // tables.py:1514
  { scope: "financial", entity: "custody_obligations", table: "custody_obligations" }, // tables.py:1891
  { scope: "financial", entity: "decision_journal_entries", table: "decision_journal_entries" }, // tables.py:634
  { scope: "financial", entity: "decision_sessions", table: "decision_sessions" }, // tables.py:617
];

/**
 * Datos de MERCADO cuya fidelidad de restore también se audita (V2.15.5):
 * la FUENTE DE VERDAD OHLCV (`ohlcv_bars`, la tabla más masiva del esquema,
 * decenas de miles de filas) quedaba excluida por el riesgo de `string_agg`
 * completo (riesgo 7b). Con el digest POR BLOQUES ya puede incluirse.
 * `instruments` (catálogo IBEX) y `data_sync_log` (logs de sync) se añaden como
 * vecinos del mismo universo de mercado para cobertura cercana.
 */
const MARKET_ENTITIES = [
  { scope: "market", entity: "instruments", table: "instruments" }, // tables.py:66
  { scope: "market", entity: "ohlcv_bars", table: "ohlcv_bars" }, // tables.py:107
  { scope: "market", entity: "data_sync_log", table: "data_sync_log" }, // tables.py:138
];

/** Inventario de cobertura de datos completo y determinista (financiero + mercado). */
const ALL_ENTITIES = [...FINANCIAL_ENTITIES, ...MARKET_ENTITIES];

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
 * V2.15.5 — MODO INDUSTRIAL (snapshot atómico + digest por bloques).
 *
 * Dos garantías que la batería previa NO daba:
 *
 *  1) SNAPSHOT ATÓMICO `REPEATABLE READ`. Antes se leía cada tabla con un psql
 *     independiente (connection/transacción por tabla) → la imagen podía mezclar
 *     estados distintos (tabla A leída en t₀, tabla B en t₁; con escritura a
 *     media batalla el "antes" no era una foto consistente y, peor, podía dar
 *     falsos positivos).
 *     Ahora TODAS las tablas (financieras + OHLCV) se leen dentro de UNA ÚNICA
 *     transacción `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` enviada por
 *     stdin a un solo psql. REPEATABLE READ congela la snapshot al principio de
 *     la transacción → todo el `count`+digest de la carrera refleja el mismo
 *     estado commitado de la BD (imagen consistente), no varias.
 *
 *  2) DIGEST INCREMENTAL / POR BLOQUES. El `md5(string_agg(fila::text,…))`
 *     materializaba el contenido ENTERO de la tabla en un único agregado
 *     (memoria O(N), riesgo de desborde con catálogos masivos → motivo por el que
 *     OHLCV quedaba excluido). Ahora cada tabla se ordena de forma estable
 *     (`rowtxt` canónico) y se parte en BLOQUES fijos (CHUNK_SIZE filas); por
 *     bloque se calcula `md5(string_agg(bloque))`, y el digest total es
 *     `md5(concat(bloque_digests en orden))`. Memoria acotada por bloque; el
 *     resultado es determinista → idéntico contenido ⇒ idéntico digest, y una
 *     fila perdida/alterada/añadida cambia el digest (no es un SUM: sin
 *     cancelación). Esto permite incluir `ohlcv_bars` (fuente de verdad de
 *     mercado, decenas de miles de filas) en la cobertura.
 *
 * md5 (no SHA-256): es BUILT-IN en core PostgreSQL; la alternativa en la
 * extensión opcional `pgcrypto` (no instalada en el restore a scratch de PG16).
 * Guard NO-adversarial; la falsificación se cubre con el sidecar SHA-256 del dump
 * en Node (`sha256Hex`). No usa FOR UPDATE (read-only).
 */
const CHUNK_SIZE = 5000;
const LABEL_SENTINEL = "BOLSA_DR_TABLE";

/** SQL de una sola línea de digest atomico por tabla (label|count|digest). */
function tableDigestSql(table, chunkSize = CHUNK_SIZE) {
  const ident = `"${table}"`;
  return (
    `WITH ord AS (` +
    `SELECT _t::text AS r, (row_number() OVER (ORDER BY _t::text) - 1) AS pos ` +
    `FROM ${ident} _t), ` +
    `grp AS (` +
    `SELECT pos / ${chunkSize} AS chunk, ` +
    `md5(string_agg(r, E'\\n' ORDER BY r)) AS cd ` +
    `FROM ord GROUP BY pos / ${chunkSize}), ` +
    `fin AS (` +
    `SELECT (SELECT count(*) FROM ${ident}) AS n, ` +
    `COALESCE(md5(string_agg(cd, '' ORDER BY chunk)), '') AS d ` +
    `FROM grp) ` +
    `SELECT '${LABEL_SENTINEL}|' || n::text || '|' || d FROM fin;`
  );
}

/**
 * Ejecuta un script SQL (multi-sentencia) por STDIN en UNA sesión psql contra
 * `db`. Devuelve { ok, out, err }. Compatible con transporte Docker y TCP (CI).
 */
function psqlScript(db, sql) {
  const base = psqlBase({
    db,
    container: CONTAINER,
    user: PG_USER,
    interactive: true, // en transporte docker añade `-i` para reenviar STDIN
  });
  const r = spawnSync(
    base.bin,
    [...base.argv, "-v", "ON_ERROR_STOP=1", "-A", "-t", "-q"],
    {
      input: sql,
      encoding: "utf8",
      // -c no; leemos el resto desde stdin. stdout pequeña (una línea por tabla).
      stdio: ["pipe", "pipe", "pipe"],
      env: clientEnv(base),
    },
  );
  return {
    ok: r.status === 0,
    out: (r.stdout ?? "").toString(),
    err: (r.stderr ?? "").toString().trim(),
  };
}

/**
 * Snapshot canónico ATÓMICO de un conjunto de tablas: count + digest por bloque
 * para cada entidad, todo bajo UNA transacción REPEATABLE READ. El orden de
 * visualización es el de `entries` (determinista). Devuelve { ok, rows, error }.
 * rows: [{ scope, entity, table, count, digest }].
 */
function atomicCoverageSnapshot(db, entries) {
  const statements = [`BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;`];
  for (const entry of entries) {
    statements.push(tableDigestSql(entry.table));
  }
  statements.push("COMMIT;");
  const script = statements.join("\n");
  const raw = psqlScript(db, script);
  if (!raw.ok) {
    // Si falla (p. ej. tabla inexistente en la scratch) devolvemos rows parseables
    // hasta el fallo + error: el comparador lo marcará como FAIL explícito (7a).
    const rows = parseTableLines(raw.out, entries);
    if (rows.length > 0)
      return { ok: false, error: raw.err || "fallo de lectura", rows };
    return { ok: false, error: raw.err || "fallo de lectura", rows: [] };
  }
  const rows = parseTableLines(raw.out, entries);
  if (rows.length !== entries.length) {
    return {
      ok: false,
      rows,
      error: `se esperaban ${entries.length} filas de digest, se leyeron ${rows.length}`,
    };
  }
  return { ok: true, rows };
}

/**
 * Parsea la salida psql -A -t de `atomicCoverageSnapshot` (una línea
 * "@SENTINEL|count|digest" por fila) alineándola con `entries` por posición.
 */
function parseTableLines(out, entries) {
  const lines = out
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.startsWith(`${LABEL_SENTINEL}|`));
  return lines.map((line, i) => {
    const seg = line.split("|");
    const entry = entries[i] ?? { scope: "?", entity: "?", table: "?" };
    const countStr = seg[1] ?? "0";
    return {
      scope: entry.scope,
      entity: entry.entity,
      table: entry.table,
      count: /^\d+$/.test(countStr) ? Number.parseInt(countStr, 10) : 0,
      digest: seg.slice(2).join("|"), // el digest md5 es hex (sin '|' interno)
    };
  });
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

    // (2b) Snapshot canónico ATÓMICO ANTES (repeatable-read de COBERTURA completa,
    // financiero + mercado) sobre la BD PRINCIPAL. Se reutiliza tal cual para
    // comparar tras el restore (C2-02). La single-transaction garantiza que el
    // count y el digest de CADA tabla ven el MISMO estado commitado de la BD.
    let beforeSnap;
    try {
      beforeSnap = atomicCoverageSnapshot(MAIN_DB, ALL_ENTITIES);
      if (!beforeSnap.ok) throw new Error(beforeSnap.error);
      const finCounts = beforeSnap.rows.filter((r) => r.scope === "financial")
        .map((r) => `${r.entity}=${r.count}`)
        .join(" ");
      const mktCounts = beforeSnap.rows.filter((r) => r.scope === "market")
        .map((r) => `${r.entity}=${r.count}`)
        .join(" ");
      logInfo("db-dr-verify", `snapshot financiero (antes): ${finCounts}`);
      logInfo("db-dr-verify", `snapshot mercado (antes): ${mktCounts}`);
    } catch (err) {
      throw new Error(
        `No se pudo computar snapshot de la principal: ${err.message}`,
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
    const t0Restore = Date.now();
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
    const rtoMs = Date.now() - t0Restore;
    checks.push(
      restore.status === 0
        ? { ok: true, name: "db-restore-cli-exit0" }
        : {
            ok: false,
            name: "db-restore-cli-exit",
            detail: `exit=${restore.status}`,
          },
    );
    checks.push({
      ok: true,
      name: "rto-observado",
      detail: `${rtoMs} ms (restore a scratch en el mismo server, no aislado)`,
    });

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

    // (4b) Snapshot canónico ATÓMICO DESPUÉS sobre la scratch y comparación contra
    // el snapshot ANTES de la principal (por entidad + digest, y por scope).
    // Varios FAILs son intencionales (legibilidad): uno global que rompe de
    // inmediato si la scratch no es capaz siquiera de ser consultada (7a).
    let afterSnap;
    try {
      afterSnap = atomicCoverageSnapshot(targetDB, ALL_ENTITIES);
    } catch (err) {
      afterSnap = { ok: false, error: String(err.message ?? err) };
    }
    checks.push(
      afterSnap.ok
        ? { ok: true, name: "dr-snapshot-datos-leido" }
        : {
            ok: false,
            name: "dr-snapshot-datos-leido",
            detail: `no se pudo leer snapshot de ${targetDB}: ${afterSnap.error ?? ""}`,
          },
    );
    if (afterSnap.ok) {
      const diffs = [];
      for (const a of afterSnap.rows) {
        const b = beforeSnap.rows.find(
          (r) => r.entity === a.entity && r.scope === a.scope,
        );
        if (!b) {
          diffs.push(`entidad ${a.scope}/${a.entity} no estaba en el ANTES`);
          continue;
        }
        if (a.count !== b.count) {
          diffs.push(
            `${a.scope}/${a.entity}: COUNT ${b.count} vs ${a.count} (tras restore)`,
          );
        } else if (a.digest !== b.digest) {
          diffs.push(
            `${a.scope}/${a.entity}: contenido alterado (${a.count} filas en ambas, digest distinto)`,
          );
        }
      }
      checks.push(
        diffs.length === 0
          ? {
              ok: true,
              name: "dr-datos-integridad",
              detail:
                "COUNT y digest md5 (por bloques) idénticos en scratch · financieras + mercado",
            }
          : {
              ok: false,
              name: "dr-datos-integridad",
              detail: diffs.join("; "),
            },
      );
    } else {
      checks.push({
        ok: false,
        name: "dr-datos-integridad",
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
      { status: verdict.status, targetDB },
    );
    const coverageSummary = (beforeSnap?.rows ?? []).map((r) => ({
      scope: r.scope,
      entity: r.entity,
      count: r.count,
    }));
    writeAgentLog("db-dr-verify", {
      status: verdict.status,
      targetDB,
      rtoObservedMs: rtoMs,
      coverageAtomicRepeatableRead: true,
      digestMode: "block-md5",
      chunkSize: CHUNK_SIZE,
      financialEntities: FINANCIAL_ENTITIES.length,
      marketEntities: MARKET_ENTITIES.length,
      coverage: coverageSummary,
      checks,
    });
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
