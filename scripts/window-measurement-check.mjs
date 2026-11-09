#!/usr/bin/env node
/**
 * Validador READ-ONLY de la medicion PAPER de un dia de ventana.
 *
 * Que hace
 * --------
 * Contrasta los artefactos durables de una corrida (`manifest.json`,
 * `forward-market-<day>.json`, certificacion y export de ciclos) con el arbol
 * sellado (`git rev-parse <tag>^{}:apps|packages` frente al pin de `WINDOW_CONFIG`)
 * y emite un dictamen: `GREEN` / `INCONCLUSIVE` / `PREMATURE_TERMINATION` /
 * `INVALID`.
 *
 * Que NO hace
 * -----------
 * * **No ejecuta la ventana** ni escribe en PostgreSQL, journal, pin ni artefactos.
 * * **No sustituye** la corrida real: solo LEE material durable ya existente.
 * * **No rellena huecos con 0**: lo que el artefacto no declara es `UNKNOWN`.
 *
 * Vive en `scripts/`, que NO participa del freeze (`HEAD:apps`/`HEAD:packages`).
 *
 * Uso (desde la raiz del repo):
 *   node scripts/window-measurement-check.mjs --day 20261109
 *   node scripts/window-measurement-check.mjs --day 20261109 --expected-ticks 400 --json
 *   node scripts/window-measurement-check.mjs --day 20261106 --blind-ticks 263
 *   node scripts/window-measurement-check.mjs --day 20261105 --historical
 *
 * `--historical` audita una corrida anterior al sello: la discrepancia de arbol se
 * declara WARN y NO se exige el arbol sellado. Un dictamen `GREEN` obtenido asi no
 * certifica el tag actual.
 *
 * Codigos de salida:
 *   0  dictamen emitido (aunque sea INCONCLUSIVE o PREMATURE_TERMINATION);
 *   1  invariante duro roto (TREE_MOVED, corrida no congelada, umbral rebajado,
 *      sello ausente) o uso incorrecto;
 *   2  material ilegible o inexistente (no se puede emitir dictamen).
 */
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, join } from "node:path";

import { ROOT } from "./lib/logger.mjs";
import { WINDOW_CONFIG } from "./lib/window-forward.mjs";
import {
  VERDICT,
  evaluateMeasurement,
  summarizeChecks,
} from "./lib/window-measurement-check.mjs";

const DEFAULT_TAG = "v2.88.186-beta";
const DEFAULT_RUNS = join(ROOT, "operability_runs");

function parseArgs(argv) {
  const flags = {
    day: null,
    expectedTicks: 400,
    tag: DEFAULT_TAG,
    runs: DEFAULT_RUNS,
    cert: null,
    cycles: null,
    blindTicks: null,
    coverageStart: null,
    coverageMidnight: null,
    historical: false,
    json: false,
  };
  const need = (index, name) => {
    const value = argv[index];
    if (value === undefined) throw new Error(`falta el valor de ${name}`);
    return value;
  };
  const number = (raw, name) => {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed))
      throw new Error(`${name} no es un numero: ${raw}`);
    return parsed;
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const [name, inline] = arg.includes("=")
      ? [arg.slice(0, arg.indexOf("=")), arg.slice(arg.indexOf("=") + 1)]
      : [arg, null];
    const value = (flagName) => {
      if (inline !== null) return inline;
      const next = need(i + 1, flagName);
      i += 1;
      return next;
    };
    if (name === "--day") flags.day = value("--day");
    else if (name === "--expected-ticks")
      flags.expectedTicks = number(
        value("--expected-ticks"),
        "--expected-ticks",
      );
    else if (name === "--tag") flags.tag = value("--tag");
    else if (name === "--runs") flags.runs = value("--runs");
    else if (name === "--cert") flags.cert = value("--cert");
    else if (name === "--cycles") flags.cycles = value("--cycles");
    else if (name === "--blind-ticks")
      flags.blindTicks = number(value("--blind-ticks"), "--blind-ticks");
    else if (name === "--coverage-start")
      flags.coverageStart = number(
        value("--coverage-start"),
        "--coverage-start",
      );
    else if (name === "--coverage-midnight") {
      flags.coverageMidnight = number(
        value("--coverage-midnight"),
        "--coverage-midnight",
      );
    } else if (name === "--historical") flags.historical = true;
    else if (name === "--json") flags.json = true;
    else throw new Error(`argumento no reconocido: ${arg}`);
  }
  return flags;
}

function resolvePath(target) {
  return isAbsolute(target) ? target : join(ROOT, target);
}

/**
 * @param {string} file
 * @returns {{ value: any | null, missing: boolean, empty: boolean }}
 */
function readJson(file) {
  if (!existsSync(file)) return { value: null, missing: true, empty: false };
  const raw = readFileSync(file, "utf8");
  if (!raw.trim()) return { value: null, missing: false, empty: true };
  return { value: JSON.parse(raw), missing: false, empty: false };
}

function git(args) {
  const result = spawnSync("git", args, { cwd: ROOT, encoding: "utf8" });
  if (result.status !== 0) return null;
  return String(result.stdout ?? "").trim();
}

function resolveTagTrees(tag) {
  const out = git(["rev-parse", `${tag}^{}:apps`, `${tag}^{}:packages`]);
  const commit = git(["rev-parse", "--short=8", `${tag}^{}`]);
  if (!out) return { tagTrees: null, tagCommit: commit };
  const [apps, packages] = out.split(/\r?\n/).map((line) => line.trim());
  return { tagTrees: { apps, packages }, tagCommit: commit };
}

