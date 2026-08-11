#!/usr/bin/env node
/**
 * F5a — contrato FE/BE. Sincroniza el contrato OpenAPI con FastAPI y regenera
 * los tipos TS (`openapi-typescript`).
 *
 *   node scripts/sync-contract.mjs          # genera (dump + schema.d.ts) en sitio
 *   node scripts/sync-contract.mjs --check  # verifica que NO hay diff (gate CI)
 *
 * Fuente de verdad: FastAPI (Pydantic) → apps/web/api/openapi.json → schema.d.ts.
 * El dump requiere el venv Python de `apps/api-python` (uv). Si no hay uv, el
 * modo `--check` no puede validar contra FastAPI y termina en verde con aviso.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const WEB = path.resolve(fileURLToPath(new URL("..", import.meta.url))); // .../apps/web
const ROOT = path.resolve(WEB, "../..");
const APP_PY = path.join(ROOT, "apps", "api-python");
const SPEC = path.join(WEB, "api", "openapi.json");
const SCHEMA = path.join(WEB, "src", "api", "schema.d.ts");

const isCheck = process.argv.includes("--check");

function hasUv() {
  try {
    execFileSync("uv", ["--version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

/** Vuelca openapi.json desde FastAPI (offline, sin servir). */
function dumpSpec() {
  execFileSync(
    "uv",
    ["run", "--project", APP_PY, "python", "apps/api-python/scripts/dump_openapi.py"],
    { cwd: ROOT, stdio: isCheck ? "pipe" : "inherit", encoding: "utf-8" },
  );
}

/** Regenera schema.d.ts desde openapi.json con openapi-typescript. */
function genSchema() {
  if (!existsSync(SPEC)) {
    throw new Error(`no existe ${SPEC}; ejecuta primero contract:gen con el venv Python`);
  }
  execFileSync(
    process.execPath,
    [path.join(WEB, "node_modules", "openapi-typescript", "bin", "cli.js"), SPEC, "--output", SCHEMA],
    { cwd: WEB, stdio: isCheck ? "pipe" : "inherit", encoding: "utf-8" },
  );
}

function snapshot() {
  return {
    spec: existsSync(SPEC) ? readFileSync(SPEC) : null,
    schema: existsSync(SCHEMA) ? readFileSync(SCHEMA) : null,
  };
}

/** Compara ignorando el final de línea (CRLF vs LF), que Git normaliza a LF. */
function sameText(a, b) {
  if (!a || !b) return false;
  const norm = (buf) => buf.toString("utf8").replace(/\r\n/g, "\n");
  return norm(a) === norm(b);
}

function main() {
  try {
    if (isCheck) {
      if (!hasUv()) {
        console.log("contract:check — aviso: uv no disponible; se omite la validación contra FastAPI.");
        return 0;
      }
      const before = snapshot();
      dumpSpec();
      genSchema();
      const specChanged = !sameText(before.spec, readFileSync(SPEC));
      const schemaChanged = !sameText(before.schema, readFileSync(SCHEMA));
      if (specChanged || schemaChanged) {
        console.error(
          "contract:check — el contrato ha cambiado. Ejecuta `pnpm --filter @bolsa/web contract:gen` y commitéalo.",
        );
        return 1;
      }
      console.log("contract:check OK — openapi.json y schema.d.ts coinciden con el commit.");
      return 0;
    }
    dumpSpec();
    genSchema();
    console.log("contract:gen OK — openapi.json + schema.d.ts regenerados en apps/web/");
    return 0;
  } catch (err) {
    console.error(`contract:${isCheck ? "check" : "gen"} — ${err instanceof Error ? err.message : String(err)}`);
    return 1;
  }
}

process.exit(main());
