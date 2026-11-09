import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Paridad del cliente API con el contrato OpenAPI (Fase 3.4, auditoría externa).
 *
 * `api.ts` ya usa `openapi-fetch` tipado con `paths` de `schema.d.ts`, así que un path
 * inexistente normalmente lo detecta `tsc`. Este test añade una guarda ejecutable que
 * cubre los huecos que el tipo no ve:
 *
 * 1. Una llamada con path **no literal** (variable, plantilla) escapa al chequeo de
 *    tipos y a este test; se falla explícitamente para que la extracción no sea ciega.
 * 2. Un path/método usado en `api.ts` debe existir en `api/openapi.json` — si el
 *    contrato pierde un endpoint que la web sigue llamando, se ve aquí y no en runtime.
 * 3. El path debe estar también en `src/api/schema.d.ts`, que es lo que consume
 *    `openapi-fetch`; detecta una regeneración parcial del contrato.
 */

type HttpMethod = "get" | "post" | "put" | "patch" | "delete";

interface ApiCall {
  method: HttpMethod;
  path: string;
  line: number;
}

const WEB_ROOT = process.cwd();
const API_TS = resolve(WEB_ROOT, "src/lib/api.ts");
const OPENAPI_JSON = resolve(WEB_ROOT, "api/openapi.json");
const SCHEMA_D_TS = resolve(WEB_ROOT, "src/api/schema.d.ts");

const CALL_START = /client\.(GET|POST|PUT|PATCH|DELETE)\s*\(/g;
const CALL_LITERAL = /client\.(GET|POST|PUT|PATCH|DELETE)\(\s*"([^"]+)"/g;

function lineAt(source: string, index: number): number {
  let line = 1;
  for (let i = 0; i < index; i += 1) {
    if (source[i] === "\n") line += 1;
  }
  return line;
}

function readCalls(): {
  calls: ApiCall[];
  starts: number;
} {
  const source = readFileSync(API_TS, "utf8");
  const starts = [...source.matchAll(CALL_START)].length;
  const calls = [...source.matchAll(CALL_LITERAL)].map((match) => ({
    method: match[1].toLowerCase() as HttpMethod,
    path: match[2],
    line: lineAt(source, match.index ?? 0),
  }));
  return { calls, starts };
}

function openapiPaths(): Record<string, Record<string, unknown>> {
  const spec = JSON.parse(readFileSync(OPENAPI_JSON, "utf8")) as {
    paths?: Record<string, Record<string, unknown>>;
  };
  return spec.paths ?? {};
}

function schemaPathKeys(): Set<string> {
  const source = readFileSync(SCHEMA_D_TS, "utf8");
  const keys = new Set<string>();
  for (const match of source.matchAll(/^\s{4}"([^"]+)":\s*\{/gm)) {
    keys.add(match[1]);
  }
  return keys;
}

describe("paridad api.ts ↔ contrato OpenAPI", () => {
  it("extrae todas las llamadas con path literal", () => {
    const { calls, starts } = readCalls();
    expect(calls.length).toBeGreaterThan(0);
    // Igualdad estricta: una llamada nueva con path calculado rompe la guarda y debe
    // resolverse con un literal (o ampliar el test de forma consciente).
    expect(
      calls.length,
      "Hay llamadas a client.* con path no literal; la paridad de paths no puede verificarlas.",
    ).toBe(starts);
  });

  it("cada path usado existe en openapi.json con su método", () => {
    const { calls } = readCalls();
    const paths = openapiPaths();
    const missing = calls
      .filter(({ method, path }) => paths[path]?.[method] === undefined)
      .map(({ method, path, line }) => {
        const knownPath = paths[path] ? "path sí, método no" : "path ausente";
        return `api.ts:${line} ${method.toUpperCase()} ${path} (${knownPath})`;
      });
    expect(
      [...new Set(missing)],
      "Endpoints usados por api.ts que no existen en api/openapi.json",
    ).toEqual([]);
  });

  it("cada path usado está declarado en schema.d.ts", () => {
    const { calls } = readCalls();
    const keys = schemaPathKeys();
    const missing = calls
      .filter(({ path }) => !keys.has(path))
      .map(
        ({ method, path, line }) =>
          `api.ts:${line} ${method.toUpperCase()} ${path}`,
      );
    expect(
      [...new Set(missing)],
      "Endpoints usados por api.ts que no están en src/api/schema.d.ts",
    ).toEqual([]);
  });
});