function cyclesInfo(file) {
  if (!existsSync(file)) return { present: false, empty: false, count: null };
  const raw = readFileSync(file, "utf8");
  if (!raw.trim()) return { present: true, empty: true, count: null };
  try {
    const parsed = JSON.parse(raw);
    const rows = Array.isArray(parsed)
      ? parsed
      : (parsed.cycles ?? parsed.results ?? null);
    return {
      present: true,
      empty: false,
      count: Array.isArray(rows) ? rows.length : null,
    };
  } catch {
    return { present: true, empty: false, count: null };
  }
}

function pad(value, width) {
  return String(value).padEnd(width);
}

function printReport({ day, tag, checks, verdict, facts, historical }) {
  const summary = summarizeChecks(checks);
  console.log(
    `[window-measurement] dia ${day} · tag ${tag} · pin apps ${WINDOW_CONFIG.appsHash.slice(0, 8)}`,
  );
  if (historical) {
    console.log(
      "  modo historico: la corrida NO se valida contra el arbol sellado (solo para auditoria del pasado).",
    );
  }
  console.log("");
  console.log(`${pad("comprobacion", 15)}${pad("estado", 9)}detalle`);
  console.log("-".repeat(110));
  for (const item of checks) {
    console.log(`${pad(item.id, 15)}${pad(item.status, 9)}${item.detail}`);
  }
  console.log("-".repeat(110));
  console.log(
    `OK ${summary.OK} · WARN ${summary.WARN} · FAIL ${summary.FAIL} · UNKNOWN ${summary.UNKNOWN}` +
      ` · ciclos cerrados ${facts.closedCycles ?? "null"} · medibles ${facts.measurableCycles ?? "null"}`,
  );
  console.log(`DICTAMEN: ${verdict}`);
  if (verdict === VERDICT.INCONCLUSIVE) {
    console.log(
      "  sin ciclos cerrados suficientes no hay evidencia de eficacia (no es un fallo de CI).",
    );
  }
  if (verdict === VERDICT.PREMATURE_TERMINATION) {
    console.log("  la corrida no dejo forward-market: la medicion NO cuenta.");
  }
  if (verdict === VERDICT.GREEN) {
    console.log(
      "  umbrales cumplidos sobre el arbol sellado; la ventana real sigue siendo OPERACION.",
    );
  }
}

function main() {
  let flags;
  try {
    flags = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.log(`[window-measurement] ${String(error.message)}`);
    console.log(
      "  uso: node scripts/window-measurement-check.mjs --day 20261109 [--expected-ticks 400] [--json]",
    );
    return 1;
  }
  if (!flags.day || !/^\d{8}$/.test(flags.day)) {
    console.log(
      "[window-measurement] --day es obligatorio y debe ser YYYYMMDD (p. ej. 20261109)",
    );
    return 1;
  }

  const runs = resolvePath(flags.runs);
  const manifestPath = join(runs, "window-runs", flags.day, "manifest.json");
  const forwardPath = join(runs, `forward-market-${flags.day}.json`);
  const certPath = flags.cert
    ? resolvePath(flags.cert)
    : join(runs, "paper-window-certification", `cert-${flags.day}.json`);
  const cyclesPath = flags.cycles
    ? resolvePath(flags.cycles)
    : join(runs, `paper-cycles-${flags.day}.json`);

  const iso = `${flags.day.slice(0, 4)}-${flags.day.slice(4, 6)}-${flags.day.slice(6, 8)}`;
  let manifest;
  let forward;
  let certification;
  try {
    manifest = readJson(manifestPath).value;
    forward = readJson(forwardPath).value;
    certification = readJson(certPath).value;
    if (!certification && !flags.cert) {
      // `window-certify` escribe por defecto `window-certificate.json`: se acepta solo
      // si su fecha capturada es la del dia (nunca un certificado de otra corrida).
      const fallback = readJson(
        join(runs, "paper-window-certification", "window-certificate.json"),
      ).value;
      const captured =
        fallback?.meta?.capturedAt ?? fallback?.capturedAt ?? null;
      if (captured && String(captured).startsWith(iso))
        certification = fallback;
    }
  } catch (error) {
    console.log(
      `[window-measurement] material ilegible: ${String(error.message)}`,
    );
    return 2;
  }

  const { tagTrees, tagCommit } = resolveTagTrees(flags.tag);
  const result = evaluateMeasurement({
    pin: WINDOW_CONFIG,
    tag: flags.tag,
    tagTrees,
    tagCommit,
    strictRunTree: !flags.historical,
    expectedTicks: flags.expectedTicks,
    blindTicks: flags.blindTicks,
    coverageStart: flags.coverageStart,
    coverageMidnight: flags.coverageMidnight,
    manifest,
    forward,
    forwardExists: Boolean(forward),
    certification,
    cyclesExport: cyclesInfo(cyclesPath),
  });

  if (flags.json) {
    console.log(
      JSON.stringify(
        {
          day: flags.day,
          tag: flags.tag,
          verdict: result.verdict,
          exitCode: result.exitCode,
          summary: summarizeChecks(result.checks),
          facts: result.facts,
          checks: result.checks,
        },
        null,
        2,
      ),
    );
  } else {
    printReport({
      day: flags.day,
      tag: flags.tag,
      checks: result.checks,
      verdict: result.verdict,
      facts: result.facts,
      historical: flags.historical,
    });
  }
  return result.exitCode;
}

process.exit(main());
